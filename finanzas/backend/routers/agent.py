import os, json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from database import get_db

router = APIRouter(prefix="/api/agent", tags=["agent"])

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
MAXIMOS_URL    = os.getenv("MAXIMOS_URL", "https://maximos-worker.luchotour.workers.dev")

SYSTEM_PROMPT = """Sos un asesor financiero personal de alto nivel. Hablás en español rioplatense, tono profesional y directo. Sin markdown, texto corrido.

Reglas de conducta:
- Respondé exclusivamente lo que se te pregunta. Si te saludan, saludá brevemente y preguntá en qué podés ayudar.
- Nunca vomites todos los datos de golpe. Usá solo la información relevante para la pregunta puntual.
- Sé preciso: mencioná montos, activos y fechas concretos cuando aporten valor a la respuesta.
- Si no hay suficiente contexto para dar una respuesta útil, pedí la información que falta.
- Mantené un tono calmo y seguro. No uses signos de exclamación ni expresiones de entusiasmo exagerado.
- Máximo 4 oraciones por respuesta, salvo que el usuario pida un análisis detallado.

Tenés acceso a los datos financieros reales del usuario: cuentas, posiciones con precios actuales de mercado, P&L no realizado, transacciones y resumen mensual. Usalos cuando sean pertinentes.

Si el usuario tiene liquidez disponible y te consulta sobre dónde invertir, podés mencionar el screener de mercado (maximos) para ver señales técnicas actuales."""

STABLECOINS = {'USDT', 'USDC', 'DAI', 'BUSD', 'FDUSD', 'TUSD', 'PYUSD'}
FIAT_USD    = {'USD'}
FIAT_ARS    = {'ARS'}
NO_PRICE_TYPES = {'fixed_term', 'fund', 'flexible'}

def to_yahoo_ticker(asset: str, asset_type: str) -> str:
    if asset_type == 'crypto' or (
        asset not in STABLECOINS and asset not in FIAT_USD and asset not in FIAT_ARS
        and asset_type not in ('stock', 'cedear', 'fixed_term', 'fund', 'flexible')
    ):
        return f"{asset}-USD"
    return asset

def build_context(conn) -> tuple[str, list]:
    accounts = conn.execute("SELECT * FROM accounts WHERE active = 1").fetchall()
    positions = conn.execute(
        "SELECT p.*, a.name as account_name FROM positions p JOIN accounts a ON p.account_id = a.id"
    ).fetchall()
    recent_tx = conn.execute(
        "SELECT t.*, a.name as account_name FROM transactions t JOIN accounts a ON t.account_id = a.id ORDER BY t.date DESC LIMIT 50"
    ).fetchall()
    summary = conn.execute("""
        SELECT strftime('%Y-%m', date) as month, currency,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
        FROM transactions
        GROUP BY month, currency
        ORDER BY month DESC
        LIMIT 6
    """).fetchall()
    realized = conn.execute("""
        SELECT currency, SUM(realized_pnl) as total
        FROM transactions WHERE realized_pnl IS NOT NULL
        GROUP BY currency
    """).fetchall()
    total_fees = conn.execute("""
        SELECT fee_currency, SUM(fee) as total FROM transactions
        WHERE fee IS NOT NULL AND fee > 0 GROUP BY fee_currency
    """).fetchall()

    ctx = "=== DATOS FINANCIEROS DEL USUARIO ===\n\n"

    ctx += "CUENTAS:\n"
    for a in accounts:
        ctx += f"- {a['name']} ({a['type']})\n"

    # Positions se devuelven por separado para enriquecer con precios
    ctx += "\nPOSICIONES ACTUALES (ver valuación actualizada abajo):\n"
    for p in positions:
        line = f"- {p['account_name']}: {p['quantity']} {p['asset']} ({p['asset_type']})"
        if p['avg_price']:
            line += f" | precio promedio USD {p['avg_price']}"
        if p['end_date']:
            line += f" | vence {p['end_date']}"
            if p['rate']:
                line += f" | tasa {p['rate']}% anual"
            if p['auto_renew']:
                line += " | renovación automática"
        if p['notes']:
            line += f" | {p['notes']}"
        ctx += line + "\n"

    ctx += "\nÚLTIMAS 50 TRANSACCIONES:\n"
    for t in recent_tx:
        sign = "+" if t['type'] == 'income' else ("-" if t['type'] == 'expense' else "↔")
        line = f"- {t['date']} | {t['account_name']} | {sign}{t['amount']} {t['currency']} | {t['description'] or ''} | {t['category'] or ''}"
        if t['unit_price']:
            line += f" | precio unit. USD {t['unit_price']}"
        if t['realized_pnl'] is not None:
            line += f" | P&L realizado USD {t['realized_pnl']:+.2f}"
        if t['fee']:
            line += f" | comisión {t['fee']} {t['fee_currency'] or ''}"
        ctx += line + "\n"

    ctx += "\nRESUMEN POR MES:\n"
    for r in summary:
        ctx += f"- {r['month']} {r['currency']}: ingresos {r['income']:.0f}, gastos {r['expense']:.0f}, balance {r['income']-r['expense']:.0f}\n"

    if realized:
        ctx += "\nP&L REALIZADO TOTAL:\n"
        for r in realized:
            ctx += f"- {r['currency']}: USD {r['total']:+.2f}\n"

    if total_fees:
        ctx += "\nCOMISIONES ACUMULADAS:\n"
        for f in total_fees:
            ctx += f"- {f['total']} {f['fee_currency']}\n"

    return ctx, [dict(p) for p in positions]

from datetime import date as _date, datetime as _datetime

def _calc_accrued(p: dict) -> float:
    """Interés devengado en moneda nativa. Replica calcAccruedInterest del frontend."""
    if not p.get('rate') or not p.get('start_date'):
        return 0.0
    try:
        start = _datetime.strptime(p['start_date'], "%Y-%m-%d").date()
    except Exception:
        return 0.0
    today = _date.today()
    end = None
    if p.get('end_date'):
        try:
            end = _datetime.strptime(p['end_date'], "%Y-%m-%d").date()
        except Exception:
            pass
    effective_end = min(end, today) if end and end < today else today
    days = (effective_end - start).days
    if days <= 0:
        return 0.0
    return p['quantity'] * (p['rate'] / 100) * (days / 365)

async def build_price_context(positions: list, client: httpx.AsyncClient) -> str:
    """Fetches current market prices from maximos and returns a full portfolio valuation."""
    quotes = {}
    blue_rate = None

    try:
        r = await client.get(f"{MAXIMOS_URL}/api/dollar", timeout=5)
        if r.is_success:
            blue_list = r.json().get("dollar", [])
            blue = next((d for d in blue_list if "blue" in (d.get("nombre") or "").lower()), None)
            if blue:
                blue_rate = blue.get("venta")
    except Exception:
        pass

    needs_quote = [
        p for p in positions
        if p['asset'] not in STABLECOINS
        and p['asset'] not in FIAT_USD
        and p['asset'] not in FIAT_ARS
        and p['asset_type'] not in NO_PRICE_TYPES
    ]

    if needs_quote:
        tickers = ",".join({to_yahoo_ticker(p['asset'], p['asset_type']) for p in needs_quote})
        try:
            r = await client.get(f"{MAXIMOS_URL}/api/quotes?tickers={tickers}", timeout=10)
            if r.is_success:
                quotes = r.json().get("quotes", {})
        except Exception:
            pass

    def get_market_price(p) -> Optional[float]:
        asset, atype = p['asset'], p['asset_type']
        if asset in FIAT_USD or asset in STABLECOINS:
            return 1.0
        if asset in FIAT_ARS:
            return (1 / blue_rate) if blue_rate else None
        if atype in NO_PRICE_TYPES:
            return None
        q = quotes.get(to_yahoo_ticker(asset, atype))
        return q['price'] if q else None

    ctx = "\nVALUACIÓN ACTUAL DE CARTERA:\n"
    if blue_rate:
        ctx += f"Dólar blue: ARS {blue_rate:.0f}\n"

    total_usd = 0.0
    for p in positions:
        asset   = p['asset']
        atype   = p['asset_type']
        qty     = p['quantity']
        accrued = _calc_accrued(p)
        total_native = qty + accrued

        market_price = get_market_price(p)

        if market_price is not None:
            # Fiat, stablecoin, crypto, acción, cedear con precio conocido
            value_usd = total_native * market_price
            total_usd += value_usd
            if asset in FIAT_USD or asset in FIAT_ARS or asset in STABLECOINS:
                line = f"- {p['account_name']} | {asset} ({atype}): {total_native:,.2f} = USD {value_usd:,.2f}"
            else:
                line = f"- {p['account_name']} | {asset} ({atype}): {qty} × USD {market_price:,.4g} = USD {value_usd:,.2f}"
                avg = p.get('avg_price')
                if avg and avg > 0:
                    upnl = (market_price - avg) * qty
                    pct  = (market_price - avg) / avg * 100
                    line += f" | P&L no realizado USD {upnl:+,.2f} ({pct:+.1f}%)"

        elif atype in NO_PRICE_TYPES:
            # Plazo fijo / fondo / rendimiento flexible — valuado por su moneda subyacente
            if asset in FIAT_USD or asset in STABLECOINS:
                value_usd = total_native
                total_usd += value_usd
                line = f"- {p['account_name']} | {asset} ({atype}): capital {qty:,.2f}"
                if accrued:
                    line += f" + interés devengado {accrued:,.2f}"
                line += f" = USD {value_usd:,.2f}"
            elif asset in FIAT_ARS and blue_rate:
                value_usd = total_native / blue_rate
                total_usd += value_usd
                line = f"- {p['account_name']} | {asset} ({atype}): capital {qty:,.0f} ARS"
                if accrued:
                    line += f" + interés {accrued:,.0f} ARS"
                line += f" = USD {value_usd:,.2f}"
            else:
                line = f"- {p['account_name']} | {asset} ({atype}): {total_native:,.2f} (moneda sin conversión disponible)"
        else:
            line = f"- {p['account_name']} | {asset} ({atype}): {qty} (precio no disponible)"

        ctx += line + "\n"

    ctx += f"TOTAL CARTERA: USD {total_usd:,.2f}"
    if blue_rate:
        ctx += f" ≈ ARS {total_usd * blue_rate:,.0f}"
    ctx += "\n"
    if not quotes and needs_quote:
        ctx += "(Nota: maximos no disponible — precios de mercado sin actualizar)\n"

    return ctx

class ChatMessage(BaseModel):
    role: str   # user | assistant
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@router.post("/chat")
async def chat(req: ChatRequest):
    conn = get_db()
    db_context, positions = build_context(conn)
    conn.close()

    async with httpx.AsyncClient(timeout=30) as client:
        price_context = await build_price_context(positions, client)
        full_context  = db_context + price_context

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + full_context}
        ] + [{"role": m.role, "content": m.content} for m in req.messages]

        # Groq primero
        if GROQ_API_KEY:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={"model": "llama-3.3-70b-versatile", "messages": messages, "temperature": 0.7},
                )
                if r.is_success:
                    return {"reply": r.json()["choices"][0]["message"]["content"]}
            except Exception:
                pass

        # Gemini como fallback
        if GOOGLE_API_KEY:
            try:
                gemini_messages = [{"parts": [{"text": m["content"]}], "role": "user" if m["role"] != "assistant" else "model"} for m in messages if m["role"] != "system"]
                system_text = next((m["content"] for m in messages if m["role"] == "system"), "")
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}",
                    json={
                        "system_instruction": {"parts": [{"text": system_text}]},
                        "contents": gemini_messages,
                        "generationConfig": {"temperature": 0.7},
                    },
                )
                if r.is_success:
                    return {"reply": r.json()["candidates"][0]["content"]["parts"][0]["text"]}
            except Exception:
                pass

    raise HTTPException(503, "No se pudo conectar con el agente de IA. Verificá las API keys.")

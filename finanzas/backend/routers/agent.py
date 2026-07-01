import os, json, asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from database import get_db

router = APIRouter(prefix="/api/agent", tags=["agent"])

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
MAXIMOS_URL    = os.getenv("MAXIMOS_URL", "https://maximos-worker.luchotour.workers.dev")

SYSTEM_PROMPT = """Sos el asesor financiero personal del usuario. Conocés su cartera en detalle, su historial de movimientos y los precios actuales de mercado. Hablás en español rioplatense, directo y sin rodeos, como alguien de confianza que sabe de lo que habla.

Cómo responder:
- Máximo 3-4 oraciones. Si el usuario pide análisis detallado, podés extenderte.
- Siempre arrancá desde los números reales del usuario: cuánto tiene, a qué precio promedio entró, cuánto lleva ganado o perdido. No hablés en abstracto.
- Tomá posición. Recomendá una cosa concreta y justificala con 1-2 datos clave. No listes opciones sin comprometerte con ninguna.
- Si hay datos técnicos disponibles (RSI, zona, tendencia), usalos como argumento dentro de la recomendación, no como una lista de indicadores.
- Nunca termines con frases genéricas como "considerá tu tolerancia al riesgo" o "consultá un profesional". Eso ya lo saben.
- Tono: calmo, seguro, sin exclamaciones. Como el amigo que más sabe de inversiones.

Tenés acceso a los datos financieros reales: cuentas, posiciones con precios actuales de mercado, P&L no realizado por posición, transacciones históricas, resumen mensual y análisis técnico actualizado de cada activo en cartera (señal, RSI, ADX, zona, MACD, volumen, medias móviles, patrones de velas, SL/TP).

Filosofía:
- La construcción de patrimonio es a largo plazo. El DCA es válido en activos con convicción real, no para tapar errores.
- Un movimiento sin volumen es una trampa hasta que se confirme. Si el volumen es bajo y la señal es débil, decilo.
- Los indicadores técnicos tienen prioridad sobre el ruido del mercado.

Contexto Argentina:
- El dólar blue y la brecha son variables clave para activos en ARS.
- Los CEDEARs cubren contra devaluación: su valor en pesos sube cuando cae el peso.
- Plazo fijo en ARS solo vale si la tasa real supera la inflación proyectada."""

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
        and p['asset_type'] not in ('fixed_term', 'fund')
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
        if atype in ('fixed_term', 'fund'):
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
            if p.get('end_date'):
                line += f" | vence {p['end_date']}"
                if p.get('rate'):
                    line += f" | tasa {p['rate']}% anual"
                if p.get('auto_renew'):
                    line += " | renovación automática"
        else:
            line = f"- {p['account_name']} | {asset} ({atype}): {qty} (precio no disponible)"

        if p.get('notes'):
            line += f" | nota: {p['notes']}"
        ctx += line + "\n"

    ctx += f"TOTAL CARTERA: USD {total_usd:,.2f}"
    if blue_rate:
        ctx += f" ≈ ARS {total_usd * blue_rate:,.0f}"
    ctx += "\n"
    if not quotes and needs_quote:
        ctx += "(Nota: maximos no disponible — precios de mercado sin actualizar)\n"

    return ctx

ASSET_TYPE_TO_LIST = {
    'crypto':   'crypto',
    'flexible': 'crypto',
    'cedear':   'adrs_arg',
    'stock':    'sp500',
}

async def build_technical_context(positions: list, client: httpx.AsyncClient) -> str:
    """Fetches technical indicators from maximos screener for assets in portfolio."""
    lists_needed = {}
    for p in positions:
        asset, atype = p['asset'], p['asset_type']
        if asset in FIAT_USD or asset in FIAT_ARS or asset in STABLECOINS:
            continue
        list_id = ASSET_TYPE_TO_LIST.get(atype)
        if list_id:
            lists_needed.setdefault(list_id, set()).add(asset)

    if not lists_needed:
        return ""

    all_data = {}
    async def fetch_list(list_id):
        try:
            r = await client.get(f"{MAXIMOS_URL}/api/stocks?list_id={list_id}&signal=all", timeout=10)
            if r.is_success:
                for s in r.json().get('stocks', []):
                    t = s.get('ticker', '')
                    key = t[:-4] if t.endswith('-USD') else t
                    all_data[key] = s
        except Exception:
            pass

    await asyncio.gather(*[fetch_list(lid) for lid in lists_needed])

    signal_label = {
        'compra_fuerte': 'COMPRA FUERTE', 'compra': 'COMPRA',
        'neutral': 'NEUTRAL', 'venta': 'VENTA', 'venta_fuerte': 'VENTA FUERTE',
    }
    zone_label = {'discount': 'descuento', 'fair': 'valor justo', 'premium': 'premium'}

    lines = []
    for p in positions:
        asset = p['asset']
        if asset not in all_data:
            continue
        d = all_data[asset]
        line = f"\n{asset} — {signal_label.get(d.get('signal','neutral'), 'NEUTRAL')}"
        line += f" | Score: {d.get('long_score',0)}L / {d.get('short_score',0)}S"
        line += f" | Zona: {zone_label.get(d.get('zone','fair'), d.get('zone',''))}"
        line += f" | RSI: {round(d['rsi'],1) if d.get('rsi') else '—'}"
        line += f" | ADX: {round(d['adx'],1) if d.get('adx') else '—'}"
        if d.get('macd_hist') is not None:
            line += f" | MACD hist: {round(d['macd_hist'],4)}"
        if d.get('vol_ratio') is not None:
            line += f" | Volumen: {round(d['vol_ratio'],2)}x promedio"
        if d.get('pulse_signal'):
            line += f" | Pulse: {d.get('pulse_state','')} / {d.get('pulse_signal','')}"
        if d.get('pct_from_high') is not None:
            line += f" | Dist. máx 52s: {d['pct_from_high']:.1f}%"
        # Medias móviles clave
        ma_parts = []
        for name, key in [('MA20','pct_vs_ma20'),('MA50','pct_vs_ma50'),('MA200','pct_vs_ma200')]:
            v = d.get(key)
            if v is not None:
                ma_parts.append(f"{name}: {'+' if v >= 0 else ''}{v:.1f}%")
        if ma_parts:
            line += f"\n  Medias móviles: {' | '.join(ma_parts)}"
        if d.get('candle_pattern') and isinstance(d['candle_pattern'], dict) and d['candle_pattern'].get('name'):
            cp = d['candle_pattern']
            type_map = {'bullish': 'alcista', 'bearish': 'bajista', 'neutral': 'indecisión'}
            line += f"\n  Patrón velas: {cp['name']} ({type_map.get(cp.get('type',''), cp.get('type',''))})"
        if d.get('sl'):
            line += f"\n  SL: ${d['sl']} | TP1: ${d['tp1']} | TP2: ${d['tp2']}"
        lines.append(line)

    if not lines:
        return ""

    return "\nANÁLISIS TÉCNICO (último screener de maximos):\n" + "\n".join(lines) + "\n"


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
        price_context, tech_context = await asyncio.gather(
            build_price_context(positions, client),
            build_technical_context(positions, client),
        )
        full_context = db_context + price_context + tech_context

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

import os, json, asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from database import get_db

router = APIRouter(prefix="/api/agent", tags=["agent"])

GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY    = os.getenv("GOOGLE_API_KEY", "")
MAXIMOS_URL       = os.getenv("MAXIMOS_URL", "https://maximos-worker.luchotour.workers.dev")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

SYSTEM_PROMPT = """Sos el asesor financiero personal del usuario. Conocés su cartera en detalle, su historial de movimientos y los precios actuales de mercado. Hablás en español rioplatense, directo y sin rodeos, como alguien de confianza que sabe de lo que habla.

Cómo responder:
- Máximo 3-4 oraciones. Si el usuario pide análisis detallado, podés extenderte.
- Siempre arrancá desde los números reales del usuario: cuánto tiene, a qué precio promedio entró, cuánto lleva ganado o perdido. No hablés en abstracto.
- Tomá posición. Recomendá una cosa concreta y justificala con 1-2 datos clave. No listes opciones sin comprometerte con ninguna.
- Si hay datos técnicos disponibles (RSI, zona, tendencia), usalos para pensar tu conclusión, pero nunca los nombres crudos en la respuesta ("RSI 49.7", "ADX bajo") — traducilos a una idea simple ("el precio viene sin fuerza"). El usuario te tiene a vos para no tener que saber qué es un indicador.
- Si el usuario ya te contó su estrategia u objetivo para un activo (perfil de inversión, o una nota en la posición — ej. "hago DCA hasta el halving para vender todo"), esa estrategia manda. Tu trabajo es evaluar si lo que está haciendo tiene sentido dado ESO, no proponerle algo distinto porque un indicador técnico de corto plazo diga otra cosa.
- Nunca termines con frases genéricas como "considerá tu tolerancia al riesgo" o "consultá un profesional". Eso ya lo saben.
- Tono: calmo, seguro, sin exclamaciones. Como el amigo que más sabe de inversiones.

Precisión numérica (crítico):
- Cuando tenés los números exactos en el contexto, usá esos números. Nunca redondees a cifras aproximadas como "USD 2,500" si el dato real es USD 1,704.16.
- NUNCA sumes vos el P&L no realizado de varias posiciones a mano — sos malo sumando muchas líneas y vas a inventar un total incorrecto (ya pasó). El total ya viene calculado en "P&L NO REALIZADO TOTAL" dentro de VALUACIÓN ACTUAL DE CARTERA — usá ESE número tal cual, no lo recalcules ni lo verifiques sumando.
- El P&L no realizado de cada posición individual en el contexto ya está calculado — usá esos valores directamente, no los recalcules.
- "P&L no realizado" = diferencia entre precio actual y precio promedio de compra, no desde el máximo histórico ni el máximo del año.
- NUNCA confundas "FLUJO DE CAJA POR MES" con ganancia o pérdida. Esas cifras (entradas/salidas/flujo neto) son movimientos de plata — depósitos, compras, transferencias entre cuentas, swaps — no rendimiento de inversión. Un flujo neto positivo puede ser simplemente plata que el usuario metió ese mes, no una ganancia. Para hablar de cuánto ganó o perdió usá EXCLUSIVAMENTE "P&L REALIZADO TOTAL" y el "P&L no realizado" de cada posición en VALUACIÓN ACTUAL DE CARTERA — nunca el flujo de caja.
- No existe un snapshot histórico del valor total de la cartera (no hay "cuánto valía todo a principio de mes") — no inventes ni estimes una comparación de patrimonio total vs. hace una semana/mes. Si querés hablar de evolución, usá el P&L realizado + no realizado, que sí son datos reales.
- El "P&L realizado + no realizado" combinado sirve para hablar de la CARTERA completa — nunca para decidir o justificar qué hacer con UNA posición puntual. Si te preguntan "¿qué hago con ETH?" o similar, la pérdida/ganancia que importa es SOLO el no realizado de esa posición (lo que pasa si vendés lo que tenés hoy). El realizado de ventas viejas de ese mismo activo ya pasó, es plata que ya no está en juego — sumarlo infla o desinfla el número y te hace recomendar en base a algo que no cambia si vendés ahora o no. Podés mencionarlo aparte como dato histórico, pero no lo sumes al no realizado para armar una "pérdida total" de esa posición.

Tenés acceso a los datos financieros reales: cuentas, posiciones con precios actuales de mercado, P&L no realizado por posición, transacciones históricas, flujo de caja mensual, análisis técnico actualizado (señal, RSI, ADX, zona, MACD, volumen, medias móviles, patrones de velas, SL/TP) y fundamentales con consenso de analistas (recommendation_key, target price, PE, earnings date) para stocks y CEDEARs.

Cómo usar los fundamentales:
- El "consensus" de analistas es el agregado institucional — si coincide con la señal técnica, es argumento fuerte; si diverge, mencionalo como tensión.
- El target price vs precio actual te da el upside implícito según Wall Street — calculalo y mencionalo si es relevante.
- El earnings date próximo es un catalizador concreto: si está en las próximas semanas, avisá.

Cómo usar el sentimiento de mercado crypto:
- Fear & Greed < 25 (Miedo extremo): históricamente zona de acumulación. Fear & Greed > 75 (Codicia extrema): zona de prudencia.
- Funding rate > 0.05%: mercado sobre-apalancado long → riesgo de liquidación en cascada a la baja. Funding < -0.03%: shorts dominan → squeeze potencial al alza.
- L/S ratio > 1 = más longs que shorts; < 1 = más shorts que longs.

Filosofía:
- La construcción de patrimonio es a largo plazo. El DCA es válido en activos con convicción real, no para tapar errores.
- Un movimiento sin volumen es una trampa hasta que se confirme. Si el volumen es bajo y la señal es débil, decilo.
- Los indicadores técnicos tienen prioridad sobre el ruido del mercado — pero nunca sobre la estrategia que el usuario ya declaró para ese activo.

Contexto Argentina:
- Usamos el dólar CCL (contado con liquidación) como referencia para convertir ARS↔USD — es el tipo de cambio real al que se arbitran los CEDEARs, no el blue.
- Los CEDEARs cubren contra devaluación: su valor en pesos sube cuando cae el peso.
- Plazo fijo en ARS solo vale si la tasa real supera la inflación proyectada."""

STABLECOINS = {'USDT', 'USDC', 'DAI', 'BUSD', 'FDUSD', 'TUSD', 'PYUSD'}
FIAT_USD    = {'USD'}
FIAT_ARS    = {'ARS'}
NO_PRICE_TYPES = {'fixed_term', 'fund', 'flexible'}
# 'cedear' cotiza y se compra en ARS (avg_price en ARS, hay que convertir con el dólar).
# 'cedear_usd' es el segmento que se opera directo en dólares (ticker con sufijo D en el
# broker) — avg_price ya está en USD, no se convierte.
CEDEAR_TYPES = {'cedear', 'cedear_usd'}

def to_yahoo_ticker(asset: str, asset_type: str) -> str:
    if asset_type == 'crypto':
        return f"{asset}-USD"
    if asset_type == 'flexible' and asset not in STABLECOINS and asset not in FIAT_USD and asset not in FIAT_ARS:
        return f"{asset}-USD"
    if (asset not in STABLECOINS and asset not in FIAT_USD and asset not in FIAT_ARS
            and asset_type not in ('stock', 'cedear', 'cedear_usd', 'fixed_term', 'fund', 'flexible')):
        return f"{asset}-USD"
    return asset

def get_investment_profile(conn) -> str:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'investment_profile'").fetchone()
    return (row['value'] if row else '') or ''

def build_context(conn) -> tuple[str, list]:
    profile = get_investment_profile(conn)
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

    if profile.strip():
        ctx += (
            "PERFIL DE INVERSIÓN DEL USUARIO (esto lo escribió él mismo — es su objetivo y su "
            "estrategia real, y tiene PRIORIDAD sobre cualquier conclusión genérica que saques de "
            "indicadores técnicos. Tu trabajo es evaluar si lo que está haciendo es coherente con ESTO, "
            "no proponerle una estrategia distinta porque un RSI diga otra cosa):\n"
            f"{profile.strip()}\n\n"
        )

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

    ctx += "\nFLUJO DE CAJA POR MES (depósitos, compras, transferencias, retiros — esto NO es ganancia ni pérdida de inversión, es movimiento de plata entre cuentas/activos; para P&L usar la sección P&L REALIZADO TOTAL y el P&L no realizado de VALUACIÓN ACTUAL DE CARTERA):\n"
    for r in summary:
        ctx += f"- {r['month']} {r['currency']}: entradas {r['income']:.0f}, salidas {r['expense']:.0f}, flujo neto {r['income']-r['expense']:.0f}\n"

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
    ccl_rate = None

    try:
        r = await client.get(f"{MAXIMOS_URL}/api/dollar", timeout=5)
        if r.is_success:
            dollar_list = r.json().get("dollar", [])
            # CCL (contado con liquidación): es el tipo de cambio real al que se arbitran
            # los CEDEARs en ARS — no el blue, que es un mercado informal aparte.
            ccl = next((d for d in dollar_list if d.get("casa") == "contadoconliqui"), None)
            if ccl:
                ccl_rate = ccl.get("venta")
    except Exception:
        pass

    needs_quote = [
        p for p in positions
        if p['asset'] not in STABLECOINS
        and p['asset'] not in FIAT_USD
        and p['asset'] not in FIAT_ARS
        and p['asset_type'] not in ('fixed_term', 'fund')
    ]

    crypto_assets = {
        p['asset'] for p in needs_quote
        if p['asset_type'] in ('crypto', 'flexible')
        and p['asset'] not in STABLECOINS
    }
    stock_tickers = {
        to_yahoo_ticker(p['asset'], p['asset_type']) for p in needs_quote
        if p['asset_type'] not in ('crypto', 'flexible')
    }

    # Crypto: directo a Binance desde el backend local (evita problemas del Worker con Binance)
    async def fetch_binance(symbol: str):
        try:
            r = await client.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT",
                timeout=5,
            )
            if r.is_success:
                d = r.json()
                if "price" in d:
                    quotes[f"{symbol}-USD"] = {"price": round(float(d["price"]), 4)}
        except Exception:
            pass

    await asyncio.gather(*[fetch_binance(s) for s in crypto_assets])

    # Stocks / CEDEARs: maximos local primero (yfinance, no depende de que el
    # Worker tenga el D1 al día) — si no está corriendo, cae al Worker online
    if stock_tickers:
        tickers_str = ",".join(stock_tickers)
        got_local = False
        try:
            r = await client.get(f"http://localhost:8000/api/quotes?tickers={tickers_str}", timeout=3)
            if r.is_success:
                local_quotes = r.json().get("quotes", {})
                if local_quotes:
                    quotes.update(local_quotes)
                    got_local = True
        except Exception:
            pass
        if not got_local:
            try:
                r = await client.get(f"{MAXIMOS_URL}/api/quotes?tickers={tickers_str}", timeout=10)
                if r.is_success:
                    quotes.update(r.json().get("quotes", {}))
            except Exception:
                pass

    def get_market_price(p) -> Optional[float]:
        asset, atype = p['asset'], p['asset_type']
        if asset in FIAT_USD or asset in STABLECOINS:
            return 1.0
        if asset in FIAT_ARS:
            return (1 / ccl_rate) if ccl_rate else None
        if atype in ('fixed_term', 'fund'):
            return None
        q = quotes.get(to_yahoo_ticker(asset, atype))
        if not q:
            return None
        price = q['price']
        # CEDEAR (ARS o USD): el precio en D1/yfinance es de la acción subyacente en USD —
        # dividir por el ratio para obtener el precio por CEDEAR (mismo criterio que el frontend)
        if atype in CEDEAR_TYPES and p.get('rate'):
            price = price / p['rate']
        return price

    total_usd = 0.0
    by_asset = {}  # consolida el mismo activo entre cuentas (ej. BTC en Binance + Nexo)
    raw = []  # datos intermedios por posición — se arma la línea recién en la 2da pasada,
              # cuando ya sabemos qué activos son multi-cuenta

    for p in positions:
        asset   = p['asset']
        atype   = p['asset_type']
        qty     = p['quantity']
        accrued = _calc_accrued(p)
        total_native = qty + accrued
        market_price = get_market_price(p)
        value_usd = None

        if market_price is not None:
            value_usd = total_native * market_price
            total_usd += value_usd
            if asset not in FIAT_USD and asset not in FIAT_ARS and asset not in STABLECOINS:
                # Trackear TODA posición real (tenga o no avg_price) para detectar el mismo
                # activo repartido en más de una cuenta — si solo trackeáramos las que tienen
                # avg_price, una cuenta sin precio cargado (ej. XRP en Nexo sin avg_price) queda
                # afuera de la consolidación y su cantidad/valor desaparece silenciosamente.
                acc = by_asset.setdefault(asset, {"qty": 0.0, "value": 0.0, "accounts": [], "atype": atype, "legs": []})
                acc["qty"] += qty
                acc["value"] += value_usd
                acc["accounts"].append(p['account_name'])
                # Por cuenta: cantidad + avg_price crudo, para el fallback de pooled_avg_usd
                # (el usuario no siempre carga cada movimiento — a veces corrige la posición
                # directo en Portfolio, sin transacción de respaldo).
                acc["legs"].append({"account_id": p['account_id'], "qty": qty, "avg_price_raw": p.get('avg_price')})
        elif atype in NO_PRICE_TYPES:
            if asset in FIAT_USD or asset in STABLECOINS:
                value_usd = total_native
                total_usd += value_usd
            elif asset in FIAT_ARS and ccl_rate:
                value_usd = total_native / ccl_rate
                total_usd += value_usd

        raw.append({"p": p, "asset": asset, "atype": atype, "qty": qty, "accrued": accrued,
                    "total_native": total_native, "market_price": market_price, "value_usd": value_usd})

    # El avg_price GUARDADO por posición no sirve tal cual para el P&L de un activo multi-cuenta:
    # cuando cripto se transfiere de una cuenta a otra, la transacción de entrada "hereda" el
    # avg_price de la cuenta origen (para que esa cuenta sola muestre un costo real en su propia
    # ficha) — pero eso cuenta el mismo costo dos veces si después sumás el P&L de cada cuenta
    # por separado, y también distorsiona la ficha de esa cuenta individual (bug real: la ficha
    # de BTC en Nexo sola mostraba +16.7% usando su avg_price local $68.000, cuando el promedio
    # real ponderado entre todas las cuentas es $75.766 y el P&L real de esa porción es +4.7%).
    # La forma correcta (la misma que "Promedio combinado" en Patrimonio en el frontend) es, por
    # CADA CUENTA de un activo multi-cuenta, calcular su costo "limpio" desde sus propias compras
    # reales (excluyendo source='transfer') y ponderarlo por la cantidad que esa cuenta tiene HOY.
    # PERO el usuario no siempre carga cada movimiento — a veces corrige la posición directo en
    # Portfolio sin dejar una transacción de respaldo — así que si una cuenta no tiene ninguna
    # compra propia con precio, se usa su avg_price guardado (manual o lo que sea) como respaldo
    # en vez de excluirla del todo, que subestimaría el costo real y exageraría la ganancia.
    consolidated = {a: d for a, d in by_asset.items() if len(d["accounts"]) > 1}
    leg_direct_cost = {}  # (account_id, currency) -> {"qty":, "cost":} desde compras propias, sin transferencias
    if consolidated:
        conn2 = get_db()
        try:
            rows = conn2.execute(
                "SELECT account_id, currency, amount, unit_price FROM transactions "
                "WHERE currency IN ({}) AND source != 'transfer' AND type IN ('income','buy') "
                "AND unit_price IS NOT NULL AND unit_price > 0".format(
                    ",".join("?" for _ in consolidated)),
                list(consolidated.keys())
            ).fetchall()
        finally:
            conn2.close()
        for r in rows:
            key = (r["account_id"], r["currency"])
            acc = leg_direct_cost.setdefault(key, {"qty": 0.0, "cost": 0.0})
            acc["qty"] += r["amount"]
            acc["cost"] += r["amount"] * r["unit_price"]

    _pooled_avg_cache = {}

    def pooled_avg_usd(asset, atype):
        """Promedio real ponderado en USD de un activo repartido en varias cuentas.

        Dos partes que NO se pueden mezclar en un solo pool de cantidad, porque una
        representa "cantidad alguna vez comprada" y la otra "cantidad que tengo hoy":
        1) Cuentas con compras propias (excluyendo transferencias): un único promedio
           global = costo total comprado / cantidad total comprada (weighted-average-cost
           estándar — no cambia al vender, así que se aplica tal cual a la cantidad que
           esas cuentas tienen HOY, sin importar cuánto de lo comprado ya se vendió o
           se transfirió a otro lado).
        2) Cuentas SIN ninguna compra propia con precio (el usuario corrigió la posición
           directo en Portfolio sin cargar movimiento) — no hay pool que armar ahí, se
           usa su avg_price guardado tal cual, ponderado por su cantidad actual.
        """
        if asset in _pooled_avg_cache:
            return _pooled_avg_cache[asset]
        d = by_asset.get(asset)
        global_pool_qty = 0.0   # cantidad ALGUNA VEZ comprada (cuentas con respaldo de transacciones)
        global_pool_cost = 0.0
        tx_backed_qty_now = 0.0  # cantidad que esas cuentas tienen HOY
        manual_cost = 0.0
        manual_qty = 0.0
        for leg in (d["legs"] if d else []):
            direct = leg_direct_cost.get((leg["account_id"], asset))
            if direct and direct["qty"]:
                global_pool_qty += direct["qty"]
                global_pool_cost += direct["cost"]
                tx_backed_qty_now += leg["qty"]
            else:
                leg_avg = leg["avg_price_raw"]  # respaldo: manual o lo que haya, mejor que nada
                if leg_avg and atype == 'cedear' and ccl_rate:
                    leg_avg = leg_avg / ccl_rate
                if leg_avg and leg_avg > 0:
                    manual_cost += leg_avg * leg["qty"]
                    manual_qty += leg["qty"]

        global_avg = (global_pool_cost / global_pool_qty) if global_pool_qty else None
        total_cost = (global_avg * tx_backed_qty_now if global_avg is not None else 0.0) + manual_cost
        total_qty = (tx_backed_qty_now if global_avg is not None else 0.0) + manual_qty
        result = (total_cost / total_qty) if total_qty else None
        _pooled_avg_cache[asset] = result
        return result

    ctx = "\nVALUACIÓN ACTUAL DE CARTERA:\n"
    if ccl_rate:
        ctx += f"Dólar CCL: ARS {ccl_rate:.0f}\n"

    total_unrealized_pnl = 0.0  # se suma en Python, nunca se le pide al modelo que sume esto
    for r in raw:
        p, asset, atype = r["p"], r["asset"], r["atype"]
        qty, accrued, total_native = r["qty"], r["accrued"], r["total_native"]
        market_price, value_usd = r["market_price"], r["value_usd"]

        if market_price is not None:
            if asset in FIAT_USD or asset in FIAT_ARS or asset in STABLECOINS:
                line = f"- {p['account_name']} | {asset} ({atype}): {total_native:,.2f} = USD {value_usd:,.2f}"
            else:
                line = f"- {p['account_name']} | {asset} ({atype}): {qty} × USD {market_price:,.4g} = USD {value_usd:,.2f}"
                if asset in consolidated:
                    avg_usd = pooled_avg_usd(asset, atype)
                else:
                    avg = p.get('avg_price')
                    # 'cedear' (ARS): avg_price está en ARS por CEDEAR — convertir con el CCL
                    # antes de comparar contra market_price (USD). 'cedear_usd' ya está en USD.
                    avg_usd = (avg / ccl_rate) if (atype == 'cedear' and avg and ccl_rate) else avg
                    if atype == 'cedear' and not ccl_rate:
                        avg_usd = None
                if avg_usd and avg_usd > 0:
                    # value_usd usa total_native (qty + interés devengado) — el costo solo usa
                    # qty (el interés no tiene costo, es ganancia pura). Restar avg_usd*qty de
                    # value_usd (no de market_price*qty) para que el interés devengado quede
                    # contado como ganancia, igual que ya hace la sección CONSOLIDADO y el frontend.
                    upnl = value_usd - avg_usd * qty
                    pct  = (market_price - avg_usd) / avg_usd * 100
                    total_unrealized_pnl += upnl
                    line += f" | precio prom. compra USD {avg_usd:,.4g} | P&L no realizado USD {upnl:+,.2f} ({pct:+.1f}% vs precio promedio de compra)"

        elif atype in NO_PRICE_TYPES:
            # Plazo fijo / fondo / rendimiento flexible — valuado por su moneda subyacente
            if asset in FIAT_USD or asset in STABLECOINS:
                line = f"- {p['account_name']} | {asset} ({atype}): capital {qty:,.2f}"
                if accrued:
                    line += f" + interés devengado {accrued:,.2f}"
                line += f" = USD {value_usd:,.2f}"
            elif asset in FIAT_ARS and ccl_rate:
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

    consolidated_lines = []
    for asset, d in consolidated.items():
        avg_w = pooled_avg_usd(asset, d["atype"])
        pnl = (d["value"] - avg_w * d["qty"]) if avg_w is not None else None
        pct = (pnl / (avg_w * d["qty"]) * 100) if (pnl is not None and avg_w) else None
        line = f"- {asset}: {d['qty']:.6g} total entre {', '.join(d['accounts'])} = USD {d['value']:,.2f}"
        if avg_w is not None:
            line += f" | precio prom. ponderado USD {avg_w:,.4g} | P&L no realizado consolidado USD {pnl:+,.2f} ({pct:+.1f}%)"
        consolidated_lines.append(line)

    ctx += f"TOTAL CARTERA: USD {total_usd:,.2f}"
    if ccl_rate:
        ctx += f" ≈ ARS {total_usd * ccl_rate:,.0f}"
    ctx += "\n"
    ctx += (f"P&L NO REALIZADO TOTAL (ya sumado en código, no lo recalcules ni lo estimes — "
            f"usá este número tal cual): USD {total_unrealized_pnl:+,.2f}\n")
    if not quotes and needs_quote:
        ctx += "(Nota: maximos no disponible — precios de mercado sin actualizar)\n"

    if consolidated_lines:
        ctx += "\nCONSOLIDADO POR ACTIVO (mismo activo repartido en más de una cuenta — usar ESTO para el veredicto único, no tratar cada cuenta como una posición aparte):\n"
        ctx += "\n".join(consolidated_lines) + "\n"

    if by_asset:
        ctx += (
            "\nCHECKLIST INTERNO (no lo reproduzcas en tu respuesta, es solo para que te "
            "autocontroles) — activos con posición real y precio de mercado, uno por línea arriba "
            "(fiat/stablecoin no incluidos acá): " + ", ".join(sorted(by_asset.keys())) + ". "
            "Si armás una tabla de veredictos por activo, tiene que haber EXACTAMENTE una fila por "
            "cada uno de estos — ni uno menos. Ya pasó que se te quedó afuera un activo entero "
            "(ETH) con datos completos en el contexto; contá esta lista antes de dar la tabla por "
            "terminada, pero no la pegues como texto en tu respuesta.\n"
        )

    return ctx

ASSET_TYPE_TO_LIST = {
    'crypto':     'crypto',
    'flexible':   'crypto',
    'cedear':     'adrs_arg',
    'cedear_usd': 'adrs_arg',
    'stock':      'sp500',
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


async def build_fundamentals_context(positions: list, client: httpx.AsyncClient) -> str:
    """Fetches analyst consensus + fundamentals from Yahoo Finance via /api/info for stocks and CEDEARs."""
    tickers = list({
        p['asset'] for p in positions
        if p['asset_type'] in ('stock', 'cedear', 'cedear_usd')
        and p['asset'] not in STABLECOINS
        and p['asset'] not in FIAT_USD
        and p['asset'] not in FIAT_ARS
    })
    if not tickers:
        return ""

    infos: dict = {}

    async def fetch_info(ticker: str):
        try:
            r = await client.get(f"{MAXIMOS_URL}/api/info?ticker={ticker}", timeout=8)
            if r.is_success:
                info = r.json().get("info", {})
                if info and (info.get("recommendation_key") or info.get("target_price") or info.get("trailing_pe")):
                    infos[ticker] = info
        except Exception:
            pass

    await asyncio.gather(*[fetch_info(t) for t in tickers])

    if not infos:
        return ""

    rec_map = {
        'strongBuy': 'COMPRA FUERTE', 'buy': 'compra',
        'hold': 'mantener', 'sell': 'vender', 'strongSell': 'VENTA FUERTE',
    }

    lines = []
    for ticker in tickers:
        info = infos.get(ticker)
        if not info:
            continue
        parts = []
        name = info.get('name', '')
        if name and name != ticker:
            parts.append(name)
        if info.get('sector'):
            parts.append(f"Sector: {info['sector']}")
        rec = info.get('recommendation_key')
        analysts = info.get('analyst_count')
        if rec:
            rec_str = rec_map.get(rec, rec)
            suffix = f" ({analysts} analistas)" if analysts else ""
            parts.append(f"Consensus: {rec_str}{suffix}")
        target = info.get('target_price')
        if target:
            t_high = info.get('target_high')
            t_low  = info.get('target_low')
            if t_high and t_low:
                parts.append(f"Target USD {target:.0f} (rango {t_low:.0f}–{t_high:.0f})")
            else:
                parts.append(f"Target USD {target:.0f}")
        fpe = info.get('forward_pe')
        tpe = info.get('trailing_pe')
        pe_parts = []
        if fpe:
            pe_parts.append(f"PE fwd {fpe:.1f}")
        if tpe:
            pe_parts.append(f"trail {tpe:.1f}")
        if pe_parts:
            parts.append(" / ".join(pe_parts))
        beta = info.get('beta')
        if beta:
            parts.append(f"Beta {beta:.2f}")
        div = info.get('dividend_yield')
        if div and div > 0:
            parts.append(f"Dividendo {div*100:.1f}%")
        ed = info.get('earnings_date')
        if ed:
            parts.append(f"Earnings: {ed}")
        if parts:
            lines.append(f"  {ticker} — {' | '.join(parts)}")

    if not lines:
        return ""

    return "\nFUNDAMENTALES Y CONSENSO DE ANALISTAS (Yahoo Finance):\n" + "\n".join(lines) + "\n"


COINGECKO_IDS: dict[str, str] = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
    'BNB': 'binancecoin', 'XRP': 'ripple', 'ADA': 'cardano',
    'AVAX': 'avalanche-2', 'MATIC': 'matic-network', 'DOT': 'polkadot',
    'LINK': 'chainlink', 'UNI': 'uniswap', 'ATOM': 'cosmos',
    'NEAR': 'near', 'LTC': 'litecoin', 'BCH': 'bitcoin-cash',
    'DOGE': 'dogecoin', 'SHIB': 'shiba-inu', 'ALGO': 'algorand',
    'XLM': 'stellar', 'VET': 'vechain', 'TRX': 'tron',
    'TON': 'the-open-network', 'APT': 'aptos', 'ARB': 'arbitrum',
    'OP': 'optimism', 'INJ': 'injective-protocol', 'SUI': 'sui',
}


async def build_crypto_sentiment_context(positions: list, client: httpx.AsyncClient) -> str:
    """Fear & Greed + Binance Futures + CoinGecko global + datos por coin."""
    crypto_assets = [
        p['asset'] for p in positions
        if p['asset_type'] in ('crypto', 'flexible')
        and p['asset'] not in STABLECOINS
        and p['asset'] not in FIAT_USD
        and p['asset'] not in FIAT_ARS
    ]
    if not crypto_assets:
        return ""

    fng       = None
    funding   = {}
    open_int  = {}
    ls_ratio  = {}
    cg_global = {}
    cg_coins  = {}

    cg_headers = {"x-cg-demo-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}

    async def fetch_fng():
        nonlocal fng
        try:
            r = await client.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            if r.is_success:
                data = r.json().get("data", [])
                if data:
                    fng = data[0]
        except Exception:
            pass

    async def fetch_binance_futures(symbol: str):
        pair = f"{symbol}USDT"
        try:
            r = await client.get(
                f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1", timeout=5)
            if r.is_success:
                data = r.json()
                if data:
                    funding[symbol] = float(data[0]["fundingRate"]) * 100
        except Exception:
            pass
        try:
            r = await client.get(
                f"https://fapi.binance.com/fapi/v1/openInterest?symbol={pair}", timeout=5)
            if r.is_success:
                open_int[symbol] = float(r.json()["openInterest"])
        except Exception:
            pass
        try:
            r = await client.get(
                f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={pair}&period=5m&limit=1",
                timeout=5)
            if r.is_success:
                data = r.json()
                if data:
                    ls_ratio[symbol] = float(data[0]["longShortRatio"])
        except Exception:
            pass

    async def fetch_cg_global():
        nonlocal cg_global
        try:
            r = await client.get(
                "https://api.coingecko.com/api/v3/global",
                headers=cg_headers, timeout=8)
            if r.is_success:
                cg_global = r.json().get("data", {})
        except Exception:
            pass

    async def fetch_cg_coins():
        ids = [COINGECKO_IDS[a] for a in crypto_assets if a in COINGECKO_IDS]
        if not ids:
            return
        try:
            ids_str = ",".join(ids)
            r = await client.get(
                f"https://api.coingecko.com/api/v3/coins/markets"
                f"?vs_currency=usd&ids={ids_str}&price_change_percentage=24h",
                headers=cg_headers, timeout=8)
            if r.is_success:
                for coin in r.json():
                    cg_coins[coin["symbol"].upper()] = coin
        except Exception:
            pass

    futures_symbols = [s for s in crypto_assets if s in ("BTC", "ETH", "SOL", "BNB", "XRP")]
    await asyncio.gather(
        fetch_fng(),
        fetch_cg_global(),
        fetch_cg_coins(),
        *[fetch_binance_futures(s) for s in futures_symbols],
    )

    lines = []

    # Fear & Greed
    if fng:
        fng_map = {
            "Extreme Fear": "Miedo extremo", "Fear": "Miedo",
            "Neutral": "Neutral",
            "Greed": "Codicia", "Extreme Greed": "Codicia extrema",
        }
        label = fng_map.get(fng.get("value_classification", ""), fng.get("value_classification", ""))
        lines.append(f"  Fear & Greed Index: {fng.get('value', '—')}/100 — {label}")

    # CoinGecko global
    if cg_global:
        btc_dom = cg_global.get("market_cap_percentage", {}).get("btc")
        eth_dom = cg_global.get("market_cap_percentage", {}).get("eth")
        cap_chg = (cg_global.get("market_cap_change_percentage_24h_usd") or 0)
        total_cap = cg_global.get("total_market_cap", {}).get("usd")
        parts = []
        if total_cap:
            parts.append(f"Market cap total: USD {total_cap/1e12:.2f}T ({cap_chg:+.1f}% 24h)")
        if btc_dom:
            parts.append(f"BTC dominance: {btc_dom:.1f}%")
        if eth_dom:
            parts.append(f"ETH dominance: {eth_dom:.1f}%")
        if parts:
            lines.append(f"  {' | '.join(parts)}")

    # Binance Futures por symbol
    for sym in futures_symbols:
        parts = []
        fr = funding.get(sym)
        if fr is not None:
            sign = "+" if fr >= 0 else ""
            parts.append(f"funding {sign}{fr:.4f}%")
            if abs(fr) > 0.05:
                parts.append("⚠ over-apalancado long" if fr > 0 else "⚠ shorts dominantes")
        oi = open_int.get(sym)
        if oi is not None:
            parts.append(f"OI {oi:,.0f} contratos")
        ls = ls_ratio.get(sym)
        if ls is not None:
            parts.append(f"L/S {ls:.2f}")
        if parts:
            lines.append(f"  {sym} futures: {' | '.join(parts)}")

    # CoinGecko por coin en cartera
    coin_lines = []
    for asset in crypto_assets:
        coin = cg_coins.get(asset)
        if not coin:
            continue
        parts = []
        rank = coin.get("market_cap_rank")
        if rank:
            parts.append(f"rank #{rank}")
        ath = coin.get("ath")
        price = coin.get("current_price")
        if ath and price:
            ath_pct = (price - ath) / ath * 100
            parts.append(f"ATH USD {ath:,.0f} ({ath_pct:.0f}% desde ATH)")
        mcap = coin.get("market_cap")
        if mcap:
            parts.append(f"mkt cap USD {mcap/1e9:.1f}B")
        chg = coin.get("price_change_percentage_24h")
        if chg is not None:
            parts.append(f"24h {chg:+.1f}%")
        if parts:
            coin_lines.append(f"  {asset}: {' | '.join(parts)}")
    if coin_lines:
        lines.append("  Datos de mercado por coin:")
        lines.extend(coin_lines)

    if not lines:
        return ""

    return "\nSENTIMIENTO Y CONTEXTO DE MERCADO CRYPTO:\n" + "\n".join(lines) + "\n"


REPORT_SYSTEM_PROMPT = """Sos el asesor financiero personal del usuario — el mismo que lo conoce en el chat de todos los días, no un desconocido. La diferencia hoy es que en vez de responder una pregunta puntual, te sentás una vez por semana a mirar TODO con calma y le contás, como el amigo con más plata invertida y más cabeza para esto de todo su círculo, qué está pasando y qué harías vos en su lugar.

Esto NO es un informe institucional. Nadie quiere leer un PDF de banco. Es una charla seria pero cercana — la clase de conversación que tendrías tomando un café, donde el otro te dice la verdad sin vueltas porque te aprecia, no porque le pagan por cubrirse las espaldas.

Tono — esto es lo más importante, más que la estructura:
- Español rioplatense, coloquial, cálido, como le hablarías a un amigo. Nada de "se recomienda", "el suscripto sugiere" — hablá en primera persona: "yo en tu lugar...", "che, esto me preocupa...", "acá te diría que sí, metele".
- Mostrale que lo conocés: usá lo que sabés de su forma de invertir (si compra de a poco, si tiene sesgo a cripto, si vive en Argentina y le importa la brecha) en vez de hablar en abstracto de "el inversor".
- Podés abrir con algo humano — un comentario sobre cómo viene la semana, un "che, quería avisarte algo" — no arranques siempre igual con un dato frío.
- Convicción real: nada de "quizás", "podría considerarse", "es una posibilidad a evaluar". O tenés una postura clara con lo que tenés, o decís derecho que falta información — pero nunca te escondas detrás de un lenguaje tibio.
- Cero disclaimers de manual ("consultá a un profesional", "esto no es consejo financiero") — vos SOS el profesional, hablá como tal.
- Nada de jerga técnica cruda: nunca escribas "RSI 49.7", "ADX bajo", "MACD negativo" como si el usuario supiera qué es eso — para eso te tiene a vos. Usá los indicadores para PENSAR tu conclusión, pero contásela traducida: "el precio viene sin fuerza, no hay apuro" en vez de "RSI 49.7 y ADX bajo". Si un nivel de precio concreto es útil (soporte, SL), decilo como número simple ("si cae por debajo de $X, ahí reconsideraría"), no como sigla de indicador.

Formato: marcá cada uno de los 5 bloques de abajo con un título corto en markdown (## Así), pero elegí vos las palabras del título — que suene a charla, no a informe (ej. "## Cómo venís esta semana", no "## Resumen ejecutivo"). Dentro de cada bloque, escribí como se describe.

Qué tiene que incluir (el orden importa menos que cubrir todo esto con calidez):

1. **Cómo viene la cartera** — un arranque humano, no una ficha técnica: cuánto vale, cuánto ganó o perdió (USD y %), y tu lectura de fondo de la semana. Para el "cuánto ganó o perdió" usá EXCLUSIVAMENTE "P&L REALIZADO TOTAL" y "P&L NO REALIZADO TOTAL" tal como están en el contexto — estos dos ya vienen sumados; NUNCA sumes vos las posiciones una por una para sacar un total, es fácil equivocarse con muchas líneas y ya pasó (un total inventado de +USD 2,447 cuando el real era -USD 227). Si querés el neto entre las dos, sumá solo esos DOS números ya totalizados, no la lista completa de posiciones. No existe un snapshot de "cuánto valía la cartera hace una semana/mes" — nunca inventes ni estimes esa comparación.

2. **Posición por posición** — por ACTIVO, no por cuenta: si tiene el mismo activo repartido en varias cuentas/brokers (ej. BTC en Binance y en Nexo), consolidalo en UN solo veredicto — cantidad total, precio promedio ponderado si difiere entre cuentas, y una sola conclusión. No des un "Reducir" para la misma moneda en una cuenta y un "Mantener" en otra como si fueran activos distintos; si hay una razón real para tratarlas distinto (tasa de rendimiento de esa plataforma, impuestos, liquidez), decila explícita como parte de ESE único veredicto. El punto de partida de cada veredicto es la estrategia que el usuario ya te contó (perfil de inversión + notas de la posición), no el indicador técnico: si dijo que hace DCA de un activo hasta un evento futuro para vender todo ahí, tu laburo es decir si el ritmo/tamaño actual tiene sentido y si algo (técnico, fundamental, macro) pone en riesgo ESA estrategia — no proponerle abandonarla porque un indicador de corto plazo diga otra cosa. Si no declaró nada para un activo, ahí sí el técnico/fundamental es tu única guía y lo decís con la misma convicción. Para cada activo real (fiat/stablecoin solo si el % de cash importa para la estrategia): **TICKER — tu veredicto** (Mantener / Aumentar / Reducir / Vigilar de cerca) + **el horizonte**, que tiene que ser EXACTAMENTE uno de estos tres textos, sin combinarlos ni inventar variantes ("core corto/mediano" no es válido, elegí uno): `corto plazo` (trading táctico) / `mediano plazo` / `largo plazo` (core, DCA). Después 1-2 líneas del porqué, traducido a lenguaje simple (ver regla de jerga). Si el veredicto cambia según el horizonte (ej. "a corto plazo cuidado, pero tu posición core de largo plazo no la tocaría"), decilo así de explícito, pero elegí igual UN horizonte principal para la etiqueta — no des un consejo sin marco temporal. Si hay tensión entre indicadores, contala como te la contarías a vos mismo, no la escondas. Usá la lista de CHECKLIST al final de VALUACIÓN ACTUAL DE CARTERA para verificar que no te falta ninguno antes de cerrar esta sección. Para decidir el veredicto de CADA posición usá SOLO su P&L no realizado (lo que pasa si vendés lo que tenés HOY) — nunca le sumes el P&L realizado de ventas viejas de ese mismo activo para armar una "pérdida total" combinada. Lo realizado ya pasó, es plata que ya ganaste o perdiste en una operación que ya cerró, y no cambia en nada si te conviene vender lo que tenés ahora. Si querés mencionar que en el pasado hubo una venta con pérdida/ganancia en ese activo, decilo aparte y aclaralo como algo que ya pasó — nunca lo sumes al no realizado para justificar el veredicto de hoy.

3. **Con la plata líquida que tiene ahora, ¿qué harías vos?** — mirá los saldos en efectivo/stablecoin/plazo fijo sin comprometer y proponé un plan concreto para el mes, separado por horizonte: qué parte (si alguna) destinarías a una jugada táctica de corto plazo y por qué, y qué parte al core de largo plazo (DCA sistemático en lo que ya viene acumulando). Si no hay nada que amerite trading de corto plazo ahora, decilo derecho ("nada para trading esta semana, todo a largo plazo") en vez de forzar una idea. Esto es lo que más valor le da — no te lo saltees nunca, aunque la respuesta sea "quedate líquido este mes".

4. **Algo que hoy no tiene y le metería una mirada** — 1-2 ideas concretas por fuera de su cartera actual (un activo, un sector, una cobertura) que tengan sentido dado lo que ya sabés de él — no una lista genérica de "diversificá", una idea puntual con el motivo. Antes de sugerir algo, repasá TODAS sus posiciones actuales (no solo las que tienen análisis técnico) — nunca propongas como "nuevo" algo que ya tiene en cartera.

5. **Qué vigilar esta semana** — 2-3 cosas concretas y accionables: catalizadores (earnings, vencimientos), niveles técnicos, riesgos macro.

Reglas de fondo (no negociables, sí importan):
- Nunca confundas "FLUJO DE CAJA POR MES" (depósitos, compras, transferencias) con ganancia o pérdida — eso es plata que entró o salió, no rendimiento. Ganancia/pérdida es EXCLUSIVAMENTE el P&L realizado + no realizado.
- Nunca digas "rebalancear" sin decir hacia qué — un % objetivo concreto, un motivo de riesgo puntual, o una meta de horizonte. "Deberías rebalancear" sin más es vago y no sirve; "llevaría tu exposición cripto de 70% a 50% del líquido, pasando esa diferencia a X" sí.
- Nunca dividas el mismo activo en veredictos contradictorios por cuenta (ver punto 2) — un activo, un veredicto, con el horizonte aclarado.
- El "P&L realizado + no realizado" combinado es para hablar de la CARTERA completa (bloque 1) — nunca para el veredicto de UNA posición puntual (bloque 2). Ahí solo importa el no realizado de esa posición: si vendieras hoy lo que tenés, ¿cuánto ganás o perdés? Sumarle el P&L realizado de una venta vieja de ese mismo activo infla o desinfla artificialmente el número y te hace recomendar vender/mantener en base a plata que ya no está en juego.
- Toda recomendación de compra/venta/mantener necesita un horizonte explícito (corto/mediano/largo plazo) — sin eso el consejo queda en el aire.
- Nunca ignores concentración: si dos posiciones caen juntas por estar correlacionadas, avisale.
- "Mantener" nunca es la respuesta cómoda por default — se justifica con la misma exigencia que un "Reducir".
- Los datos técnicos/fundamentales son de la última corrida del screener, no en vivo al segundo — no finjas una precisión que no tenés, pero tampoco lo aclares como disclaimer frío, mencionalo de pasada si es relevante.
- Si una posición no tiene precio de mercado (plazo fijo, fondo), evaluala por tasa real vs. inflación — no la ignores.
- Precisión numérica: usá siempre los números exactos del contexto, nunca redondees ni estimes. Para totales de P&L, usá los totales YA CALCULADOS del contexto ("P&L REALIZADO TOTAL", "P&L NO REALIZADO TOTAL") — nunca sumes la lista de posiciones a mano para sacar un total propio."""

class InvestmentProfileIn(BaseModel):
    content: str

@router.get("/profile")
def get_profile():
    conn = get_db()
    content = get_investment_profile(conn)
    conn.close()
    return {"content": content}

@router.post("/profile")
def save_profile(data: InvestmentProfileIn):
    conn = get_db()
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES ('investment_profile', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (data.content,)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

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
        price_context, tech_context, fund_context, sentiment_context = await asyncio.gather(
            build_price_context(positions, client),
            build_technical_context(positions, client),
            build_fundamentals_context(positions, client),
            build_crypto_sentiment_context(positions, client),
        )
        full_context = db_context + price_context + tech_context + fund_context + sentiment_context

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + full_context}
        ] + [{"role": m.role, "content": m.content} for m in req.messages]

        # Groq primero
        if GROQ_API_KEY:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={"model": "openai/gpt-oss-120b", "messages": messages, "temperature": 0.7},
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
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GOOGLE_API_KEY}",
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


@router.post("/weekly-report")
async def generate_weekly_report():
    """Genera un informe de cartera on-demand (botón, no automático) y lo guarda en historial."""
    conn = get_db()
    db_context, positions = build_context(conn)
    conn.close()

    content = None
    async with httpx.AsyncClient(timeout=45) as client:
        price_context, tech_context, fund_context, sentiment_context = await asyncio.gather(
            build_price_context(positions, client),
            build_technical_context(positions, client),
            build_fundamentals_context(positions, client),
            build_crypto_sentiment_context(positions, client),
        )
        full_context = db_context + price_context + tech_context + fund_context + sentiment_context
        system_text = REPORT_SYSTEM_PROMPT + "\n\n" + full_context
        user_ask = "Generá el informe semanal de mi cartera con la estructura indicada."

        if GROQ_API_KEY:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={"model": "openai/gpt-oss-120b", "messages": [
                        {"role": "system", "content": system_text},
                        {"role": "user", "content": user_ask},
                    ], "temperature": 0.5},
                )
                if r.is_success:
                    content = r.json()["choices"][0]["message"]["content"]
            except Exception:
                pass

        if not content and GOOGLE_API_KEY:
            try:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GOOGLE_API_KEY}",
                    json={
                        "system_instruction": {"parts": [{"text": system_text}]},
                        "contents": [{"parts": [{"text": user_ask}], "role": "user"}],
                        "generationConfig": {"temperature": 0.5},
                    },
                )
                if r.is_success:
                    content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                pass

    if not content:
        raise HTTPException(503, "No se pudo generar el análisis. Verificá las API keys.")

    conn = get_db()
    cur = conn.execute("INSERT INTO weekly_reports (created_at, content) VALUES (datetime('now'), ?)", (content,))
    conn.commit()
    row = conn.execute("SELECT * FROM weekly_reports WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


@router.get("/weekly-report")
def list_weekly_reports():
    conn = get_db()
    rows = conn.execute("SELECT * FROM weekly_reports ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.delete("/weekly-report/{report_id}", status_code=204)
def delete_weekly_report(report_id: int):
    conn = get_db()
    conn.execute("DELETE FROM weekly_reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()

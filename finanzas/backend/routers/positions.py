import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

MAXIMOS_URL = os.getenv("MAXIMOS_URL", "https://maximos-worker.luchotour.workers.dev")

router = APIRouter(prefix="/api/positions", tags=["positions"])

class PositionIn(BaseModel):
    account_id: int
    asset: str          # ARS, USD, BTC, AAPL, USDT, etc.
    asset_type: str     # fiat | crypto | stablecoin | stock | cedear | cedear_usd | fixed_term | fund | flexible
    quantity: float
    avg_price: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rate: Optional[float] = None
    auto_renew: Optional[int] = 0
    notes: Optional[str] = None

class PositionUpdate(BaseModel):
    asset: Optional[str] = None
    asset_type: Optional[str] = None
    quantity: Optional[float] = None
    avg_price: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rate: Optional[float] = None
    auto_renew: Optional[int] = None
    notes: Optional[str] = None

@router.get("")
def list_positions(account_id: Optional[int] = None):
    conn = get_db()
    if account_id:
        rows = conn.execute(
            "SELECT p.*, a.name as account_name, a.color FROM positions p JOIN accounts a ON p.account_id = a.id WHERE p.account_id = ? ORDER BY p.asset",
            (account_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, a.name as account_name, a.color FROM positions p JOIN accounts a ON p.account_id = a.id ORDER BY a.name, p.asset"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _update_opening_balance(conn, account_id: int, asset: str, target_qty: float, target_avg_price: float = None):
    """Ancla quantity (y, si se pasa, avg_price) para que _sync_position reproduzca
    exactamente lo que el usuario puso en Portfolio, aunque después se carguen más
    movimientos — Portfolio manda, no se deja que un movimiento nuevo lo pise.

    La cantidad se ancla con una transacción sintética 'opening_balance' que tapa
    el hueco entre lo que las transacciones reales explican y lo que el usuario puso
    (igual que antes). El precio promedio es distinto: si ya existe una compra real
    sin precio cargado (típico — se anota "tengo esto" sin el precio exacto), se le
    RELLENA el precio a esa transacción en vez de inventar una fila nueva — porque si
    la cantidad ya está 100% explicada por transacciones reales, no queda ningún
    "hueco" de cantidad donde anclar un precio con una fila sintética."""
    income_excl = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account_id=? AND currency=? AND type IN ('income','buy') AND source!='opening_balance'",
        (account_id, asset)
    ).fetchone()['t']
    expense_total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account_id=? AND currency=? AND type NOT IN ('income','buy') AND source!='opening_balance'",
        (account_id, asset)
    ).fetchone()['t']
    # Positivo: los movimientos reales explican MENOS que lo que el usuario puso (falta
    # sumar) — típico si depositó algo sin cargarlo. Negativo: los movimientos reales
    # explican MÁS de lo que el usuario puso (falta restar) — típico si gastó algo (el
    # almacén, comisiones, lo que sea) sin cargarlo. Las dos direcciones son igual de
    # comunes y las dos tienen que anclarse — antes solo se anclaba la primera.
    opening_amount = round(target_qty - (income_excl - expense_total), 8)

    existing = conn.execute(
        "SELECT id FROM transactions WHERE account_id=? AND currency=? AND source='opening_balance'",
        (account_id, asset)
    ).fetchone()

    from datetime import date as _date
    today = _date.today().isoformat()
    opening_type = 'income' if opening_amount > 0 else 'expense'
    opening_abs = abs(opening_amount)
    if existing:
        if opening_abs > 0:
            conn.execute("UPDATE transactions SET amount=?, type=? WHERE id=?",
                         (opening_abs, opening_type, existing['id']))
        else:
            conn.execute("DELETE FROM transactions WHERE id=?", (existing['id'],))
            existing = None
    elif opening_abs > 0:
        cur = conn.execute(
            "INSERT INTO transactions (account_id, date, description, amount, currency, type, source) VALUES (?,?,?,?,?,?,?)",
            (account_id, today, 'Saldo inicial', opening_abs, asset, opening_type, 'opening_balance')
        )
        existing = {'id': cur.lastrowid}

    if target_avg_price is None:
        return

    # Costo de compras reales ya precificadas por el usuario (nunca se tocan) — lo que falta
    # cubrir para llegar al costo total pedido se reparte entre las filas "rellenables": la
    # sintética de arriba (si quedó con cantidad > 0), cualquier compra real sin precio, y
    # cualquier fila que ESTA MISMA función haya rellenado antes (marcada source='avg_price_anchor')
    # — así una segunda edición del promedio en Portfolio puede corregir lo que rellenó la
    # primera, en vez de quedar pegada para siempre. Nunca una transferencia — esa ya tiene su
    # propio mecanismo de costo heredado.
    priced_cost = conn.execute(
        "SELECT COALESCE(SUM(amount*unit_price),0) as c FROM transactions "
        "WHERE account_id=? AND currency=? AND type IN ('income','buy') "
        "AND source NOT IN ('opening_balance','avg_price_anchor') "
        "AND unit_price IS NOT NULL AND unit_price > 0",
        (account_id, asset)
    ).fetchone()['c']
    fillable_rows = conn.execute(
        "SELECT id, amount FROM transactions WHERE account_id=? AND currency=? AND type IN ('income','buy') "
        "AND source NOT IN ('opening_balance','transfer') "
        "AND (unit_price IS NULL OR unit_price <= 0 OR source='avg_price_anchor')",
        (account_id, asset)
    ).fetchall()

    fillable_qty = sum(r['amount'] for r in fillable_rows)
    if existing and opening_amount > 0:
        fillable_qty += opening_amount

    if fillable_qty <= 0:
        return  # nada anclable con transacciones — el avg_price queda solo en la posición,
                # puede no sobrevivir si se agrega una transacción con precio más adelante

    fill_price = round((target_avg_price * target_qty - priced_cost) / fillable_qty, 8)
    for r in fillable_rows:
        conn.execute("UPDATE transactions SET unit_price=?, source='avg_price_anchor' WHERE id=?", (fill_price, r['id']))
    if existing and opening_amount > 0:
        conn.execute("UPDATE transactions SET unit_price=? WHERE id=?", (fill_price, existing['id']))


@router.post("", status_code=201)
def create_position(data: PositionIn):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO positions (account_id, asset, asset_type, quantity, avg_price, start_date, end_date, rate, auto_renew, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data.account_id, data.asset.upper(), data.asset_type, data.quantity, data.avg_price,
         data.start_date, data.end_date, data.rate, data.auto_renew, data.notes)
    )
    if data.asset_type not in ('fixed_term', 'fund') and data.quantity > 0:
        _update_opening_balance(conn, data.account_id, data.asset.upper(), data.quantity, data.avg_price)
    conn.commit()
    row = conn.execute("SELECT * FROM positions WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@router.patch("/{position_id}")
def update_position(position_id: int, data: PositionUpdate):
    conn = get_db()
    current = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
    if not current:
        conn.close()
        raise HTTPException(404, "Position not found")
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    if "asset" in fields:
        fields["asset"] = fields["asset"].upper()
    sets = ", ".join(f"{k} = ?" for k in fields)
    sets += ", updated_at = datetime('now')"
    values = list(fields.values())
    conn.execute(f"UPDATE positions SET {sets} WHERE id = ?", (*values, position_id))
    # Si cambió quantity y/o avg_price, ajustar el saldo inicial para anclar ambos —
    # así lo que se corrige acá (Portfolio manda) sobrevive a que se carguen más
    # movimientos después, en vez de que _sync_position lo recalcule y lo pise.
    asset_type = fields.get('asset_type', current['asset_type'])
    if ('quantity' in fields or 'avg_price' in fields) and asset_type not in ('fixed_term', 'fund'):
        asset = fields.get('asset', current['asset']).upper()
        new_qty = fields.get('quantity', current['quantity'])
        new_avg = fields.get('avg_price', current['avg_price'])
        _update_opening_balance(conn, current['account_id'], asset, new_qty, new_avg)
    conn.commit()
    row = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
    conn.close()
    return dict(row)

@router.delete("/{position_id}", status_code=204)
def delete_position(position_id: int):
    conn = get_db()
    conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))
    conn.commit()
    conn.close()

FIAT_ASSETS       = {'ARS', 'USD', 'EUR', 'BRL', 'UYU'}
STABLECOIN_ASSETS = {'USDT', 'USDC', 'DAI', 'BUSD', 'FDUSD', 'TUSD', 'PYUSD'}

def _is_binance_tradable(asset: str) -> bool:
    """Chequea si el ticker tiene un par activo contra USDT en Binance spot. Se usa ANTES de
    confiar en _looks_like_real_stock: en modo local, /api/quotes de maximos llama a yfinance
    sin restricción y puede devolver "precio encontrado" para símbolos cripto reales que
    casualmente también resuelven en Yahoo Finance (visto en vivo: BTC y XRP daban positivo
    como "acción real" en modo local) — si Binance lo reconoce como cripto, gana eso siempre."""
    try:
        r = httpx.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": f"{asset}USDT"}, timeout=3)
        return r.is_success and "price" in r.json()
    except Exception:
        return False

def _looks_like_real_stock(asset: str) -> bool:
    """Consulta a maximos si el ticker tiene cotización real de acción/ETF (S&P 500, Nasdaq
    100, ETFs, ADRs — lo que devuelve /api/quotes). Se usa para no asumir 'crypto' a ciegas en
    cuentas exchange: plataformas como Nexo ahora también dejan comprar acciones fraccionadas
    reales, no solo cripto. Si maximos no responde, no reconoce el ticker, o Binance ya lo
    reconoce como cripto, devuelve False — nunca bloquea la creación de la posición, solo se
    pierde la adivinanza inteligente."""
    if _is_binance_tradable(asset):
        return False
    try:
        r = httpx.get(f"{MAXIMOS_URL}/api/quotes", params={"tickers": asset}, timeout=3)
        if r.is_success:
            quotes = r.json().get("quotes", {})
            return quotes.get(asset, {}).get("price") is not None
    except Exception:
        pass
    return False

def guess_asset_type(asset: str, account_type: str = None) -> str:
    a = asset.upper()
    if a in FIAT_ASSETS:       return 'fiat'
    if a in STABLECOIN_ASSETS: return 'stablecoin'
    if account_type in ('exchange', 'wallet_crypto'):
        # Antes se asumía cripto siempre para cuentas exchange — pero plataformas como Nexo
        # ahora también permiten comprar acciones fraccionadas reales (ej. SPY, AAPL). Si
        # maximos reconoce el ticker como una acción/ETF real, se prioriza eso sobre cripto.
        if _looks_like_real_stock(a):
            return 'stock'
        return 'crypto'
    if account_type == 'broker': return 'cedear'
    return 'crypto'

@router.post("/create-missing/{account_id}")
def create_missing_positions(account_id: int):
    """Solo crea posiciones que no existen — no toca las existentes."""
    conn = get_db()
    account = conn.execute("SELECT type FROM accounts WHERE id = ?", (account_id,)).fetchone()
    account_type = account['type'] if account else None
    rows = conn.execute("""
        SELECT currency AS asset,
               SUM(CASE WHEN type='income' THEN amount ELSE -amount END) AS quantity
        FROM transactions
        WHERE account_id = ?
        GROUP BY currency
    """, (account_id,)).fetchall()

    created = 0
    for row in rows:
        asset    = row['asset'].upper()
        quantity = round(row['quantity'], 8)
        if quantity <= 0:
            continue
        existing = conn.execute(
            "SELECT id FROM positions WHERE account_id = ? AND asset = ? AND (end_date IS NULL OR end_date = '')",
            (account_id, asset)
        ).fetchone()
        if not existing:
            asset_type = guess_asset_type(asset, account_type)
            conn.execute(
                "INSERT INTO positions (account_id, asset, asset_type, quantity) VALUES (?, ?, ?, ?)",
                (account_id, asset, asset_type, quantity)
            )
            created += 1

    conn.commit()
    conn.close()
    return {"created": created}

@router.post("/sync/{account_id}")
def sync_positions(account_id: int):
    from routers.transactions import _sync_position
    conn = get_db()
    assets = conn.execute(
        "SELECT DISTINCT currency FROM transactions WHERE account_id = ?",
        (account_id,)
    ).fetchall()
    for row in assets:
        _sync_position(conn, account_id, row['currency'].upper())
    conn.commit()
    conn.close()
    return {"synced": len(assets)}

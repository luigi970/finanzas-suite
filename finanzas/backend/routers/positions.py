from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter(prefix="/api/positions", tags=["positions"])

class PositionIn(BaseModel):
    account_id: int
    asset: str          # ARS, USD, BTC, AAPL, USDT, etc.
    asset_type: str     # fiat | crypto | stablecoin | stock | cedear | fixed_term | fund
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

def _update_opening_balance(conn, account_id: int, asset: str, target_qty: float):
    """Crea o ajusta la transacción 'opening_balance' de forma que _sync_position
    produzca exactamente target_qty para este account/asset."""
    income_excl = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account_id=? AND currency=? AND type IN ('income','buy') AND source!='opening_balance'",
        (account_id, asset)
    ).fetchone()['t']
    expense_total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as t FROM transactions WHERE account_id=? AND currency=? AND type NOT IN ('income','buy')",
        (account_id, asset)
    ).fetchone()['t']
    opening_amount = round(target_qty - (income_excl - expense_total), 8)

    existing = conn.execute(
        "SELECT id FROM transactions WHERE account_id=? AND currency=? AND source='opening_balance'",
        (account_id, asset)
    ).fetchone()

    from datetime import date as _date
    today = _date.today().isoformat()
    if existing:
        if opening_amount > 0:
            conn.execute("UPDATE transactions SET amount=? WHERE id=?", (opening_amount, existing['id']))
        else:
            conn.execute("DELETE FROM transactions WHERE id=?", (existing['id'],))
    elif opening_amount > 0:
        conn.execute(
            "INSERT INTO transactions (account_id, date, description, amount, currency, type, source) VALUES (?,?,?,?,?,?,?)",
            (account_id, today, 'Saldo inicial', opening_amount, asset, 'income', 'opening_balance')
        )


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
        _update_opening_balance(conn, data.account_id, data.asset.upper(), data.quantity)
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
    # Si cambió la quantity, ajustar el saldo inicial
    new_qty = fields.get('quantity')
    asset_type = fields.get('asset_type', current['asset_type'])
    if new_qty is not None and asset_type not in ('fixed_term', 'fund'):
        asset = fields.get('asset', current['asset']).upper()
        _update_opening_balance(conn, current['account_id'], asset, new_qty)
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

def guess_asset_type(asset: str, account_type: str = None) -> str:
    a = asset.upper()
    if a in FIAT_ASSETS:       return 'fiat'
    if a in STABLECOIN_ASSETS: return 'stablecoin'
    if account_type in ('exchange', 'wallet_crypto'): return 'crypto'
    if account_type == 'broker': return 'stock'
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

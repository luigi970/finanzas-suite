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

@router.post("", status_code=201)
def create_position(data: PositionIn):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO positions (account_id, asset, asset_type, quantity, avg_price, start_date, end_date, rate, auto_renew, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data.account_id, data.asset.upper(), data.asset_type, data.quantity, data.avg_price,
         data.start_date, data.end_date, data.rate, data.auto_renew, data.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM positions WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@router.patch("/{position_id}")
def update_position(position_id: int, data: PositionUpdate):
    conn = get_db()
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    if "asset" in fields:
        fields["asset"] = fields["asset"].upper()
    fields["updated_at"] = "datetime('now')"
    sets = ", ".join(f"{k} = ?" for k in fields if k != "updated_at")
    sets += ", updated_at = datetime('now')"
    values = [v for k, v in fields.items() if k != "updated_at"]
    conn.execute(f"UPDATE positions SET {sets} WHERE id = ?", (*values, position_id))
    conn.commit()
    row = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Position not found")
    return dict(row)

@router.delete("/{position_id}", status_code=204)
def delete_position(position_id: int):
    conn = get_db()
    conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))
    conn.commit()
    conn.close()

FIAT_ASSETS       = {'ARS', 'USD', 'EUR', 'BRL', 'UYU'}
STABLECOIN_ASSETS = {'USDT', 'USDC', 'DAI', 'BUSD', 'FDUSD', 'TUSD', 'PYUSD'}

def guess_asset_type(asset: str) -> str:
    a = asset.upper()
    if a in FIAT_ASSETS:       return 'fiat'
    if a in STABLECOIN_ASSETS: return 'stablecoin'
    return 'crypto'

@router.post("/create-missing/{account_id}")
def create_missing_positions(account_id: int):
    """Solo crea posiciones que no existen — no toca las existentes."""
    conn = get_db()
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
            asset_type = guess_asset_type(asset)
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

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

FIAT_CURRENCIES = {'ARS', 'USD', 'EUR', 'BRL', 'UYU'}

class TransactionIn(BaseModel):
    account_id: int
    date: str
    description: Optional[str] = None
    amount: float
    currency: str
    type: str           # income | expense | transfer
    category: Optional[str] = None
    source: Optional[str] = "manual"
    unit_price: Optional[float] = None

class TransactionItem(BaseModel):
    date: str
    description: Optional[str] = None
    amount: float
    currency: str
    type: str
    category: Optional[str] = None
    source: Optional[str] = "manual"

class TransactionBatch(BaseModel):
    account_id: int
    transactions: list[TransactionItem]

class TransactionUpdate(BaseModel):
    date: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None


def _apply_unit_price(conn, account_id: int, currency: str, tx_type: str, amount: float, unit_price: float):
    """Update avg_price on income; calculate and return realized_pnl on expense."""
    asset = currency.upper()
    if asset in FIAT_CURRENCIES or unit_price <= 0:
        return None

    pos = conn.execute(
        "SELECT id, quantity, avg_price FROM positions WHERE account_id = ? AND asset = ? AND end_date IS NULL",
        (account_id, asset)
    ).fetchone()

    realized_pnl = None

    if tx_type == 'income':
        if pos:
            old_qty = pos['quantity'] or 0
            old_avg = pos['avg_price'] or unit_price
            new_total_qty = old_qty + amount
            new_avg = (old_qty * old_avg + amount * unit_price) / new_total_qty if new_total_qty > 0 else unit_price
            conn.execute(
                "UPDATE positions SET avg_price = ?, updated_at = datetime('now') WHERE id = ?",
                (round(new_avg, 8), pos['id'])
            )
        # If no position yet, it will be created manually or via sync — avg_price will be set then

    elif tx_type == 'expense':
        if pos and pos['avg_price'] is not None:
            realized_pnl = round((unit_price - pos['avg_price']) * amount, 2)

    return realized_pnl


@router.get("")
def list_transactions(account_id: Optional[int] = None, limit: int = 200):
    conn = get_db()
    if account_id:
        rows = conn.execute(
            "SELECT t.*, a.name as account_name FROM transactions t JOIN accounts a ON t.account_id = a.id WHERE t.account_id = ? ORDER BY t.date DESC LIMIT ?",
            (account_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.*, a.name as account_name FROM transactions t JOIN accounts a ON t.account_id = a.id ORDER BY t.date DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("", status_code=201)
def create_transaction(data: TransactionIn):
    conn = get_db()
    realized_pnl = None
    if data.unit_price and data.type in ('income', 'expense'):
        realized_pnl = _apply_unit_price(conn, data.account_id, data.currency, data.type, data.amount, data.unit_price)
    cur = conn.execute(
        "INSERT INTO transactions (account_id, date, description, amount, currency, type, category, source, unit_price, realized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data.account_id, data.date, data.description, data.amount, data.currency.upper(), data.type, data.category, data.source, data.unit_price, realized_pnl)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@router.post("/batch", status_code=201)
def create_transactions_batch(data: TransactionBatch):
    conn = get_db()
    inserted = []
    for t in data.transactions:
        cur = conn.execute(
            "INSERT INTO transactions (account_id, date, description, amount, currency, type, category, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data.account_id, t.date, t.description, t.amount, t.currency.upper(), t.type, t.category, t.source or "manual")
        )
        inserted.append(cur.lastrowid)
    conn.commit()
    conn.close()
    return {"inserted": len(inserted), "ids": inserted}

@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()

@router.patch("/{transaction_id}")
def update_transaction(transaction_id: int, data: TransactionUpdate):
    conn = get_db()
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    if "currency" in fields:
        fields["currency"] = fields["currency"].upper()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    conn.execute(f"UPDATE transactions SET {sets} WHERE id = ?", (*values, transaction_id))
    conn.commit()
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Transaction not found")
    return dict(row)

@router.get("/summary")
def summary(account_id: Optional[int] = None):
    conn = get_db()
    base = "WHERE 1=1"
    params = []
    if account_id:
        base += " AND account_id = ?"
        params.append(account_id)

    by_month = conn.execute(f"""
        SELECT strftime('%Y-%m', date) as month,
               currency,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
        FROM transactions {base}
        GROUP BY month, currency
        ORDER BY month DESC
    """, params).fetchall()

    by_category = conn.execute(f"""
        SELECT category, currency,
               SUM(amount) as total,
               COUNT(*) as count
        FROM transactions {base} AND type='expense' AND category IS NOT NULL
        GROUP BY category, currency
        ORDER BY total DESC
    """, params).fetchall()

    realized = conn.execute(f"""
        SELECT currency,
               SUM(realized_pnl) as total_realized
        FROM transactions {base} AND realized_pnl IS NOT NULL
        GROUP BY currency
    """, params).fetchall()

    conn.close()
    return {
        "by_month": [dict(r) for r in by_month],
        "by_category": [dict(r) for r in by_category],
        "realized_pnl": [dict(r) for r in realized],
    }

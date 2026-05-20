from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

class TransactionIn(BaseModel):
    account_id: int
    date: str
    description: Optional[str] = None
    amount: float
    currency: str
    type: str           # income | expense | transfer
    category: Optional[str] = None
    source: Optional[str] = "manual"

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
    cur = conn.execute(
        "INSERT INTO transactions (account_id, date, description, amount, currency, type, category, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (data.account_id, data.date, data.description, data.amount, data.currency.upper(), data.type, data.category, data.source)
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

    conn.close()
    return {
        "by_month": [dict(r) for r in by_month],
        "by_category": [dict(r) for r in by_category],
    }

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

class AccountIn(BaseModel):
    name: str
    type: str   # bank | crypto | broker | cash | other
    color: Optional[str] = "#6366f1"

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    color: Optional[str] = None
    active: Optional[int] = None

@router.get("")
def list_accounts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM accounts ORDER BY active DESC, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("", status_code=201)
def create_account(data: AccountIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO accounts (name, type, color) VALUES (?, ?, ?)",
        (data.name, data.type, data.color)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@router.patch("/{account_id}")
def update_account(account_id: int, data: AccountUpdate):
    conn = get_db()
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE accounts SET {sets} WHERE id = ?", (*fields.values(), account_id))
    conn.commit()
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Account not found")
    return dict(row)

@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int):
    conn = get_db()
    conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()

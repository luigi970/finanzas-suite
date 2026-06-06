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
    fee: Optional[float] = None
    fee_currency: Optional[str] = None

VALID_TYPES = {'income', 'expense', 'transfer'}

class TransactionItem(BaseModel):
    date: str
    description: Optional[str] = None
    amount: float
    currency: str
    type: str
    category: Optional[str] = None
    source: Optional[str] = "manual"
    unit_price: Optional[float] = None
    fee: Optional[float] = None
    fee_currency: Optional[str] = None

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
    fee: Optional[float] = None
    fee_currency: Optional[str] = None


def _calc_realized_pnl(conn, account_id: int, asset: str, unit_price: float, amount: float):
    """Calcula P&L realizado para un egreso usando el avg_price actual de la posición."""
    if asset in FIAT_CURRENCIES or not unit_price or unit_price <= 0:
        return None
    pos = conn.execute(
        "SELECT avg_price FROM positions WHERE account_id = ? AND asset = ? AND (end_date IS NULL OR end_date = '')",
        (account_id, asset)
    ).fetchone()
    if pos and pos['avg_price']:
        return round((unit_price - pos['avg_price']) * amount, 2)
    return None


def _sync_position(conn, account_id: int, asset: str):
    """Recalcula quantity y avg_price de la posición desde todos los movimientos."""
    from routers.positions import guess_asset_type

    qty_row = conn.execute("""
        SELECT SUM(CASE WHEN type='income' THEN amount ELSE -amount END) as qty
        FROM transactions WHERE account_id = ? AND currency = ?
    """, (account_id, asset)).fetchone()
    qty = round(qty_row['qty'] or 0, 8)

    # Restar lo que ya está asignado a posiciones manuales (plazo fijo / fondo)
    # que tienen fecha de vencimiento futura — esas no las toca _sync_position
    manual_row = conn.execute("""
        SELECT COALESCE(SUM(quantity), 0) as manual_qty
        FROM positions
        WHERE account_id = ? AND asset = ?
          AND asset_type IN ('fixed_term', 'fund')
          AND end_date IS NOT NULL AND end_date != '' AND end_date > date('now')
    """, (account_id, asset)).fetchone()
    qty = round(qty - (manual_row['manual_qty'] or 0), 8)

    # Calcular avg_price solo desde compras reales (con unit_price).
    # Las transferencias (sin unit_price) no cuentan como compras — no modifican el costo promedio.
    # Si no hay ninguna compra con precio, preservar el avg_price actual (puede ser manual).
    buys_row = conn.execute("""
        SELECT COUNT(*) as cnt FROM transactions
        WHERE account_id = ? AND currency = ? AND type = 'income'
          AND unit_price IS NOT NULL AND unit_price > 0
    """, (account_id, asset)).fetchone()

    if buys_row['cnt'] > 0:
        avg_row = conn.execute("""
            SELECT SUM(amount * unit_price) / NULLIF(SUM(amount), 0) as avg_price
            FROM transactions
            WHERE account_id = ? AND currency = ? AND type = 'income'
              AND unit_price IS NOT NULL AND unit_price > 0
        """, (account_id, asset)).fetchone()
        avg_price = round(float(avg_row['avg_price']), 8) if avg_row and avg_row['avg_price'] else None
    else:
        avg_price = None  # preserva el avg_price manual si no hay compras con precio

    pos = conn.execute(
        "SELECT id FROM positions WHERE account_id = ? AND asset = ? AND (end_date IS NULL OR end_date = '')",
        (account_id, asset)
    ).fetchone()

    if pos:
        if avg_price is not None:
            conn.execute(
                "UPDATE positions SET quantity = ?, avg_price = ?, updated_at = datetime('now') WHERE id = ?",
                (qty, avg_price, pos['id'])
            )
        else:
            conn.execute(
                "UPDATE positions SET quantity = ?, updated_at = datetime('now') WHERE id = ?",
                (qty, pos['id'])
            )
    elif qty > 0:
        conn.execute(
            "INSERT INTO positions (account_id, asset, asset_type, quantity, avg_price) VALUES (?, ?, ?, ?, ?)",
            (account_id, asset, guess_asset_type(asset), qty, avg_price)
        )


@router.get("/export")
def export_transactions(account_id: Optional[int] = None):
    from fastapi.responses import StreamingResponse
    import csv, io
    conn = get_db()
    params = []
    where = "WHERE 1=1"
    if account_id:
        where += " AND t.account_id = ?"
        params.append(account_id)
    rows = conn.execute(
        f"SELECT t.date, a.name as account_name, t.description, t.amount, t.currency, t.type, t.category, t.unit_price, t.realized_pnl, t.fee, t.fee_currency, t.source FROM transactions t JOIN accounts a ON t.account_id = a.id {where} ORDER BY t.date DESC",
        params
    ).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['fecha', 'cuenta', 'descripcion', 'monto', 'moneda', 'tipo', 'categoria', 'precio_unit', 'pnl_realizado', 'comision', 'moneda_comision', 'fuente'])
    for r in rows:
        writer.writerow([r['date'], r['account_name'], r['description'] or '', r['amount'], r['currency'], r['type'], r['category'] or '', r['unit_price'] or '', r['realized_pnl'] or '', r['fee'] or '', r['fee_currency'] or '', r['source'] or ''])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=movimientos.csv"})

@router.get("")
def list_transactions(account_id: Optional[int] = None, limit: int = 500):
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
    asset = data.currency.upper()
    realized_pnl = None
    if data.unit_price and data.type == 'expense':
        realized_pnl = _calc_realized_pnl(conn, data.account_id, asset, data.unit_price, data.amount)
    fee_currency = data.fee_currency.upper() if data.fee_currency else None
    cur = conn.execute(
        "INSERT INTO transactions (account_id, date, description, amount, currency, type, category, source, unit_price, realized_pnl, fee, fee_currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data.account_id, data.date, data.description, data.amount, asset, data.type, data.category, data.source, data.unit_price, realized_pnl, data.fee, fee_currency)
    )
    conn.commit()
    _sync_position(conn, data.account_id, asset)
    conn.commit()
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

import re as _re
_DATE_RE = _re.compile(r'^\d{4}-\d{2}-\d{2}$')

def _sanitize_date(d):
    from datetime import date
    if d and _DATE_RE.match(str(d)):
        return d
    return date.today().isoformat()

@router.post("/batch", status_code=201)
def create_transactions_batch(data: TransactionBatch):
    conn = get_db()
    inserted = []
    for t in data.transactions:
        tx_type = t.type if t.type in VALID_TYPES else 'expense'
        currency = t.currency.upper()
        fee_currency = t.fee_currency.upper() if t.fee_currency else None
        tx_date = _sanitize_date(t.date)
        realized_pnl = None
        if t.unit_price and tx_type == 'expense':
            realized_pnl = _calc_realized_pnl(conn, data.account_id, currency, t.unit_price, t.amount)
        cur = conn.execute(
            "INSERT INTO transactions (account_id, date, description, amount, currency, type, category, source, unit_price, realized_pnl, fee, fee_currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (data.account_id, tx_date, t.description, t.amount, currency, tx_type, t.category, t.source or "manual", t.unit_price, realized_pnl, t.fee, fee_currency)
        )
        inserted.append(cur.lastrowid)
    conn.commit()

    # Recalcular posiciones (qty y avg_price) desde todos los movimientos
    currencies = {t.currency.upper() for t in data.transactions}
    for asset in currencies:
        _sync_position(conn, data.account_id, asset)
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
    if "fee_currency" in fields and fields["fee_currency"]:
        fields["fee_currency"] = fields["fee_currency"].upper()

    existing = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "Transaction not found")
    tx = dict(existing)

    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    conn.execute(f"UPDATE transactions SET {sets} WHERE id = ?", (*values, transaction_id))
    conn.commit()

    # Resync posición afectada
    account_id = tx.get("account_id")
    asset = fields.get("currency", tx.get("currency", "")).upper()
    if account_id and asset:
        _sync_position(conn, account_id, asset)
        conn.commit()

    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
    conn.close()
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

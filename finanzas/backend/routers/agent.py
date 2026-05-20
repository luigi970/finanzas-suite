import os, json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import httpx
from database import get_db

router = APIRouter(prefix="/api/agent", tags=["agent"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

SYSTEM_PROMPT = """Sos un asesor financiero personal. Hablás en español rioplatense, tono amigable y directo, como un amigo que sabe de finanzas. Sin jerga técnica innecesaria, sin markdown, texto corrido.

Tenés acceso a los datos financieros reales del usuario. Cuando respondas usá esos datos concretos — montos, fechas, activos específicos. No des consejos genéricos.

Si el usuario tiene plata disponible para invertir y te parece relevante, podés mencionar que puede consultar el screener de mercado (maximos) para ver señales de compra/venta actuales."""

def build_context(conn) -> str:
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

    ctx = "=== DATOS FINANCIEROS DEL USUARIO ===\n\n"

    ctx += "CUENTAS:\n"
    for a in accounts:
        ctx += f"- {a['name']} ({a['type']})\n"

    ctx += "\nPOSICIONES ACTUALES:\n"
    for p in positions:
        line = f"- {p['account_name']}: {p['quantity']} {p['asset']} ({p['asset_type']})"
        if p['end_date']:
            line += f" | vence {p['end_date']}"
            if p['rate']:
                line += f" | tasa {p['rate']}% anual"
        if p['notes']:
            line += f" | {p['notes']}"
        ctx += line + "\n"

    ctx += "\nÚLTIMAS 50 TRANSACCIONES:\n"
    for t in recent_tx:
        sign = "+" if t['type'] == 'income' else "-"
        ctx += f"- {t['date']} | {t['account_name']} | {sign}{t['amount']} {t['currency']} | {t['description'] or ''} | {t['category'] or ''}\n"

    ctx += "\nRESUMEN POR MES:\n"
    for r in summary:
        ctx += f"- {r['month']} {r['currency']}: ingresos {r['income']:.0f}, gastos {r['expense']:.0f}, balance {r['income']-r['expense']:.0f}\n"

    return ctx

class ChatMessage(BaseModel):
    role: str   # user | assistant
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@router.post("/chat")
async def chat(req: ChatRequest):
    conn = get_db()
    context = build_context(conn)
    conn.close()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}
    ] + [{"role": m.role, "content": m.content} for m in req.messages]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7,
            }
        )
        r.raise_for_status()
        reply = r.json()["choices"][0]["message"]["content"]

    return {"reply": reply}

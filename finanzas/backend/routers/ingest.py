import os, base64, json, re, asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

EXTRACTION_PROMPT = """Sos un extractor de transacciones financieras. Dado el siguiente documento bancario o financiero, extraé todas las transacciones que encuentres.

Para cada transacción devolvé un JSON con estos campos:
- date: fecha en formato YYYY-MM-DD (si no hay año usá el año actual)
- description: descripción breve de la operación
- amount: monto como número positivo (la cantidad del activo, no el valor en USD)
- currency: moneda o activo (ARS, USD, USDT, BTC, ETH, etc.)
- type: uno de estos valores:
    "income"   → ingreso, acreditación (el activo entra a la cuenta desde afuera)
    "expense"  → egreso, débito, gasto (el activo sale de la cuenta hacia afuera)
    "buy"      → compra de cripto/acción PAGADA con otro activo propio (ver regla de swap abajo)
    "sell"     → venta de cripto/acción RECIBIENDO otro activo propio (ver regla de swap abajo)
    "transfer" → transferencia entre cuentas propias del mismo usuario
- category: categoría sugerida (sueldo, freelance, inversión, comida, transporte, servicios, alquiler_pagado, alquiler_cobrado, entretenimiento, salud, educación, retiro, comisión, otro)
- unit_price: precio por unidad en USD al momento de la operación (solo para cripto y acciones, null para fiat y stablecoins)
- fee: comisión cobrada como número positivo (null si no hay)
- fee_currency: moneda de la comisión, ej "BNB", "USD" (null si no hay fee)
- source: "swap" SOLO para el caso de intercambio descripto abajo, sino omitilo (o "manual")

Regla clave — INTERCAMBIO / SWAP entre dos activos propios (ej: "comprás BTC pagando con USDT", "cambiás USD por ARS", "vendés ETH y te acreditan USDT" en un exchange): NO es un ingreso ni un gasto aislado, es UN intercambio. Generá SIEMPRE DOS transacciones linkeadas, ambas con la MISMA description (ej: "Swap USDT → BTC") y AMBAS con source="swap":
  1. Una por el activo que se ENTREGA: type="expense" si es fiat/stablecoin, type="sell" si es cripto/acción
  2. Otra por el activo que se RECIBE: type="income" si es fiat/stablecoin, type="buy" si es cripto/acción
  Ejemplo: "Compra de 0.001 BTC pagando 90 USDT" en Binance →
    {"description":"Swap USDT → BTC","amount":90,"currency":"USDT","type":"expense","source":"swap",...}
    {"description":"Swap USDT → BTC","amount":0.001,"currency":"BTC","type":"buy","source":"swap","unit_price":90000,...}
  Si el activo recibido es cripto/acción y no hay precio en USD explícito, calculá unit_price = monto_entregado / monto_recibido
  (USDT y USD valen 1:1, así que ese cálculo ya da el precio en USD). Si el activo pagado no es USD/USDT, dejá unit_price null.
  NUNCA registres solo un lado del intercambio — el saldo del activo entregado queda mal si falta esa transacción.

Reglas importantes:
- type DEBE ser exactamente "income", "expense", "buy", "sell" o "transfer". Nunca uses otro valor.
- Un ingreso real de dinero externo (sueldo, depósito, transferencia recibida de otra persona): type="income", source="manual"
- Un gasto real hacia afuera (pagaste algo, retiraste plata): type="expense", source="manual"
- Si ves un gasto en ARS/USD que NO es parte de un swap: type="expense", unit_price=null

Devolvé SOLO un JSON válido con esta estructura:
{"transactions": [...]}

Sin explicaciones, sin markdown, solo el JSON.

"""

def extract_json(text: str) -> dict:
    text = text.strip()
    # Strip thinking blocks (Qwen, DeepSeek, etc.) — tomar todo lo que viene después
    if "</think>" in text:
        text = text.split("</think>", 1)[-1].strip()
    elif "<think>" in text:
        # Bloque sin cerrar: descartar todo hasta el primer { fuera del bloque
        text = text[text.rfind("<think>"):]
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No se encontró JSON válido en la respuesta: {text[:200]}")

async def call_groq_text(text: str) -> list:
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(500, "GROQ_API_KEY not configured")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": EXTRACTION_PROMPT + "Documento:\n" + text}],
                "temperature": 0.1,
            }
        )
        if not r.is_success:
            raise HTTPException(500, f"Groq error {r.status_code}: {r.text[:300]}")
        content = r.json()["choices"][0]["message"]["content"]
        return extract_json(content).get("transactions", [])


async def call_groq_vision(image_b64: str, mime: str) -> list:
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(500, "GROQ_API_KEY not configured")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}"},
            json={
                "model": "qwen/qwen3.6-27b",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT + "Analizá la imagen y extraé todas las transacciones visibles."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}
                    ]
                }],
                "temperature": 0.1,
                "reasoning_effort": "none",
            }
        )
        if not r.is_success:
            raise HTTPException(500, f"Groq vision error {r.status_code}: {r.text[:300]}")
        content = r.json()["choices"][0]["message"]["content"]
        return extract_json(content).get("transactions", [])

async def call_gemini_vision(image_b64: str, mime: str) -> list:
    google_key = os.getenv("GOOGLE_API_KEY", "")
    if not google_key:
        raise HTTPException(500, "GOOGLE_API_KEY not configured")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={google_key}",
            json={
                "contents": [{
                    "parts": [
                        {"text": EXTRACTION_PROMPT + "Analizá la imagen adjunta y extraé todas las transacciones visibles."},
                        {"inline_data": {"mime_type": mime, "data": image_b64}}
                    ]
                }],
                "generationConfig": {"temperature": 0.1}
            }
        )
        if not r.is_success:
            raise HTTPException(500, f"Gemini error {r.status_code}: {r.text[:300]}")
        content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return extract_json(content).get("transactions", [])

async def call_vision(image_b64: str, mime: str) -> list:
    # Groq vision primero, Gemini como fallback
    groq_err = None
    try:
        return await call_groq_vision(image_b64, mime)
    except HTTPException as e:
        groq_err = e.detail
    try:
        return await call_gemini_vision(image_b64, mime)
    except HTTPException as e:
        raise HTTPException(500, f"Groq: {groq_err} | Gemini: {e.detail}")

class TextIngest(BaseModel):
    text: str
    account_id: Optional[int] = None

@router.post("/text")
async def ingest_text(data: TextIngest):
    try:
        transactions = await call_groq_text(data.text)
        return {"transactions": transactions, "source": "text"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")

@router.post("/file")
async def ingest_file(file: UploadFile = File(...), account_id: Optional[int] = Form(None)):
    try:
        content = await file.read()
        fname = file.filename.lower()

        if fname.endswith(".csv") or fname.endswith(".txt"):
            text = content.decode("utf-8", errors="replace")
            transactions = await call_groq_text(text)
            return {"transactions": transactions, "source": "csv"}

        if fname.endswith(".pdf"):
            import pypdf, io
            reader = pypdf.PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if not text.strip():
                raise HTTPException(422, "El PDF no tiene texto extraíble. Probá con un screenshot.")
            transactions = await call_groq_text(text)
            return {"transactions": transactions, "source": "pdf"}

        if any(fname.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            mime = "image/jpeg" if ("jpg" in fname or "jpeg" in fname) else f"image/{fname.split('.')[-1]}"
            image_b64 = base64.b64encode(content).decode()
            transactions = await call_vision(image_b64, mime)
            return {"transactions": transactions, "source": "image"}

        raise HTTPException(400, f"Formato no soportado: {fname}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")

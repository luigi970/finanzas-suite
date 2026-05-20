import os, base64, json, re, asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

EXTRACTION_PROMPT = """Sos un extractor de transacciones financieras. Dado el siguiente documento bancario o financiero, extraé todas las transacciones que encuentres.

Para cada transacción devolvé un JSON con estos campos:
- date: fecha en formato YYYY-MM-DD
- description: descripción de la operación
- amount: monto como número positivo
- currency: moneda (ARS, USD, USDT, BTC, etc.)
- type: "income" si es un ingreso/acreditación, "expense" si es un egreso/débito
- category: categoría sugerida (comida, transporte, sueldo, transferencia, retiro, inversión, servicio, entretenimiento, salud, otro)

Devolvé SOLO un JSON válido con esta estructura:
{"transactions": [...]}

Sin explicaciones, sin markdown, solo el JSON.

"""

def extract_json(text: str) -> dict:
    text = text.strip()
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
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT + "Analizá la imagen y extraé todas las transacciones visibles."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}
                    ]
                }],
                "temperature": 0.1,
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
    try:
        return await call_groq_vision(image_b64, mime)
    except HTTPException:
        return await call_gemini_vision(image_b64, mime)

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

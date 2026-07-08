import os, httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from database import get_db

router = APIRouter()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def _extract_text(file_path: str, mime: str) -> str:
    import pdfplumber, base64
    if mime == "application/pdf":
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)[:8000]
    # imagen → Gemini vision
    if not GOOGLE_API_KEY:
        return ""
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GOOGLE_API_KEY}",
            json={"contents": [{"parts": [
                {"text": "Extraé todo el texto fiscal relevante de esta imagen. Incluí todos los números, fechas y conceptos."},
                {"inlineData": {"mimeType": mime, "data": b64}},
            ]}]},
        )
        return r.json()["candidates"][0]["content"]["parts"][0]["text"][:8000]

@router.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    type: str = Form("otro"),
    period: Optional[str] = Form(None),
):
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ("application/pdf", "image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Solo se aceptan PDF, JPG, PNG o WebP")

    dest = os.path.join(UPLOAD_DIR, file.filename)
    with open(dest, "wb") as f:
        f.write(await file.read())

    try:
        text = await _extract_text(dest, content_type)
    except Exception as e:
        text = f"[Error al extraer texto: {e}]"

    db = get_db()
    cursor = db.execute(
        "INSERT INTO documents (name, type, period, content, file_path) VALUES (?,?,?,?,?)",
        (file.filename, type, period, text, dest)
    )
    db.commit()
    doc_id = cursor.lastrowid
    db.close()
    return {"id": doc_id, "name": file.filename, "text_preview": text[:200]}

@router.get("/api/documents")
def list_documents():
    db = get_db()
    rows = db.execute("SELECT id, name, type, period, created_at FROM documents ORDER BY created_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]

@router.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int):
    db = get_db()
    row = db.execute("SELECT file_path FROM documents WHERE id=?", (doc_id,)).fetchone()
    if row and os.path.exists(row["file_path"]):
        os.remove(row["file_path"])
    db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    db.commit()
    db.close()
    return {"ok": True}

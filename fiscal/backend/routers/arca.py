import os, json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from database import get_db

router = APIRouter()

AFIPSDK_TOKEN = os.getenv("AFIPSDK_ACCESS_TOKEN", "")
AFIPSDK_URL   = "https://api.afipsdk.com/v1/automations"

TTL_DAYS = {
    "nuestra-parte":              7,
    "monotributo-info":           7,
    "mis-retenciones":           30,
    "domicilio-fiscal-electronico": 7,
    "ccma":                      30,
    "mis-comprobantes":          30,
    "mis-facilidades":           30,
}

class SyncRequest(BaseModel):
    automation: str
    cuit: str
    password: str
    periodo: Optional[str] = None   # año "2025" o MM/YYYY según automation
    force: Optional[bool] = False   # ignorar cache

async def _call_afipsdk(automation: str, data: dict) -> dict:
    if not AFIPSDK_TOKEN:
        raise HTTPException(503, "AFIPSDK_ACCESS_TOKEN no configurado")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            AFIPSDK_URL,
            headers={"Authorization": f"Bearer {AFIPSDK_TOKEN}"},
            json={"automation": automation, "data": data, "wait": True},
        )
        if r.status_code != 200:
            raise HTTPException(502, f"AFIP SDK error {r.status_code}: {r.text[:300]}")
        return r.json().get("data", r.json())

def _get_cache(automation: str, periodo: Optional[str]) -> Optional[dict]:
    db = get_db()
    row = db.execute(
        "SELECT data, expires_at FROM arca_cache WHERE automation=? AND (periodo=? OR (periodo IS NULL AND ? IS NULL))",
        (automation, periodo, periodo)
    ).fetchone()
    db.close()
    if not row:
        return None
    if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return None
    return json.loads(row["data"])

def _set_cache(automation: str, periodo: Optional[str], data: dict):
    ttl = TTL_DAYS.get(automation, 7)
    expires = (datetime.now() + timedelta(days=ttl)).isoformat()
    db = get_db()
    db.execute("DELETE FROM arca_cache WHERE automation=? AND (periodo=? OR (periodo IS NULL AND ? IS NULL))",
               (automation, periodo, periodo))
    db.execute("INSERT INTO arca_cache (automation, periodo, data, expires_at) VALUES (?,?,?,?)",
               (automation, periodo, json.dumps(data, ensure_ascii=False), expires))
    db.commit()
    db.close()

@router.post("/api/arca/sync")
async def sync_arca(req: SyncRequest):
    if not req.force:
        cached = _get_cache(req.automation, req.periodo)
        if cached:
            return {"source": "cache", "data": cached}

    payload = {"cuit": req.cuit, "username": req.cuit, "password": req.password}
    if req.periodo:
        payload["periodo"] = req.periodo

    data = await _call_afipsdk(req.automation, payload)
    _set_cache(req.automation, req.periodo, data)
    return {"source": "arca", "data": data}

@router.get("/api/arca/cache")
def list_cache():
    db = get_db()
    rows = db.execute("SELECT automation, periodo, fetched_at, expires_at FROM arca_cache ORDER BY fetched_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]

@router.get("/api/arca/cache/{automation}")
def get_cache(automation: str, periodo: Optional[str] = None):
    data = _get_cache(automation, periodo)
    if data is None:
        raise HTTPException(404, "No hay datos en cache para esta automatización")
    return {"automation": automation, "periodo": periodo, "data": data}

@router.delete("/api/arca/cache/{automation}")
def clear_cache(automation: str):
    db = get_db()
    db.execute("DELETE FROM arca_cache WHERE automation=?", (automation,))
    db.commit()
    db.close()
    return {"ok": True}

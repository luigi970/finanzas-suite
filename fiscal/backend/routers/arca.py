import os, json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter()

AFIPSDK_TOKEN = os.getenv("AFIPSDK_ACCESS_TOKEN", "")

TTL_DAYS = {
    "nuestra-parte":               7,
    "monotributo-info":            7,
    "mis-retenciones":            30,
    "domicilio-fiscal-electronico": 7,
    "ccma":                       30,
    "mis-comprobantes":           30,
    "mis-facilidades":            30,
}


class SyncRequest(BaseModel):
    automation: str
    cuit: str
    password: str
    periodo: Optional[str] = None
    force:    Optional[bool] = False


def _get_afip():
    token = os.getenv("AFIPSDK_ACCESS_TOKEN", "") or AFIPSDK_TOKEN
    if not token:
        raise HTTPException(503, "AFIPSDK_ACCESS_TOKEN no configurado — ingresalo en ⚙️ del launcher")
    from afip import Afip
    return Afip({"access_token": token})


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
    db.execute(
        "DELETE FROM arca_cache WHERE automation=? AND (periodo=? OR (periodo IS NULL AND ? IS NULL))",
        (automation, periodo, periodo)
    )
    db.execute(
        "INSERT INTO arca_cache (automation, periodo, data, expires_at) VALUES (?,?,?,?)",
        (automation, periodo, json.dumps(data, ensure_ascii=False), expires)
    )
    db.commit()
    db.close()


@router.post("/api/arca/sync")
def sync_arca(req: SyncRequest):
    if not req.force:
        cached = _get_cache(req.automation, req.periodo)
        if cached:
            return {"source": "cache", "data": cached}

    afip = _get_afip()

    payload = {"cuit": req.cuit, "username": req.cuit, "password": req.password}
    if req.periodo:
        payload["periodo"] = req.periodo

    try:
        result = afip.createAutomation(req.automation, payload, True)
    except Exception as e:
        msg = str(e)
        if "401" in msg or "unauthorized" in msg.lower():
            raise HTTPException(401, "AFIP SDK: token inválido o vencido")
        if "timeout" in msg.lower():
            raise HTTPException(504, "AFIP SDK no respondió — la automatización tardó demasiado")
        raise HTTPException(502, f"AFIP SDK: {msg}")

    data = result.get("data", result) if isinstance(result, dict) else result
    _set_cache(req.automation, req.periodo, data)
    return {"source": "arca", "data": data}


@router.get("/api/arca/cache")
def list_cache():
    db = get_db()
    rows = db.execute(
        "SELECT automation, periodo, fetched_at, expires_at FROM arca_cache ORDER BY fetched_at DESC"
    ).fetchall()
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

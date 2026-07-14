import os, json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter()

AFIPSDK_TOKEN = os.getenv("AFIPSDK_ACCESS_TOKEN", "")

TTL_DAYS = {
    "nuestra-parte":                7,
    "monotributo-info":             7,
    "mis-retenciones":             30,
    "domicilio-fiscal-electronico": 7,
    "ccma":                        30,
    "mis-comprobantes":            30,
    "mis-facilidades":             30,
}


class SyncRequest(BaseModel):
    automation: str
    cuit:       str
    password:   str
    periodo:    Optional[str]  = None
    filters:    Optional[dict] = None
    page:       Optional[int]  = None
    size:       Optional[int]  = None
    mode:       Optional[str]  = None
    force:      Optional[bool] = False


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


def _set_cache(automation: str, periodo: Optional[str], data):
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


def _extract_error(result: dict) -> str:
    d = result.get("data")
    if isinstance(d, dict):
        return d.get("message", "Error desconocido")
    return str(d or "Error desconocido")


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
    if req.filters:
        payload["filters"] = req.filters
    if req.page is not None:
        payload["page"] = req.page
    if req.size is not None:
        payload["size"] = req.size
    if req.mode is not None:
        payload["mode"] = req.mode

    try:
        # wait=False: devuelve de inmediato con el ID de la automatización
        result = afip.createAutomation(req.automation, payload, False)
    except Exception as e:
        msg = str(e)
        if "401" in msg or "unauthorized" in msg.lower():
            raise HTTPException(401, "AFIP SDK: token inválido o vencido")
        raise HTTPException(502, f"AFIP SDK: {msg}")

    if not isinstance(result, dict):
        raise HTTPException(502, f"AFIP SDK: respuesta inesperada: {result}")

    status = result.get("status", "")

    if status == "complete":
        data = result.get("data", result)
        _set_cache(req.automation, req.periodo, data)
        return {"source": "arca", "data": data}

    if status == "error":
        raise HTTPException(502, f"AFIP SDK: {_extract_error(result)}")

    # in_process u otro → devolver ID para que el frontend haga polling
    return {"source": "polling", "automation_id": result.get("id"), "status": status}


@router.get("/api/arca/poll/{automation_id}")
def poll_automation(automation_id: str, automation: str, periodo: Optional[str] = None):
    afip = _get_afip()
    try:
        result = afip.getAutomationDetails(automation_id)
    except Exception as e:
        raise HTTPException(502, f"AFIP SDK: {str(e)}")

    if not isinstance(result, dict):
        return {"status": "in_process"}

    status = result.get("status", "in_process")

    if status == "complete":
        data = result.get("data", result)
        _set_cache(automation, periodo, data)
        return {"source": "arca", "status": "complete", "data": data}

    if status == "error":
        raise HTTPException(502, f"AFIP SDK: {_extract_error(result)}")

    return {"status": status}


@router.get("/api/arca/cache")
def list_cache():
    db = get_db()
    now = datetime.now().isoformat()
    rows = db.execute(
        "SELECT automation, periodo, fetched_at, expires_at FROM arca_cache WHERE expires_at IS NULL OR expires_at > ? ORDER BY fetched_at DESC",
        (now,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.get("/api/arca/cache/{automation}")
def get_cache_entry(automation: str, periodo: Optional[str] = None):
    # Devuelve el dato aunque esté expirado — el frontend solo usa esto para "Ver datos"
    db = get_db()
    row = db.execute(
        "SELECT data FROM arca_cache WHERE automation=? AND (periodo=? OR (periodo IS NULL AND ? IS NULL)) ORDER BY fetched_at DESC LIMIT 1",
        (automation, periodo, periodo)
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "No hay datos en cache para esta automatización")
    return {"automation": automation, "periodo": periodo, "data": json.loads(row["data"])}


@router.delete("/api/arca/cache/{automation}")
def clear_cache(automation: str):
    db = get_db()
    db.execute("DELETE FROM arca_cache WHERE automation=?", (automation,))
    db.commit()
    db.close()
    return {"ok": True}

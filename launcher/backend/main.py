from dotenv import load_dotenv
load_dotenv()

import os, subprocess, json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import httpx

app = FastAPI(title="Finanzas Suite Launcher")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5172", "http://localhost:5173",
                   "http://localhost:5174", "http://localhost:5175"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# Fuente de verdad única para toda la configuración del launcher
LAUNCHER_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher_config.json")

ENV_PATHS = {
    "maximos":  os.path.join(ROOT, "maximos", "backend", ".env"),
    "finanzas": os.path.join(ROOT, "finanzas", "backend", ".env"),
    "fiscal":   os.path.join(ROOT, "fiscal",   "backend", ".env"),
}

APPS = {
    "maximos":  {"backend": 8000, "frontend": 5173, "backend_dir": os.path.join(ROOT, "maximos", "backend"),  "frontend_dir": os.path.join(ROOT, "maximos", "frontend")},
    "finanzas": {"backend": 8001, "frontend": 5174, "backend_dir": os.path.join(ROOT, "finanzas", "backend"), "frontend_dir": os.path.join(ROOT, "finanzas", "frontend")},
    "fiscal":   {"backend": 8002, "frontend": 5175, "backend_dir": os.path.join(ROOT, "fiscal", "backend"),   "frontend_dir": os.path.join(ROOT, "fiscal", "frontend")},
}

# Qué env var va a cada app .env (para distribución)
KEYS_MAP = {
    "GROQ_API_KEY":         ["maximos", "finanzas", "fiscal"],
    "GOOGLE_API_KEY":       ["maximos", "finanzas", "fiscal"],
    "COINGECKO_API_KEY":    ["finanzas"],
    "AFIPSDK_ACCESS_TOKEN": ["fiscal"],
    "MAXIMOS_MODE":         ["finanzas"],
}


def _load_cfg() -> dict:
    try:
        with open(LAUNCHER_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cfg(updates: dict):
    cfg = _load_cfg()
    cfg.update(updates)
    with open(LAUNCHER_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _write_env_key(path: str, key: str, value: str):
    """Escribe/actualiza un key en un .env usando file I/O directo."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    found = False
    new_lines = []
    for line in lines:
        k = line.split('=')[0].strip().lstrip('export').strip()
        if k == key:
            new_lines.append(f'{key}={value}\n')
            found = True
        else:
            new_lines.append(line)
    if not found:
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
        new_lines.append(f'{key}={value}\n')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(new_lines)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    cfg = _load_cfg()

    # Si el launcher_config.json no tiene las keys todavía, leerlas de los .env de cada app
    # (migración única: después del primer save quedan en el JSON)
    if not any(cfg.get(k) for k in ("groq", "google", "coingecko", "afipsdk")):
        from dotenv import dotenv_values
        for path in ENV_PATHS.values():
            if not os.path.exists(path):
                continue
            env = dotenv_values(path)
            if not cfg.get("groq") and env.get("GROQ_API_KEY"):
                cfg["groq"] = env["GROQ_API_KEY"]
            if not cfg.get("google") and env.get("GOOGLE_API_KEY"):
                cfg["google"] = env["GOOGLE_API_KEY"]
            if not cfg.get("coingecko") and env.get("COINGECKO_API_KEY"):
                cfg["coingecko"] = env["COINGECKO_API_KEY"]
            if not cfg.get("afipsdk") and env.get("AFIPSDK_ACCESS_TOKEN"):
                cfg["afipsdk"] = env["AFIPSDK_ACCESS_TOKEN"]

    return JSONResponse(
        content={
            "groq":         cfg.get("groq", ""),
            "google":       cfg.get("google", ""),
            "coingecko":    cfg.get("coingecko", ""),
            "afipsdk":      cfg.get("afipsdk", ""),
            "maximos_mode": cfg.get("maximos_mode", "online"),
        },
        headers={"Cache-Control": "no-store"},
    )


class ConfigIn(BaseModel):
    groq:         Optional[str] = None
    google:       Optional[str] = None
    coingecko:    Optional[str] = None
    afipsdk:      Optional[str] = None
    maximos_mode: Optional[str] = None


@app.post("/api/config")
def save_config(data: ConfigIn):
    # 1. Guardar todo en launcher_config.json (fuente de verdad)
    updates = {
        "groq":         data.groq         or "",
        "google":       data.google       or "",
        "coingecko":    data.coingecko    or "",
        "afipsdk":      data.afipsdk      or "",
        "maximos_mode": data.maximos_mode or "online",
    }
    _save_cfg(updates)

    # 2. Distribuir a los .env de cada app
    env_map = {
        "GROQ_API_KEY":         data.groq,
        "GOOGLE_API_KEY":       data.google,
        "COINGECKO_API_KEY":    data.coingecko,
        "AFIPSDK_ACCESS_TOKEN": data.afipsdk,
        "MAXIMOS_MODE":         data.maximos_mode,
    }
    for env_var, value in env_map.items():
        if not value or not value.strip():
            continue
        for app_id in KEYS_MAP.get(env_var, []):
            try:
                _write_env_key(ENV_PATHS[app_id], env_var, value.strip())
            except Exception:
                pass
        os.environ[env_var] = value.strip()

    return {"ok": True}


@app.get("/api/apps/status")
async def apps_status():
    results = {}
    async with httpx.AsyncClient(timeout=2) as client:
        for app_id, info in APPS.items():
            backend_ok = frontend_ok = False
            try:
                r = await client.get(f"http://localhost:{info['backend']}/api/health")
                backend_ok = r.is_success
            except Exception:
                pass
            try:
                r = await client.get(f"http://localhost:{info['frontend']}/")
                frontend_ok = r.status_code < 500
            except Exception:
                pass
            results[app_id] = {"backend": backend_ok, "frontend": frontend_ok}
    return results


@app.post("/api/apps/{app_id}/start")
async def start_app(app_id: str):
    if app_id not in APPS:
        return {"error": "app desconocida"}
    info = APPS[app_id]
    is_win = os.name == "nt"
    flags = subprocess.CREATE_NEW_CONSOLE if is_win else 0

    async with httpx.AsyncClient(timeout=2) as client:
        try:
            r = await client.get(f"http://localhost:{info['backend']}/api/health")
            if r.is_success:
                return {"started": False, "message": f"{app_id} ya estaba corriendo"}
        except Exception:
            pass

    subprocess.Popen(
        ["uvicorn", "main:app", "--port", str(info["backend"])],
        cwd=info["backend_dir"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=flags,
    )
    subprocess.Popen(
        ["npm", "run", "dev"], cwd=info["frontend_dir"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags, shell=is_win,
    )
    return {"started": True}

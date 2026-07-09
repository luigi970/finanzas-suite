from dotenv import load_dotenv, dotenv_values
load_dotenv()

import os, subprocess
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

ROOT     = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SELF_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")  # launcher/backend/.env

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

# A qué app .env va cada variable (para distribución al guardar)
KEYS_MAP = {
    "GROQ_API_KEY":         ["maximos", "finanzas", "fiscal"],
    "GOOGLE_API_KEY":       ["maximos", "finanzas", "fiscal"],
    "COINGECKO_API_KEY":    ["finanzas"],
    "AFIPSDK_ACCESS_TOKEN": ["fiscal"],
    "MAXIMOS_MODE":         ["finanzas"],
}


def _write_env_key(path: str, key: str, value: str):
    """Escribe/actualiza un key en un .env con file I/O directo."""
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
    # Leer siempre del .env propio del launcher (fuente de verdad)
    env = dotenv_values(SELF_ENV)
    return JSONResponse(
        content={
            "groq":         env.get("GROQ_API_KEY", ""),
            "google":       env.get("GOOGLE_API_KEY", ""),
            "coingecko":    env.get("COINGECKO_API_KEY", ""),
            "afipsdk":      env.get("AFIPSDK_ACCESS_TOKEN", ""),
            "maximos_mode": env.get("MAXIMOS_MODE", "online"),
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
    env_map = {
        "GROQ_API_KEY":         data.groq,
        "GOOGLE_API_KEY":       data.google,
        "COINGECKO_API_KEY":    data.coingecko,
        "AFIPSDK_ACCESS_TOKEN": data.afipsdk,
        "MAXIMOS_MODE":         data.maximos_mode,
    }

    for env_var, value in env_map.items():
        # Siempre escribir en el .env del launcher (vacío = borra el valor)
        _write_env_key(SELF_ENV, env_var, (value or "").strip())

        # Distribuir a los .env de cada app solo si tiene valor
        if value and value.strip():
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

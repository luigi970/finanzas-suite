from dotenv import load_dotenv
load_dotenv()

import os, subprocess
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

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

KEYS_MAP = {
    "GROQ_API_KEY":         ["maximos", "finanzas", "fiscal"],
    "GOOGLE_API_KEY":       ["maximos", "finanzas", "fiscal"],
    "COINGECKO_API_KEY":    ["finanzas"],
    "AFIPSDK_ACCESS_TOKEN": ["fiscal"],
}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/config")
def get_config():
    from dotenv import dotenv_values
    result = {}
    for app_id, path in ENV_PATHS.items():
        if os.path.exists(path):
            env = dotenv_values(path)
            for key in ["GROQ_API_KEY", "GOOGLE_API_KEY", "COINGECKO_API_KEY", "AFIPSDK_ACCESS_TOKEN"]:
                if key in env and env[key]:
                    result[key] = env[key]
    return {
        "groq":      result.get("GROQ_API_KEY", ""),
        "google":    result.get("GOOGLE_API_KEY", ""),
        "coingecko": result.get("COINGECKO_API_KEY", ""),
        "afipsdk":   result.get("AFIPSDK_ACCESS_TOKEN", ""),
    }

class ConfigIn(BaseModel):
    groq:      Optional[str] = None
    google:    Optional[str] = None
    coingecko: Optional[str] = None
    afipsdk:   Optional[str] = None

@app.post("/api/config")
def save_config(data: ConfigIn):
    from dotenv import set_key
    updates = {
        "GROQ_API_KEY":         data.groq,
        "GOOGLE_API_KEY":       data.google,
        "COINGECKO_API_KEY":    data.coingecko,
        "AFIPSDK_ACCESS_TOKEN": data.afipsdk,
    }
    for env_var, value in updates.items():
        if not value or not value.strip():
            continue
        targets = KEYS_MAP.get(env_var, [])
        for app_id in targets:
            path = ENV_PATHS[app_id]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                set_key(path, env_var, value.strip())
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

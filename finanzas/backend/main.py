from dotenv import load_dotenv
load_dotenv()

import os, subprocess
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import init_db
from routers import accounts, positions, transactions, ingest, agent
import httpx

app = FastAPI(title="Finanzas Personales")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(positions.router)
app.include_router(transactions.router)
app.include_router(ingest.router)
app.include_router(agent.router)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    return {"status": "ok"}

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

@app.get("/api/config")
def get_config():
    from dotenv import dotenv_values
    env = dotenv_values(ENV_PATH)
    return {
        "groq":         env.get("GROQ_API_KEY") or "",
        "google":       env.get("GOOGLE_API_KEY") or "",
        "coingecko":    env.get("COINGECKO_API_KEY") or "",
        "maximos_mode": env.get("MAXIMOS_MODE") or "online",
    }

class ConfigIn(BaseModel):
    groq_key:       Optional[str] = None
    google_key:     Optional[str] = None
    coingecko_key:  Optional[str] = None

MAXIMOS_ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "maximos", "backend", ".env")
)

@app.post("/api/config")
def save_config(data: ConfigIn):
    from dotenv import set_key
    updates = {
        "GROQ_API_KEY":      data.groq_key,
        "GOOGLE_API_KEY":    data.google_key,
        "COINGECKO_API_KEY": data.coingecko_key,
    }
    for env_var, value in updates.items():
        if value and value.strip():
            set_key(ENV_PATH, env_var, value.strip())
            try:
                set_key(MAXIMOS_ENV_PATH, env_var, value.strip())
            except Exception:
                pass
            os.environ[env_var] = value.strip()
    return {"ok": True}

MAXIMOS_BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "maximos", "backend")
)

@app.get("/api/maximos/status")
async def maximos_status():
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get("http://localhost:8000/api/status")
            return {"running": r.is_success}
    except Exception:
        return {"running": False}

@app.post("/api/maximos/start")
async def maximos_start():
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get("http://localhost:8000/api/status")
            if r.is_success:
                return {"started": False, "message": "Ya estaba corriendo"}
    except Exception:
        pass
    subprocess.Popen(
        ["uvicorn", "main:app", "--port", "8000"],
        cwd=MAXIMOS_BACKEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
    )
    return {"started": True}

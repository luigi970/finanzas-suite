from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import init_db
from routers import profile, arca, agent, documents

app = FastAPI(title="Asistente Fiscal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://localhost:5174", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(arca.router)
app.include_router(agent.router)
app.include_router(documents.router)

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
        "groq":      env.get("GROQ_API_KEY") or "",
        "google":    env.get("GOOGLE_API_KEY") or "",
        "afipsdk":   env.get("AFIPSDK_ACCESS_TOKEN") or "",
    }

class ConfigIn(BaseModel):
    groq_key:    Optional[str] = None
    google_key:  Optional[str] = None
    afipsdk_key: Optional[str] = None

@app.post("/api/config")
def save_config(data: ConfigIn):
    from dotenv import set_key
    updates = {
        "GROQ_API_KEY":         data.groq_key,
        "GOOGLE_API_KEY":       data.google_key,
        "AFIPSDK_ACCESS_TOKEN": data.afipsdk_key,
    }
    for env_var, value in updates.items():
        if value and value.strip():
            set_key(ENV_PATH, env_var, value.strip())
            os.environ[env_var] = value.strip()
    return {"ok": True}

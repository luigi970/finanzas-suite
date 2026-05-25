from dotenv import load_dotenv
load_dotenv()

import os, subprocess
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

MAXIMOS_BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "backend")
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

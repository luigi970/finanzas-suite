import os
import threading
import time

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from screener import get_tickers, run_screener, LISTS

load_dotenv()

app = FastAPI(title="Stock Screener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache: dict = {
    "data": [], "last_updated": None, "status": "idle",
    "processed": 0, "total_tickers": 0, "list_id": "sp500",
}
_lock = threading.Lock()


class RefreshRequest(BaseModel):
    list_id: str = "sp500"
    custom: list[str] = []
    crypto_limit: int = 20


def _refresh_cache(list_id: str, custom: list[str], crypto_limit: int = 20):
    _cache["status"] = "downloading"
    _cache["processed"] = 0
    _cache["data"] = []
    _cache["list_id"] = list_id

    tickers = get_tickers(list_id, custom, crypto_limit)
    _cache["total_tickers"] = len(tickers)
    _cache["status"] = "loading"

    def on_result(result, n):
        with _lock:
            _cache["processed"] = n
            if result is not None:
                _cache["data"].append(result)
                _cache["data"].sort(key=lambda x: x["pct_from_high"], reverse=True)

    run_screener(tickers, on_result=on_result)
    _cache["last_updated"] = time.time()
    _cache["status"] = "ready"


@app.get("/api/status")
def get_status():
    return {
        "status": _cache["status"],
        "last_updated": _cache["last_updated"],
        "total": len(_cache["data"]),
        "processed": _cache["processed"],
        "total_tickers": _cache["total_tickers"],
        "list_id": _cache["list_id"],
    }


@app.get("/api/lists")
def get_lists():
    return {
        "lists": [
            {"id": "sp500",     "label": "S&P 500",          "count": 503},
            {"id": "nasdaq100", "label": "Nasdaq 100",        "count": len(LISTS["nasdaq100"])},
            {"id": "etfs",      "label": "ETFs",              "count": len(LISTS["etfs"])},
            {"id": "adrs_arg",  "label": "ADRs Argentina",    "count": len(LISTS["adrs_arg"])},
            {"id": "custom",    "label": "Lista personalizada","count": None},
        ]
    }


@app.post("/api/refresh")
def refresh(body: RefreshRequest, background_tasks: BackgroundTasks):
    if _cache["status"] in ("loading", "downloading"):
        return {"message": "Ya hay una carga en progreso"}
    background_tasks.add_task(_refresh_cache, body.list_id, body.custom, body.crypto_limit)
    return {"message": "Carga iniciada"}


@app.post("/api/analyze")
async def analyze(body: dict):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY no configurada"}

    ticker = body.get("ticker", "?")
    signal_label = {
        "compra_fuerte": "COMPRA FUERTE", "compra": "COMPRA",
        "neutral": "NEUTRAL", "venta": "VENTA", "venta_fuerte": "VENTA FUERTE",
    }.get(body.get("signal", "neutral"), body.get("signal", "NEUTRAL").upper())

    prompt = (
        f"Sos un analista técnico experto. Analizá el siguiente activo y escribí una "
        f"recomendación clara y concisa en español (máximo 4 oraciones). Sé directo, "
        f"usa datos concretos, no uses bullets ni markdown.\n\n"
        f"ACTIVO: {ticker}\n"
        f"Precio: {body.get('price')} | Señal: {signal_label} | Dirección: {body.get('direction','NEUTRAL')}\n"
        f"Score LONG: {body.get('long_score',0)}/100 | Score SHORT: {body.get('short_score',0)}/100\n"
        f"Zona estructural: {str(body.get('zone','fair')).upper()} | ADX: {body.get('adx')} | RSI: {body.get('rsi')}\n"
        f"Momentum oscilador: {body.get('mom')} | Pulse: {body.get('pulse_signal','NEUTRAL')} ({body.get('pulse_state','NEUTRAL')})\n"
        f"Volumen relativo: {body.get('vol_ratio')}x | %B Bollinger: {body.get('pct_b')}\n"
        f"Distancia de máximo 52s: {body.get('pct_from_high')}% | de mínimo: {body.get('pct_from_low')}%\n"
        f"vs MA200: {body.get('pct_vs_ma200')}% | POC volumen: {body.get('poc')}\n"
        f"MACD histograma: {body.get('macd_hist')}\n"
        f"SL sugerido: {body.get('sl')} | TP1 sugerido: {body.get('tp1')}\n\n"
        f"Recomendación:"
    )

    async def call_groq(key):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 512, "temperature": 0.4},
            )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return data["choices"][0]["message"]["content"].strip()

    async def call_gemini(key):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": 512, "temperature": 0.4}},
            )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GOOGLE_API_KEY")

    try:
        if groq_key:
            recommendation = await call_groq(groq_key)
        else:
            recommendation = await call_gemini(gemini_key)
        return {"ticker": ticker, "recommendation": recommendation}
    except Exception as groq_err:
        if gemini_key:
            try:
                return {"ticker": ticker, "recommendation": await call_gemini(gemini_key)}
            except Exception as gemini_err:
                return {"error": f"Groq: {groq_err} | Gemini: {gemini_err}"}
        return {"error": str(groq_err)}


@app.get("/api/stocks")
def get_stocks(signal: str = "all"):
    data = [s for s in _cache["data"] if s is not None]
    if signal != "all":
        data = [s for s in data if s.get("signal") == signal]
    return {
        "status": _cache["status"],
        "last_updated": _cache["last_updated"],
        "total": len(data),
        "stocks": data,
    }

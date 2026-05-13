from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from screener import get_tickers, run_screener, LISTS
import threading
import time

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

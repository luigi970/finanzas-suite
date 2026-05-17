import os
import concurrent.futures
import threading
import time

import httpx
import yfinance as yf
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

    raw = body.get("ticker", "?")
    ticker = raw[:-4] if raw.endswith("-USD") else raw
    price  = body.get("price") or 0

    signal_label = {
        "compra_fuerte": "COMPRA FUERTE", "compra": "COMPRA",
        "neutral": "NEUTRAL", "venta": "VENTA", "venta_fuerte": "VENTA FUERTE",
    }.get(body.get("signal", "neutral"), "NEUTRAL")

    zone_desc = {
        "discount": "zona de descuento (precio bajo respecto a su historia reciente)",
        "fair":     "zona de valor justo (precio equilibrado)",
        "premium":  "zona premium (precio elevado respecto a su historia reciente)",
    }.get(body.get("zone", "fair"), "zona de valor justo")

    def _fmt(v): return str(round(v, 2)) if v is not None else "—"

    ma_parts = []
    for name, key in [("MA5","pct_vs_ma5"),("MA10","pct_vs_ma10"),("MA20","pct_vs_ma20"),
                      ("MA50","pct_vs_ma50"),("MA200","pct_vs_ma200")]:
        v = body.get(key)
        if v is not None:
            ma_parts.append(f"{name}: {'+' if v >= 0 else ''}{v:.1f}%")
    ma_line = " | ".join(ma_parts) if ma_parts else "no disponibles"

    rsi   = body.get("rsi")
    rsi_note = (" — sobrecomprado, cuidado con una corrección" if rsi and rsi > 70 else
                " — sobrevendido, posible rebote" if rsi and rsi < 30 else " — zona neutral") if rsi else ""

    adx = body.get("adx")
    adx_note = (" — tendencia definida y fuerte" if adx and adx > 25 else
                " — sin tendencia clara, mercado lateral" if adx and adx < 15 else " — tendencia moderada") if adx else ""

    macd = body.get("macd_hist")
    macd_note = (" — momentum alcista" if macd and macd > 0 else " — momentum bajista") if macd is not None else ""

    pct_b = body.get("pct_b")
    bb_note = (" — precio tocando el techo de la banda" if pct_b and pct_b > 0.8 else
               " — precio en el piso de la banda"       if pct_b and pct_b < 0.2 else "") if pct_b is not None else ""

    vol = body.get("vol_ratio")
    vol_note = (" — volumen excepcionalmente alto, hay interés institucional real" if vol and vol > 2.0 else
                " — volumen por encima del promedio"                               if vol and vol > 1.5 else
                " — volumen muy bajo, movimiento sin convicción"                   if vol and vol < 0.7 else "") if vol else ""

    candle = body.get("candle_pattern")
    candle_txt = "sin patrón especial en las últimas velas"
    if candle and isinstance(candle, dict) and candle.get("name"):
        tipo = {"bullish": "señal alcista", "bearish": "señal bajista", "neutral": "señal de indecisión"}.get(candle.get("type",""), "")
        candle_txt = f"{candle['name']}{' (' + tipo + ')' if tipo else ''}"

    pulse_parts = [p for p in [body.get("pulse_state"), body.get("pulse_signal")] if p]
    pulse_txt   = " / ".join(pulse_parts) if pulse_parts else "NEUTRAL"

    pivots_line = ""
    pivots  = body.get("pivots") or {}
    classic = pivots.get("classic") or {}
    if classic:
        P, R1, S1 = classic.get("P"), classic.get("R1"), classic.get("S1")
        if P and R1 and S1:
            pos = "por encima del pivot" if price > P else "por debajo del pivot"
            pivots_line = f"\nNiveles pivot del día: Soporte S1=${S1} | Pivot central P=${P} ({pos}) | Resistencia R1=${R1}"

    prompt = (
        "Sos el mejor analista financiero del mundo. "
        "Combinás la precisión de un quant con la calidez de un gran comunicador. "
        "Tu misión es explicarle a una persona común — sin experiencia en mercados — "
        "qué conviene hacer con este activo hoy y por qué. "
        "Hablás como un amigo muy exitoso en inversiones: directo, confiado, sin jerga técnica. "
        "Cuando usás un término técnico, lo explicás en pocas palabras entre paréntesis. "
        "Escribís en español rioplatense. Sin bullets, sin títulos, sin markdown. "
        "El output es exactamente 4 o 5 oraciones seguidas, bien redactadas, que fluyan de forma natural.\n\n"
        f"ACTIVO: {ticker} | Precio actual: ${price}\n"
        f"Señal del sistema: {signal_label} | Dirección dominante: {body.get('direction','NEUTRAL')}\n"
        f"Puntaje alcista: {body.get('long_score',0)}/100 | Puntaje bajista: {body.get('short_score',0)}/100\n\n"
        f"Posición estructural: {zone_desc}\n"
        f"Distancia al máximo del año: {_fmt(body.get('pct_from_high'))}% | Al mínimo del año: +{_fmt(body.get('pct_from_low'))}%\n"
        f"Precio de mayor volumen histórico (POC): ${_fmt(body.get('poc'))}\n\n"
        f"Medias móviles (precio vs promedio): {ma_line}\n\n"
        f"RSI (impulso): {_fmt(rsi)}{rsi_note}\n"
        f"MACD histograma: {_fmt(macd)}{macd_note}\n"
        f"Bollinger %B: {_fmt(pct_b)}{bb_note}\n"
        f"Momentum oscilador: {_fmt(body.get('mom'))} | Pulse: {pulse_txt}\n"
        f"ADX (fuerza de tendencia): {_fmt(adx)}{adx_note}\n"
        f"Volumen relativo al promedio: {_fmt(vol)}x{vol_note}\n"
        f"Patrón de velas reciente: {candle_txt}"
        f"{pivots_line}\n\n"
        f"Stop Loss sugerido: ${_fmt(body.get('sl'))} | TP1: ${_fmt(body.get('tp1'))} | TP2: ${_fmt(body.get('tp2'))}\n\n"
        "Escribí la recomendación empezando directamente con la conclusión (qué conviene hacer, sin rodeos). "
        "Usá los 2 o 3 datos más relevantes de forma natural dentro del texto, sin listarlos. "
        "Indicá brevemente dónde estaría la señal de que la idea falla. "
        "Terminá con una frase que dé perspectiva sobre el riesgo o la oportunidad. "
        "Soná como un experto de verdad hablando con un amigo, no como un reporte automático.\n\n"
        "Recomendación:"
    )

    async def call_groq(key):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 700, "temperature": 0.5},
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


@app.get("/api/info")
def get_info(ticker: str = ""):
    if not ticker:
        return {"info": {}}
    try:
        from datetime import datetime, timezone
        t = yf.Ticker(ticker.upper())
        info = t.info
        def _n(k): return info.get(k)

        earnings_date = None
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                dates = cal.get("Earnings Date", [])
                if dates:
                    now = datetime.now(timezone.utc)
                    future = [d for d in dates if hasattr(d, "timestamp") and d.timestamp() > now.timestamp()]
                    pick = future[0] if future else dates[0]
                    earnings_date = pick.date().isoformat() if hasattr(pick, "date") else str(pick)
        except Exception:
            pass

        return {"info": {
            "name":              _n("longName") or _n("shortName") or ticker.upper(),
            "sector":            _n("sector") or "",
            "industry":          _n("industry") or "",
            "market_cap":        _n("marketCap"),
            "trailing_pe":       _n("trailingPE"),
            "forward_pe":        _n("forwardPE"),
            "beta":              _n("beta"),
            "dividend_yield":    _n("dividendYield"),
            "target_price":      _n("targetMeanPrice"),
            "target_high":       _n("targetHighPrice"),
            "target_low":        _n("targetLowPrice"),
            "recommendation_key": _n("recommendationKey"),
            "analyst_count":     _n("numberOfAnalystOpinions"),
            "earnings_date":     earnings_date,
        }}
    except Exception as e:
        return {"info": {}, "error": str(e)}


@app.get("/api/news")
def get_news(ticker: str = ""):
    if not ticker:
        return {"news": []}
    try:
        raw = yf.Ticker(ticker.upper()).news or []
        news = []
        for item in raw[:15]:
            content = item.get("content", {})
            title = content.get("title") or item.get("title", "")
            summary = content.get("summary", "")
            publisher = (content.get("provider") or {}).get("displayName") or item.get("publisher", "")
            pub_time = (content.get("pubDate") or "")
            link = (content.get("canonicalUrl") or {}).get("url") or item.get("link", "")
            thumbnail = None
            thumbs = (content.get("thumbnail") or {}).get("resolutions") or []
            if thumbs:
                thumbnail = thumbs[0].get("url")
            if title and link:
                news.append({
                    "title":     title,
                    "summary":   summary,
                    "publisher": publisher,
                    "time":      pub_time,
                    "link":      link,
                    "thumbnail": thumbnail,
                })
        return {"news": news}
    except Exception as e:
        return {"news": [], "error": str(e)}


@app.get("/api/quotes")
def get_quotes(tickers: str = ""):
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not symbols:
        return {"quotes": {}}

    def fetch_one(symbol):
        try:
            fi = yf.Ticker(symbol).fast_info
            price      = fi.last_price
            prev_close = fi.previous_close
            change     = round(price - prev_close, 2)                    if price and prev_close else None
            change_pct = round((price - prev_close) / prev_close * 100, 2) if price and prev_close else None
            return symbol, {
                "price":      round(price, 2)      if price      else None,
                "change":     change,
                "change_pct": change_pct,
                "open":       round(fi.open, 2)      if fi.open      else None,
                "high":       round(fi.day_high, 2)  if fi.day_high  else None,
                "low":        round(fi.day_low, 2)   if fi.day_low   else None,
                "volume":     fi.volume,
                "prev_close": round(prev_close, 2)   if prev_close   else None,
            }
        except Exception:
            return symbol, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(symbols), 8)) as ex:
        results = dict(ex.map(fetch_one, symbols))

    return {"quotes": {k: v for k, v in results.items() if v is not None}}


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

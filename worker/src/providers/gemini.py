import json

from workers import fetch

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-2.0-flash-lite"


async def analyze(ticker_data: dict, api_key: str) -> str:
    prompt = _build_prompt(ticker_data)

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 512, "temperature": 0.4},
    }

    url = f"{GEMINI_BASE}/{MODEL}:generateContent?key={api_key}"
    response = await fetch(
        url,
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload),
    )

    text = await response.text()
    data = json.loads(text)

    if "error" in data:
        raise RuntimeError(f"Gemini error: {data['error'].get('message', data['error'])}")

    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _build_prompt(s: dict) -> str:
    ticker = s.get("ticker", "?")
    price = s.get("price")
    signal = s.get("signal", "neutral")
    direction = s.get("direction", "NEUTRAL")
    long_score = s.get("long_score", 0)
    short_score = s.get("short_score", 0)
    zone = s.get("zone", "fair")
    adx = s.get("adx")
    rsi = s.get("rsi")
    mom = s.get("mom")
    pulse = s.get("pulse_signal", "NEUTRAL")
    pulse_state = s.get("pulse_state", "NEUTRAL")
    vol_ratio = s.get("vol_ratio")
    pct_b = s.get("pct_b")
    pct_from_high = s.get("pct_from_high")
    pct_from_low = s.get("pct_from_low")
    pct_vs_ma200 = s.get("pct_vs_ma200")
    sl = s.get("sl")
    tp1 = s.get("tp1")
    poc = s.get("poc")
    macd_hist = s.get("macd_hist")

    signal_label = {
        "compra_fuerte": "COMPRA FUERTE",
        "compra": "COMPRA",
        "neutral": "NEUTRAL",
        "venta": "VENTA",
        "venta_fuerte": "VENTA FUERTE",
    }.get(signal, signal.upper())

    return f"""Sos un analista técnico experto. Analizá el siguiente activo y escribí una recomendación clara y concisa en español (máximo 4 oraciones). Sé directo, usa datos concretos, no uses bullets ni markdown.

ACTIVO: {ticker}
Precio: {price} | Señal: {signal_label} | Dirección: {direction}
Score LONG: {long_score}/100 | Score SHORT: {short_score}/100
Zona estructural: {zone.upper()} | ADX: {adx} | RSI: {rsi}
Momentum oscilador: {mom} | Pulse: {pulse} ({pulse_state})
Volumen relativo: {vol_ratio}x | %B Bollinger: {pct_b}
Distancia de máximo 52s: {pct_from_high}% | de mínimo: {pct_from_low}%
vs MA200: {pct_vs_ma200}% | POC volumen: {poc}
MACD histograma: {macd_hist}
SL sugerido: {sl} | TP1 sugerido: {tp1}

Recomendación:"""

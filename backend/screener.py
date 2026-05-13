import io
import httpx
import pandas as pd
import numpy as np
import yfinance as yf

SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies"
    "/main/data/constituents.csv"
)

LISTS: dict[str, list[str]] = {
    "nasdaq100": [
        "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","GOOG","AVGO","COST",
        "NFLX","ASML","AZN","TMUS","AMD","PEP","LIN","CSCO","ADBE","TXN",
        "QCOM","INTU","ISRG","AMAT","BKNG","CMCSA","HON","AMGN","MU","VRTX",
        "ARM","LRCX","REGN","ADI","KLAC","PANW","CRWD","MELI","GILD","SNPS",
        "CDNS","CTAS","MDLZ","ADP","ABNB","MAR","ORLY","FTNT","CEG","CSX",
        "DXCM","PCAR","ROP","CHTR","WDAY","MNST","NXPI","MRVL","PYPL","FAST",
        "KDP","IDXX","AEP","CPRT","ROST","FANG","ODFL","PAYX","VRSK","MCHP",
        "EXC","GEHC","EA","KHC","DDOG","XEL","CTSH","WBD","LULU","ON",
        "BKR","ZS","CSGP","CCEP","TTWO","BIIB","ILMN","WBA","DLTR","SIRI",
        "MDB","ALGN","ENPH","ZM","LCID","RIVN","SMCI","NWSA","NWS","FOX",
    ],
    "etfs": [
        "SPY","IVV","VOO","QQQ","IWM","DIA","VTI","VEA","VWO","EFA",
        "XLF","XLK","XLE","XLV","XLI","XLY","XLP","XLU","XLB","XLRE",
        "TLT","IEF","SHY","AGG","BND","HYG","LQD","EMB",
        "GLD","SLV","USO","UNG","PDBC","DBC","CORN","WEAT",
        "UVXY","SQQQ","SH","PSQ",
        "ARKK","ARKG","ARKW","SOXX","SMH","CIBR","ICLN","JETS","ROBO",
    ],
    "adrs_arg": [
        "GGAL","BMA","SUPV","BBAR","PAMP","CEPU","EDN","TGSU2",
        "LOMA","CRESY","IRS","MELI","GLOB","VIST","YPF","PAM","TGS",
    ],
}


def get_sp500_tickers() -> list[str]:
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(SP500_CSV_URL)
        resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    return [t.replace(".", "-") for t in df["Symbol"].tolist()]


def get_tickers(list_id: str, custom: list[str] | None = None) -> list[str]:
    if list_id == "sp500":
        return get_sp500_tickers()
    if list_id == "custom" and custom:
        return [t.upper().strip() for t in custom if t.strip()]
    return LISTS.get(list_id, [])


# ── Indicadores ──────────────────────────────────────────────────────────────

def compute_rsi(closes: pd.Series, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def compute_macd(closes: pd.Series):
    if len(closes) < 35:
        return None, None, None
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal
    return (
        round(float(macd_line.iloc[-1]), 4),
        round(float(signal.iloc[-1]), 4),
        round(float(histogram.iloc[-1]), 4),
    )


def compute_bollinger(closes: pd.Series, period: int = 20):
    if len(closes) < period:
        return None, None, None
    ma = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    price = closes.iloc[-1]
    b_upper = float(upper.iloc[-1])
    b_lower = float(lower.iloc[-1])
    if b_upper == b_lower:
        return None, None, None
    # %B: 0 = banda inferior, 1 = banda superior
    pct_b = (price - b_lower) / (b_upper - b_lower)
    return round(b_upper, 2), round(b_lower, 2), round(float(pct_b), 3)


# ── Scoring ───────────────────────────────────────────────────────────────────
#
# Score 0-100 compuesto por 5 componentes:
#
#  Tendencia   (30 pts): precio vs MA200, MA50 vs MA200
#  RSI         (20 pts): zona óptima de compra/venta
#  MACD        (20 pts): dirección y cruce
#  Volumen     (15 pts): confirmación con volumen relativo
#  Bollinger   (15 pts): posición dentro de las bandas
#
# < 20  → Venta Fuerte   (señal bajista muy clara)
# 20-39 → Venta          (presión bajista)
# 40-59 → Neutral
# 60-74 → Compra         (señal alcista)
# ≥ 75  → Compra Fuerte  (confluencia de señales alcistas)

def compute_score(
    price: float,
    ma50: float | None,
    ma200: float | None,
    rsi: float | None,
    macd_hist: float | None,
    macd_line: float | None,
    macd_signal: float | None,
    vol_ratio: float | None,
    pct_b: float | None,
) -> int:
    score = 0

    # Tendencia (30 pts)
    if ma200 is not None:
        if price > ma200:
            score += 20          # precio sobre MA200 = tendencia alcista
        else:
            score -= 10          # precio bajo MA200 = tendencia bajista
        if ma50 is not None:
            if ma50 > ma200:
                score += 10      # golden cross / estructura alcista
            else:
                score -= 5       # death cross / estructura bajista

    # RSI (20 pts)
    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 20          # zona ideal: momentum sin exceso
        elif rsi < 30:
            score += 15          # sobreventa — rebote potencial
        elif 30 <= rsi < 40:
            score += 10          # acercándose a sobreventa
        elif 60 < rsi <= 70:
            score += 5           # momentum positivo pero vigilar
        elif rsi > 70:
            score -= 10          # sobrecompra

    # MACD (20 pts)
    if macd_hist is not None:
        if macd_hist > 0:
            score += 12          # histograma positivo
        else:
            score -= 8
        if macd_line is not None and macd_signal is not None:
            if macd_line > macd_signal:
                score += 8       # MACD sobre señal = momentum alcista
            else:
                score -= 5

    # Volumen (15 pts)
    if vol_ratio is not None:
        if vol_ratio >= 1.5:
            score += 15          # volumen 50% sobre la media — confirma movimiento
        elif vol_ratio >= 1.2:
            score += 8
        elif vol_ratio < 0.7:
            score -= 5           # volumen bajo — movimiento no confirmado

    # Bollinger %B (15 pts)
    if pct_b is not None:
        if pct_b < 0.2:
            score += 15          # cerca de banda inferior — sobreventa técnica
        elif pct_b < 0.4:
            score += 8
        elif pct_b > 0.8:
            score -= 10          # cerca de banda superior — sobrecompra técnica
        elif pct_b > 0.6:
            score -= 3

    return max(0, min(100, score))


def score_to_signal(score: int) -> str:
    if score >= 75:
        return "compra_fuerte"
    if score >= 60:
        return "compra"
    if score >= 40:
        return "neutral"
    if score >= 20:
        return "venta"
    return "venta_fuerte"


# ── Screener ─────────────────────────────────────────────────────────────────

def run_screener(tickers: list[str], on_result=None) -> list[dict]:
    data = yf.download(
        " ".join(tickers), period="1y", progress=False, auto_adjust=True
    )

    if isinstance(data.columns, pd.MultiIndex):
        close_df  = data["Close"]
        high_df   = data["High"]
        low_df    = data["Low"]
        volume_df = data["Volume"]
    else:
        close_df  = data[["Close"]].rename(columns={"Close": tickers[0]})
        high_df   = data[["High"]].rename(columns={"High": tickers[0]})
        low_df    = data[["Low"]].rename(columns={"Low": tickers[0]})
        volume_df = data[["Volume"]].rename(columns={"Volume": tickers[0]})

    results = []
    for i, ticker in enumerate(tickers):
        result = None
        try:
            if ticker not in close_df.columns:
                raise KeyError(ticker)

            close  = close_df[ticker].dropna()
            high   = high_df[ticker].dropna()
            low    = low_df[ticker].dropna()
            volume = volume_df[ticker].dropna()

            if len(close) < 30:
                raise ValueError("insufficient data")

            price    = float(close.iloc[-1])
            high_52w = float(high.max())
            low_52w  = float(low.min())

            ma50  = float(close.rolling(50).mean().iloc[-1])  if len(close) >= 50  else None
            ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

            rsi                        = compute_rsi(close)
            macd_line, macd_sig, macd_hist = compute_macd(close)
            bb_upper, bb_lower, pct_b  = compute_bollinger(close)

            vol_avg   = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else None
            vol_today = float(volume.iloc[-1])
            vol_ratio = round(vol_today / vol_avg, 2) if vol_avg and vol_avg > 0 else None

            pct_from_high = round((price - high_52w) / high_52w * 100, 2)
            pct_from_low  = round((price - low_52w)  / low_52w  * 100, 2)
            pct_vs_ma200  = round((price - ma200) / ma200 * 100, 2) if ma200 else None
            pct_vs_ma50   = round((price - ma50)  / ma50  * 100, 2) if ma50  else None

            score  = compute_score(price, ma50, ma200, rsi, macd_hist, macd_line, macd_sig, vol_ratio, pct_b)
            signal = score_to_signal(score)

            result = {
                "ticker":        ticker,
                "price":         round(price, 2),
                "score":         score,
                "signal":        signal,
                # 52 semanas
                "high_52w":      round(high_52w, 2),
                "low_52w":       round(low_52w, 2),
                "pct_from_high": pct_from_high,
                "pct_from_low":  pct_from_low,
                # Medias móviles
                "ma50":          round(ma50, 2)  if ma50  else None,
                "ma200":         round(ma200, 2) if ma200 else None,
                "pct_vs_ma50":   pct_vs_ma50,
                "pct_vs_ma200":  pct_vs_ma200,
                # Momentum
                "rsi":           rsi,
                "macd_hist":     macd_hist,
                # Volumen
                "vol_ratio":     vol_ratio,
                # Bollinger
                "bb_upper":      bb_upper,
                "bb_lower":      bb_lower,
                "pct_b":         pct_b,
            }
            results.append(result)
        except Exception:
            pass

        if on_result:
            on_result(result, i + 1)

    return sorted(results, key=lambda x: x["score"], reverse=True)

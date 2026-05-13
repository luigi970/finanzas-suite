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
    # Top 100 crypto por market cap (sin stablecoins) — ordenados de mayor a menor.
    # get_tickers() acepta el parámetro `crypto_limit` para devolver los primeros N.
    "crypto": [
        "BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD",
        "ADA-USD","AVAX-USD","DOGE-USD","TRX-USD","DOT-USD",
        "LINK-USD","MATIC-USD","LTC-USD","BCH-USD","NEAR-USD",
        "UNI-USD","ATOM-USD","XLM-USD","SHIB-USD","APT-USD",
        "SUI-USD","OP-USD","ARB-USD","FIL-USD","INJ-USD",
        "HBAR-USD","IMX-USD","VET-USD","GRT-USD","ALGO-USD",
        "SAND-USD","MANA-USD","AXS-USD","CHZ-USD","ENJ-USD",
        "AAVE-USD","SNX-USD","CRV-USD","LDO-USD","MKR-USD",
        "RUNE-USD","KAVA-USD","FLOW-USD","EOS-USD","XTZ-USD",
        "EGLD-USD","THETA-USD","FTM-USD","ZIL-USD","ONE-USD",
        "ICX-USD","ZRX-USD","BAT-USD","SC-USD","DCR-USD",
        "DASH-USD","ZEC-USD","XMR-USD","WAVES-USD","IOTA-USD",
        "QTUM-USD","ONT-USD","LSK-USD","NANO-USD","DGB-USD",
        "RVN-USD","STORJ-USD","SKL-USD","OGN-USD","RSR-USD",
        "CELR-USD","BAND-USD","ANKR-USD","CKB-USD","CELO-USD",
        "AUDIO-USD","ENS-USD","LRC-USD","DYDX-USD","PERP-USD",
        "1INCH-USD","SUSHI-USD","YFI-USD","COMP-USD","BAL-USD",
        "OCEAN-USD","NMR-USD","REN-USD","UMA-USD","BNT-USD",
        "ALPHA-USD","REEF-USD","BAKE-USD","BURGER-USD","TWT-USD",
        "WIN-USD","BTT-USD","HOT-USD","DENT-USD","LOOM-USD",
    ],
}


def get_sp500_tickers() -> list[str]:
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(SP500_CSV_URL)
        resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    return [t.replace(".", "-") for t in df["Symbol"].tolist()]


def get_tickers(list_id: str, custom: list[str] | None = None, crypto_limit: int = 20) -> list[str]:
    if list_id == "sp500":
        return get_sp500_tickers()
    if list_id == "custom" and custom:
        return [t.upper().strip() for t in custom if t.strip()]
    if list_id == "crypto":
        return LISTS["crypto"][:max(1, crypto_limit)]
    return LISTS.get(list_id, [])


# ── Indicadores base ──────────────────────────────────────────────────────────

def _rsi_series(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_rsi(closes: pd.Series, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    return round(float(_rsi_series(closes, period).iloc[-1]), 2)


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
    pct_b = (price - b_lower) / (b_upper - b_lower)
    return round(b_upper, 2), round(b_lower, 2), round(float(pct_b), 3)


# ── Helper Prime internals ────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _atr_series(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    """Returns (plus_di, minus_di, adx) floats for the last bar."""
    if len(close) < period * 2:
        return None, None, None
    dm_up = high.diff().clip(lower=0)
    dm_dn = (-low.diff()).clip(lower=0)
    dm_plus  = dm_up.where(dm_up  > dm_dn, 0.0)
    dm_minus = dm_dn.where(dm_dn  > dm_up, 0.0)
    atr = _atr_series(high, low, close, period)
    safe_atr = atr.replace(0, np.nan)
    di_plus  = 100 * dm_plus.ewm(alpha=1 / period, adjust=False).mean()  / safe_atr
    di_minus = 100 * dm_minus.ewm(alpha=1 / period, adjust=False).mean() / safe_atr
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return float(di_plus.iloc[-1]), float(di_minus.iloc[-1]), float(adx.iloc[-1])


def _linreg_zone(close: pd.Series, period: int = 100):
    """Returns ('discount'|'fair'|'premium', lr_basis, lr_dev)."""
    if len(close) < period:
        return "fair", None, None
    y = close.values[-period:].astype(float)
    x = np.arange(period, dtype=float)
    m, b = np.polyfit(x, y, 1)
    lr_values = m * x + b
    lr_end = float(lr_values[-1])
    dev = float(np.std(y - lr_values)) * 2.0
    price = float(close.iloc[-1])
    if price <= lr_end - dev * 0.35:
        return "discount", lr_end, dev
    if price >= lr_end + dev * 0.35:
        return "premium", lr_end, dev
    return "fair", lr_end, dev


def _compute_poc(high: pd.Series, low: pd.Series, volume: pd.Series, period: int = 70, buckets: int = 15) -> float | None:
    """Volume-weighted Point of Control over the last `period` bars."""
    n = min(period, len(high))
    h = high.values[-n:].astype(float)
    l = low.values[-n:].astype(float)
    v = volume.values[-n:].astype(float)
    hi_r, lo_r = h.max(), l.min()
    if hi_r <= lo_r:
        return None
    dist = (hi_r - lo_r) / buckets
    counts = np.array([
        v[((l <= lo_r + i * dist) & (h >= lo_r + i * dist))].sum()
        for i in range(buckets)
    ])
    return float(lo_r + int(np.argmax(counts)) * dist)


# ── Helper Prime scoring ──────────────────────────────────────────────────────
#
# Port of the Pine Script Helper Prime indicator.
# Computes two symmetric scores (long/short) 0-100 based on:
#   EMA alignment (15), ADX/DI direction (15), RSI-50 momentum (15),
#   MTF proxy via daily EMA relationships (15), volatility filter (10),
#   structural zone: discount / near support / POC (15).
# Multi-timeframe (15m/1h/4h/1D) is approximated using 4 daily EMA signals.

def helper_prime_score(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    volume: pd.Series,
) -> dict:
    price = float(close.iloc[-1])

    # EMA 20 / 55 / 200
    e20 = float(_ema(close, 20).iloc[-1])
    e55 = float(_ema(close, 55).iloc[-1])
    e200 = float(_ema(close, 200).iloc[-1]) if len(close) >= 200 else None

    # ADX + DI
    plus_di, minus_di, adx = _compute_adx(high, low, close)
    adx_ok       = adx is not None and adx > 20
    dir_long_ok  = plus_di is not None and minus_di is not None and plus_di > minus_di
    dir_short_ok = plus_di is not None and minus_di is not None and minus_di > plus_di

    # RSI-50 momentum (current vs previous bar)
    rsi_s = _rsi_series(close)
    mom_cur  = float(rsi_s.iloc[-1]) - 50 if not np.isnan(rsi_s.iloc[-1]) else 0.0
    mom_prev = float(rsi_s.iloc[-2]) - 50 if len(rsi_s) >= 2 and not np.isnan(rsi_s.iloc[-2]) else mom_cur
    mom_rising  = mom_cur > mom_prev
    mom_falling = mom_cur < mom_prev

    # Volatility filter: current ATR vs 20-bar ATR average
    atr_s   = _atr_series(high, low, close)
    atr_cur = float(atr_s.iloc[-1])
    atr_sma = float(atr_s.iloc[-20:].mean()) if len(atr_s) >= 20 else atr_cur
    volatilidad_ok = atr_cur > atr_sma * 1.05

    # Linear regression zone
    zone, lr_end, lr_dev = _linreg_zone(close)

    # Support / Resistance proximity (20-bar swing high/low, excluding current bar)
    if len(high) >= 22:
        high_level = float(high.iloc[-22:-1].max())
        low_level  = float(low.iloc[-22:-1].min())
        near_support = abs(price - low_level)  <= atr_cur * 0.8
        near_resist  = abs(price - high_level) <= atr_cur * 0.8
    else:
        near_support = near_resist = False

    # Volume-weighted POC proximity
    poc_price = _compute_poc(high, low, volume)
    poc_support = poc_resist = False
    if poc_price is not None:
        n = min(70, len(high))
        hi_r = float(high.values[-n:].max())
        lo_r = float(low.values[-n:].min())
        bucket_size = max((hi_r - lo_r) / 15.0, 1e-10)
        poc_near    = abs(price - poc_price) <= bucket_size * 1.2
        poc_support = poc_near and price >= poc_price
        poc_resist  = poc_near and price <= poc_price

    long_zone  = (zone == "discount") or near_support or poc_support
    short_zone = (zone == "premium")  or near_resist  or poc_resist

    # MTF proxy: 4 daily-based signals mimicking 15m/1h/4h/1D EMA200 checks
    mtf_bull = sum([
        price > e20,
        price > e55,
        e200 is not None and price > e200,
        e20 > e55,
    ])
    mtf_bear  = 4 - mtf_bull
    min_align = 3

    # ── Long score (max 100) ──
    ls = 0
    ls += 15 if (e200 is not None and price > e200) else 0
    ls += 15 if (e200 is not None and e20 > e55 and e55 > e200) else (8 if e20 > e55 else 0)
    ls += 15 if (adx_ok and dir_long_ok)  else (8 if adx_ok else 0)
    ls += 15 if (mom_cur > 0 and mom_rising)  else (8 if mom_cur > 0 else 0)
    ls += 15 if mtf_bull >= min_align else (8 if mtf_bull == min_align - 1 else 0)
    ls += 10 if volatilidad_ok else 0
    ls += 15 if long_zone else 0

    # ── Short score (max 100) ──
    ss = 0
    ss += 15 if (e200 is not None and price < e200) else 0
    ss += 15 if (e200 is not None and e20 < e55 and e55 < e200) else (8 if e20 < e55 else 0)
    ss += 15 if (adx_ok and dir_short_ok) else (8 if adx_ok else 0)
    ss += 15 if (mom_cur < 0 and mom_falling) else (8 if mom_cur < 0 else 0)
    ss += 15 if mtf_bear >= min_align else (8 if mtf_bear == min_align - 1 else 0)
    ss += 10 if volatilidad_ok else 0
    ss += 15 if short_zone else 0

    best = max(ls, ss)
    direction = "LONG" if ls > ss else "SHORT" if ss > ls else "NEUTRAL"

    # ATR-based SL / TP levels (1.5× and 3.0×)
    sl = tp1 = tp2 = None
    if direction == "LONG":
        sl  = round(price - atr_cur * 1.5, 2)
        tp1 = round(price + atr_cur * 1.5, 2)
        tp2 = round(price + atr_cur * 3.0, 2)
    elif direction == "SHORT":
        sl  = round(price + atr_cur * 1.5, 2)
        tp1 = round(price - atr_cur * 1.5, 2)
        tp2 = round(price - atr_cur * 3.0, 2)

    return {
        "long_score":  ls,
        "short_score": ss,
        "best_score":  best,
        "direction":   direction,
        "zone":        zone,
        "adx":         round(adx, 1) if adx is not None else None,
        "mom":         round(mom_cur, 1),
        "poc":         round(poc_price, 2) if poc_price is not None else None,
        "sl":          sl,
        "tp1":         tp1,
        "tp2":         tp2,
    }


# ── Helper Pulse divergence engine ────────────────────────────────────────────
#
# Port of Helper Pulse: RSI-50 momentum oscillator with regular / hidden
# divergence detection and exhaustion signals.

def helper_pulse_signals(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    pivot_len: int = 3,
    min_bars_between: int = 5,
) -> dict:
    rsi_s = _rsi_series(close)
    mom = (rsi_s - 50).ewm(span=3, adjust=False).mean().fillna(0)
    mom_arr  = mom.values.astype(float)
    low_arr  = low.values.astype(float)
    high_arr = high.values.astype(float)

    def pivot_lows(arr, pl):
        out = []
        for i in range(pl, len(arr) - pl):
            if all(arr[i] <= arr[i - j] for j in range(1, pl + 1)) and \
               all(arr[i] <= arr[i + j] for j in range(1, pl + 1)):
                out.append(i)
        return out

    def pivot_highs(arr, pl):
        out = []
        for i in range(pl, len(arr) - pl):
            if all(arr[i] >= arr[i - j] for j in range(1, pl + 1)) and \
               all(arr[i] >= arr[i + j] for j in range(1, pl + 1)):
                out.append(i)
        return out

    lo_idxs = pivot_lows(mom_arr, pivot_len)
    hi_idxs = pivot_highs(mom_arr, pivot_len)

    TURN  = 15.0
    DELTA = 3.0
    signal = None

    # Bull divergences on pivot lows
    if len(lo_idxs) >= 2:
        i1, i2 = lo_idxs[-2], lo_idxs[-1]
        if i2 - i1 >= min_bars_between:
            o1, o2 = mom_arr[i1], mom_arr[i2]
            p1, p2 = low_arr[i1], low_arr[i2]
            if abs(o2 - o1) >= DELTA:
                # Regular bull: price lower low + momentum higher low (extreme zone)
                if p2 <= p1 and o2 > o1 and (o1 < -TURN or o2 < -TURN):
                    signal = "GIRO UP"
                # Hidden bull: price higher low + momentum lower low (< 0)
                elif o2 < 0 and p2 > p1 and o2 < o1:
                    signal = "SIGUE UP"

    # Bear divergences on pivot highs
    if signal is None and len(hi_idxs) >= 2:
        i1, i2 = hi_idxs[-2], hi_idxs[-1]
        if i2 - i1 >= min_bars_between:
            o1, o2 = mom_arr[i1], mom_arr[i2]
            p1, p2 = high_arr[i1], high_arr[i2]
            if abs(o2 - o1) >= DELTA:
                # Regular bear: price higher high + momentum lower high (extreme zone)
                if p2 >= p1 and o2 < o1 and (o1 > TURN or o2 > TURN):
                    signal = "GIRO DN"
                # Hidden bear: price lower high + momentum higher high (> 0)
                elif o2 > 0 and p2 < p1 and o2 > o1:
                    signal = "SIGUE DN"

    # Exhaustion (pivot in extreme zone without divergence)
    if signal is None:
        if hi_idxs and mom_arr[hi_idxs[-1]] >= TURN:
            signal = "AGOT. SUP"
        elif lo_idxs and mom_arr[lo_idxs[-1]] <= -TURN:
            signal = "AGOT. INF"

    mom_last = float(mom_arr[-1])
    mom_prev = float(mom_arr[-2]) if len(mom_arr) >= 2 else mom_last
    rising  = mom_last > mom_prev
    falling = mom_last < mom_prev

    POWER = 25.0
    if mom_last > POWER and rising:
        state = "ALCISTA FUERTE"
    elif mom_last > 0:
        state = "ALCISTA"
    elif mom_last < -POWER and falling:
        state = "BAJISTA FUERTE"
    elif mom_last < 0:
        state = "BAJISTA"
    else:
        state = "NEUTRAL"

    return {"pulse_signal": signal, "pulse_state": state, "mom": round(mom_last, 1)}


# ── Signal mapping ────────────────────────────────────────────────────────────

def prime_to_signal(direction: str, long_score: int, short_score: int) -> str:
    if direction == "LONG":
        if long_score >= 75: return "compra_fuerte"
        if long_score >= 60: return "compra"
        if long_score >= 40: return "neutral"
        return "neutral"
    if direction == "SHORT":
        if short_score >= 75: return "venta_fuerte"
        if short_score >= 60: return "venta"
        if short_score >= 40: return "neutral"
        return "neutral"
    return "neutral"


# ── Screener ──────────────────────────────────────────────────────────────────

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

            rsi                            = compute_rsi(close)
            macd_line, macd_sig, macd_hist = compute_macd(close)
            bb_upper, bb_lower, pct_b      = compute_bollinger(close)

            vol_avg   = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else None
            vol_today = float(volume.iloc[-1])
            vol_ratio = round(vol_today / vol_avg, 2) if vol_avg and vol_avg > 0 else None

            pct_from_high = round((price - high_52w) / high_52w * 100, 2)
            pct_from_low  = round((price - low_52w)  / low_52w  * 100, 2)
            pct_vs_ma200  = round((price - ma200) / ma200 * 100, 2) if ma200 else None
            pct_vs_ma50   = round((price - ma50)  / ma50  * 100, 2) if ma50  else None

            prime  = helper_prime_score(close, high, low, volume)
            pulse  = helper_pulse_signals(close, high, low)

            signal = prime_to_signal(prime["direction"], prime["long_score"], prime["short_score"])

            result = {
                "ticker":        ticker,
                "price":         round(price, 2),
                # Helper Prime
                "score":         prime["best_score"],
                "long_score":    prime["long_score"],
                "short_score":   prime["short_score"],
                "direction":     prime["direction"],
                "zone":          prime["zone"],
                "adx":           prime["adx"],
                "mom":           prime["mom"],
                "poc":           prime["poc"],
                "sl":            prime["sl"],
                "tp1":           prime["tp1"],
                "tp2":           prime["tp2"],
                # Helper Pulse
                "pulse_signal":  pulse["pulse_signal"],
                "pulse_state":   pulse["pulse_state"],
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
                # Momentum clásico (mantenidos para columnas existentes)
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

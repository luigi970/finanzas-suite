"""
GitHub Actions job: runs the screener and writes results to Cloudflare D1.
Usage: python run_job.py --list sp500 --crypto-limit 20
Env vars required: CF_API_TOKEN, CF_ACCOUNT_ID, CF_D1_DB_ID
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
from concurrent.futures import ThreadPoolExecutor

from screener import get_tickers, compute_all

CF_API = "https://api.cloudflare.com/client/v4"

# Mapeo symbol → CoinGecko ID para fallback
_CG_IDS = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin', 'SOL': 'solana',
    'XRP': 'ripple', 'ADA': 'cardano', 'AVAX': 'avalanche-2', 'DOGE': 'dogecoin',
    'TRX': 'tron', 'DOT': 'polkadot', 'LINK': 'chainlink', 'ATOM': 'cosmos',
    'LTC': 'litecoin', 'BCH': 'bitcoin-cash', 'NEAR': 'near', 'APT': 'aptos',
    'XLM': 'stellar', 'SHIB': 'shiba-inu', 'MATIC': 'matic-network',
    'UNI': 'uniswap', 'TON': 'the-open-network',
}

def fetch_crypto_prices(bases: list[str]) -> dict:
    """Precios en tiempo real con fallback chain: CoinGecko → CryptoCompare."""
    syms = [b.upper() for b in bases]

    # 1. CoinGecko — funciona desde GitHub Actions sin key
    try:
        ids = [_CG_IDS[s] for s in syms if s in _CG_IDS]
        id_to_sym = {v: k for k, v in _CG_IDS.items()}
        if ids:
            r = requests.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(ids)}&vs_currencies=usd",
                timeout=10, headers={"User-Agent": "maximos-screener/1.0"},
            )
            if r.status_code == 200:
                data = r.json()
                prices = {id_to_sym[cg_id]: float(pr["usd"]) for cg_id, pr in data.items() if "usd" in pr and cg_id in id_to_sym}
                if prices:
                    print(f"[prices] CoinGecko OK — {len(prices)} precios")
                    return prices
            else:
                print(f"[prices] CoinGecko HTTP {r.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[prices] CoinGecko error: {e}", file=sys.stderr)

    # 2. CryptoCompare — fallback (requiere key desde datacenter)
    try:
        r = requests.get(
            f"https://min-api.cryptocompare.com/data/pricemulti?fsyms={','.join(syms)}&tsyms=USD",
            timeout=10, headers={"User-Agent": "maximos-screener/1.0"},
        )
        if r.status_code == 200:
            data = r.json()
            prices = {sym: float(pr["USD"]) for sym, pr in data.items() if "USD" in pr}
            if prices:
                print(f"[prices] CryptoCompare OK — {len(prices)} precios")
                return prices
            print("[prices] CryptoCompare: respuesta vacía", file=sys.stderr)
        else:
            print(f"[prices] CryptoCompare HTTP {r.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[prices] CryptoCompare error: {e}", file=sys.stderr)

    print("[prices] Todos los proveedores fallaron", file=sys.stderr)
    return {}


def cf_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def d1_query(token: str, account_id: str, db_id: str, sql: str, params: list = None):
    url = f"{CF_API}/accounts/{account_id}/d1/database/{db_id}/query"
    body = {"sql": sql}
    if params:
        body["params"] = params
    resp = requests.post(url, headers=cf_headers(token), json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 error: {data.get('errors')}")
    return data["result"]


def create_run(token, account_id, db_id, list_id: str, total: int) -> int:
    now = datetime.now(timezone.utc).isoformat()
    result = d1_query(
        token, account_id, db_id,
        "INSERT INTO screener_runs (list_id, status, total, processed, started_at) VALUES (?, 'running', ?, 0, ?) RETURNING id",
        [list_id, total, now],
    )
    return result[0]["results"][0]["id"]


def finish_run(token, account_id, db_id, run_id: int, processed: int):
    now = datetime.now(timezone.utc).isoformat()
    d1_query(
        token, account_id, db_id,
        "UPDATE screener_runs SET status='done', processed=?, finished_at=? WHERE id=?",
        [processed, now, run_id],
    )


HISTORY_WINDOWS = [
    ("pct_5d",  3,  7),
    ("pct_10d", 8, 12),
    ("pct_20d", 17, 23),
]


def ensure_history_table(token, account_id, db_id):
    d1_query(token, account_id, db_id, """
        CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            signal TEXT NOT NULL,
            direction TEXT NOT NULL,
            score INTEGER NOT NULL,
            price REAL NOT NULL,
            recorded_at TEXT NOT NULL,
            pct_5d REAL,
            pct_10d REAL,
            pct_20d REAL,
            UNIQUE(list_id, ticker, recorded_at)
        )
    """)


def insert_history(token, account_id, db_id, list_id, today, results):
    for row in results:
        try:
            d1_query(token, account_id, db_id,
                "INSERT OR IGNORE INTO signal_history "
                "(list_id, ticker, signal, direction, score, price, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [list_id, row["ticker"], row["signal"], row["direction"],
                 row["score"], row["price"], today])
        except Exception as e:
            print(f"[history] Error {row['ticker']}: {e}", file=sys.stderr)


def update_history_prices(token, account_id, db_id, list_id, today, results):
    from datetime import timedelta
    today_dt = datetime.fromisoformat(today)
    price_map = {row["ticker"]: row["price"] for row in results}

    def do_update(col, date_from, date_to, ticker, price):
        try:
            d1_query(token, account_id, db_id,
                f"UPDATE signal_history SET {col} = ROUND((? - price) / price * 100, 2) "
                f"WHERE list_id = ? AND ticker = ? AND recorded_at BETWEEN ? AND ? AND {col} IS NULL",
                [price, list_id, ticker, date_from, date_to])
        except Exception:
            pass

    tasks = []
    for col, min_d, max_d in HISTORY_WINDOWS:
        date_from = (today_dt - timedelta(days=max_d)).date().isoformat()
        date_to   = (today_dt - timedelta(days=min_d)).date().isoformat()
        for ticker, price in price_map.items():
            tasks.append((col, date_from, date_to, ticker, price))

    with ThreadPoolExecutor(max_workers=5) as ex:
        for t in tasks:
            ex.submit(do_update, *t)


def upsert_result(token, account_id, db_id, run_id: int, list_id: str, row: dict):
    now = datetime.now(timezone.utc).isoformat()
    data_json = json.dumps(row, ensure_ascii=False)
    d1_query(
        token, account_id, db_id,
        """INSERT INTO screener_results (run_id, list_id, ticker, signal, score, data, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(list_id, ticker) DO UPDATE SET
               run_id=excluded.run_id, signal=excluded.signal, score=excluded.score,
               data=excluded.data, updated_at=excluded.updated_at""",
        [run_id, list_id, row["ticker"], row["signal"], row["score"], data_json, now],
    )


# ── Alertas por señal fuerte (push al celular vía ntfy.sh) ────────────────────
# Idea: el usuario arma una lista corta de tickers que le importan (desde la web de
# maximos, tabla alert_watchlist en D1). Cada vez que corre el screener, si alguno de
# esos tickers ENTRA o SALE de compra_fuerte/venta_fuerte respecto de su señal del día
# anterior, se manda un aviso al celular con un mensaje claro y las últimas noticias
# del propio ticker. Nunca debe romper el job principal — cualquier error acá se traga
# y se loguea, el screener ya guardó sus resultados antes de llegar a este punto.

STRONG_SIGNALS = {"compra_fuerte", "venta_fuerte"}

SIGNAL_LABELS = {
    "compra_fuerte": "COMPRA FUERTE",
    "compra":        "compra",
    "neutral":       "neutral",
    "venta":         "venta",
    "venta_fuerte":  "VENTA FUERTE",
}


def ensure_alert_watchlist_table(token, account_id, db_id):
    d1_query(token, account_id, db_id, """
        CREATE TABLE IF NOT EXISTS alert_watchlist (
            ticker TEXT PRIMARY KEY,
            added_at TEXT NOT NULL
        )
    """)


def get_alert_watchlist(token, account_id, db_id) -> set[str]:
    try:
        result = d1_query(token, account_id, db_id, "SELECT ticker FROM alert_watchlist")
        rows = result[0].get("results", []) if result else []
        return {r["ticker"] for r in rows}
    except Exception as e:
        print(f"[alerts] Error leyendo watchlist: {e}", file=sys.stderr)
        return set()


# ── Watchlist: cadencia configurable ────────────────────────────────────────────
# El workflow (watchlist-alerts.yml) corre cada hora en vez de una vez por día — más
# chances de esquivar el bloqueo intermitente de Binance a IPs de datacenter, y de
# paso el análisis se refresca más seguido. Pero no significa que TODA corrida deba
# analizar de verdad: el usuario configura desde el panel 🔔 Alertas cada cuánto (como
# mínimo cada 1 hora, igual a la cadencia del cron) y en qué rango horario — esta
# tabla guarda esa config y la marca de la última corrida real.

def ensure_alert_config_table(token, account_id, db_id):
    d1_query(token, account_id, db_id, """
        CREATE TABLE IF NOT EXISTS alert_watchlist_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            interval_minutes INTEGER NOT NULL DEFAULT 60,
            hour_from INTEGER NOT NULL DEFAULT 0,
            hour_to INTEGER NOT NULL DEFAULT 24,
            last_run_at TEXT
        )
    """)
    d1_query(token, account_id, db_id,
        "INSERT OR IGNORE INTO alert_watchlist_config (id, interval_minutes, hour_from, hour_to) "
        "VALUES (1, 60, 0, 24)")


def get_alert_config(token, account_id, db_id) -> dict:
    defaults = {"interval_minutes": 60, "hour_from": 0, "hour_to": 24, "last_run_at": None}
    try:
        result = d1_query(
            token, account_id, db_id,
            "SELECT interval_minutes, hour_from, hour_to, last_run_at FROM alert_watchlist_config WHERE id = 1",
        )
        rows = result[0].get("results", []) if result else []
        return rows[0] if rows else defaults
    except Exception as e:
        print(f"[alerts] Error leyendo config: {e}", file=sys.stderr)
        return defaults


def update_alert_config_last_run(token, account_id, db_id, when_iso: str):
    try:
        d1_query(token, account_id, db_id,
                 "UPDATE alert_watchlist_config SET last_run_at = ? WHERE id = 1", [when_iso])
    except Exception as e:
        print(f"[alerts] Error actualizando last_run_at: {e}", file=sys.stderr)


def is_watchlist_run_due(config: dict, now_utc: datetime) -> bool:
    """Argentina no tiene horario de verano desde 2009 — UTC-3 fijo, sin conversión
    con DST que pueda romperse con el tiempo."""
    art_hour = (now_utc.hour - 3) % 24
    hour_from = config.get("hour_from", 0)
    hour_to = config.get("hour_to", 24)
    in_window = (hour_from <= art_hour < hour_to) if hour_from < hour_to else (art_hour >= hour_from or art_hour < hour_to)
    if not in_window:
        return False

    last_run_at = config.get("last_run_at")
    if not last_run_at:
        return True
    try:
        elapsed_min = (now_utc - datetime.fromisoformat(last_run_at)).total_seconds() / 60
        return elapsed_min >= config.get("interval_minutes", 60)
    except Exception:
        return True


def get_previous_signal(token, account_id, db_id, ticker: str, today: str) -> str | None:
    """Última señal registrada para este ticker ANTES de hoy (para detectar el cambio)."""
    try:
        result = d1_query(
            token, account_id, db_id,
            "SELECT signal FROM signal_history WHERE ticker = ? AND recorded_at < ? "
            "ORDER BY recorded_at DESC LIMIT 1",
            [ticker, today],
        )
        rows = result[0].get("results", []) if result else []
        return rows[0]["signal"] if rows else None
    except Exception as e:
        print(f"[alerts] Error leyendo señal previa de {ticker}: {e}", file=sys.stderr)
        return None


def fetch_ticker_news(ticker: str, limit: int = 2) -> list[str]:
    """Últimos titulares del ticker (yfinance) — mismo dato que ya se muestra en la
    pestaña Noticias del modal de cada ticker en la web."""
    try:
        import yfinance as yf
        raw = yf.Ticker(ticker).news or []
        titles = []
        for item in raw[:limit]:
            content = item.get("content", {})
            title = content.get("title") or item.get("title", "")
            if title:
                titles.append(title)
        return titles
    except Exception:
        return []


def build_alert_message(ticker: str, name: str, prev_signal: str, new_signal: str, price: float) -> tuple[str, str]:
    """Arma título + cuerpo del aviso — tiene que ser corto, claro y fácil de leer en
    una notificación de celular, no un volcado técnico."""
    display = f"{name} ({ticker})" if name else ticker
    entering_buy  = new_signal == "compra_fuerte" and prev_signal != "compra_fuerte"
    entering_sell = new_signal == "venta_fuerte" and prev_signal != "venta_fuerte"

    if entering_buy:
        emoji, headline = "🚀", f"{ticker} entró en zona de COMPRA FUERTE"
        body = f"{display} está cotizando a USD {price:,.2f} y el sistema le puso la señal más fuerte de compra. Vale la pena que le eches un vistazo."
    elif entering_sell:
        emoji, headline = "⚠️", f"{ticker} entró en zona de VENTA FUERTE"
        body = f"{display} está cotizando a USD {price:,.2f} y el sistema detectó la señal más fuerte de venta. Si lo tenés en cartera, prestale atención."
    elif prev_signal == "compra_fuerte":
        emoji, headline = "📉", f"{ticker} salió de COMPRA FUERTE"
        body = f"{display} se enfrió — ahora está en {SIGNAL_LABELS.get(new_signal, new_signal)}, cotizando a USD {price:,.2f}."
    else:  # prev_signal == "venta_fuerte"
        emoji, headline = "📈", f"{ticker} salió de VENTA FUERTE"
        body = f"{display} mejoró — ahora está en {SIGNAL_LABELS.get(new_signal, new_signal)}, cotizando a USD {price:,.2f}."

    news = fetch_ticker_news(ticker)
    if news:
        body += "\n\n📰 " + "\n📰 ".join(news)

    return f"{emoji} {headline}", body


def send_ntfy_alert(topic: str, title: str, body: str):
    try:
        r = requests.post(
            f"https://ntfy.sh/{topic}",
            data=body.encode("utf-8"),
            headers={"Title": title.encode("utf-8"), "Priority": "default"},
            timeout=10,
        )
        if r.status_code == 200:
            # título en ASCII-safe para el log — emojis/tildes pueden romper la consola
            # en algunos entornos (visto en Windows local); ntfy.sh ya los recibió bien.
            print(f"[alerts] Enviado OK ({r.status_code})".encode("ascii", "replace").decode())
        else:
            print(f"[alerts] ntfy.sh HTTP {r.status_code}: {r.text[:200]}".encode("ascii", "replace").decode(), file=sys.stderr)
    except Exception as e:
        print(f"[alerts] Error enviando a ntfy.sh: {type(e).__name__}: {e}".encode("ascii", "replace").decode(), file=sys.stderr)


def check_and_send_alerts(token, account_id, db_id, today, results):
    ntfy_topic = os.environ.get("NTFY_TOPIC", "")
    if not ntfy_topic:
        return  # alertas no configuradas — no es un error, simplemente no está activado

    try:
        ensure_alert_watchlist_table(token, account_id, db_id)
        watched = get_alert_watchlist(token, account_id, db_id)
        if not watched:
            return

        for row in results:
            ticker = row.get("ticker")
            if ticker not in watched:
                continue
            new_signal = row.get("signal")
            prev_signal = get_previous_signal(token, account_id, db_id, ticker, today)
            if prev_signal is None or prev_signal == new_signal:
                continue
            was_strong = prev_signal in STRONG_SIGNALS
            is_strong = new_signal in STRONG_SIGNALS
            if not was_strong and not is_strong:
                continue  # cambió de señal, pero nunca pasó por una zona fuerte — no es lo que queremos avisar
            title, body = build_alert_message(ticker, row.get("name", ""), prev_signal, new_signal, row.get("price", 0))
            send_ntfy_alert(ntfy_topic, title, body)
    except Exception as e:
        print(f"[alerts] Error general en chequeo de alertas: {e}", file=sys.stderr)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", default="sp500", dest="list_id")
    parser.add_argument("--crypto-limit", type=int, default=20)
    parser.add_argument("--custom-tickers", default="", dest="custom_tickers")
    parser.add_argument("--force", action="store_true",
                         help="Ignora el intervalo/rango horario configurado para watchlist "
                              "(usado por el botón manual y por workflow_dispatch)")
    args = parser.parse_args()

    token = os.environ.get("CF_API_TOKEN") or os.environ.get("CLOUDFLARE_API_TOKEN")
    account_id = os.environ.get("CF_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    db_id = os.environ.get("CF_D1_DB_ID", "b2ff197f-e7e2-47f1-a4a6-5d5ee23e7aa0")

    if not token or not account_id:
        print("ERROR: CF_API_TOKEN y CF_ACCOUNT_ID son requeridos", file=sys.stderr)
        sys.exit(1)

    # "watchlist" no es una lista fija de screener.py — son los tickers que el usuario
    # cargó a mano en la sección 🔔 Alertas de la web (tabla alert_watchlist en D1),
    # para que CUALQUIER ticker que le importe (esté o no en sp500/nasdaq100/etc.) se
    # analice todos los días y pueda disparar una alerta. Sin esto, un ticker fuera de
    # las 6 listas fijas nunca se procesa y nunca puede avisar nada.
    if args.list_id == "watchlist":
        ensure_alert_watchlist_table(token, account_id, db_id)
        ensure_alert_config_table(token, account_id, db_id)
        tickers = sorted(get_alert_watchlist(token, account_id, db_id))
        if not tickers:
            print("[job] Lista de alertas vacía — nada que analizar hoy.")
            return
        if not args.force:
            config = get_alert_config(token, account_id, db_id)
            now_utc = datetime.now(timezone.utc)
            if not is_watchlist_run_due(config, now_utc):
                print(f"[job] Watchlist: todavía no toca según la config del panel ({config}) — se sale sin analizar.")
                return
    else:
        custom = [t.strip() for t in args.custom_tickers.split(",") if t.strip()] if args.custom_tickers else None
        tickers = get_tickers(args.list_id, custom=custom, crypto_limit=args.crypto_limit)
    print(f"[job] Lista: {args.list_id} — {len(tickers)} tickers")

    # Custom/watchlist: clear stale results so only the tickers actuales aparecen (si se
    # sacó un ticker de la lista de alertas, que no quede su fila vieja para siempre)
    if args.list_id in ("custom", "watchlist"):
        d1_query(token, account_id, db_id,
                 "DELETE FROM screener_results WHERE list_id = ?", [args.list_id])
        print("[job] Resultados custom anteriores eliminados")

    run_id = create_run(token, account_id, db_id, args.list_id, len(tickers))
    print(f"[job] Run ID: {run_id}")

    results = []
    errors = []

    def on_result(row):
        results.append(row)

    def on_error(ticker, err):
        errors.append((ticker, str(err)))

    t0 = time.time()
    compute_all(tickers, on_result=on_result, on_error=on_error)
    elapsed = time.time() - t0
    print(f"[job] Screener terminó en {elapsed:.1f}s — {len(results)} OK, {len(errors)} errores")

    # Crypto: enriquecer precios con fallback chain antes de guardar en D1
    if args.list_id == "crypto":
        bases = [t.replace("-USD", "").upper() for t in tickers if t.endswith("-USD")]
        price_map = fetch_crypto_prices(bases)
        if price_map:
            if results:
                for r in results:
                    base = r.get("ticker", "").replace("-USD", "").upper()
                    if base in price_map:
                        r["price"] = round(price_map[base], 4)
            else:
                # yfinance falló — actualizar solo price en D1 existente
                print("[prices] yfinance falló — actualizando precios en D1 existente")
                existing = d1_query(token, account_id, db_id,
                    "SELECT ticker, data FROM screener_results WHERE list_id = ?",
                    [args.list_id])
                rows = existing[0].get("results", []) if existing else []
                now = datetime.now(timezone.utc).isoformat()
                updated = 0
                for row in rows:
                    ticker_key = row["ticker"]
                    base = ticker_key.replace("-USD", "").upper()
                    if base in price_map:
                        data = json.loads(row["data"])
                        data["price"] = round(price_map[base], 4)
                        d1_query(token, account_id, db_id,
                            "UPDATE screener_results SET data = ?, updated_at = ? WHERE list_id = ? AND ticker = ?",
                            [json.dumps(data, ensure_ascii=False), now, args.list_id, ticker_key])
                        updated += 1
                print(f"[prices] {updated}/{len(rows)} precios actualizados en D1")

    for row in results:
        try:
            upsert_result(token, account_id, db_id, run_id, args.list_id, row)
        except Exception as e:
            print(f"[job] ERROR upsert {row.get('ticker')}: {e}", file=sys.stderr)

    finish_run(token, account_id, db_id, run_id, len(results))
    print(f"[job] Done. Run {run_id} marcado como completado.")

    today = datetime.now(timezone.utc).date().isoformat()
    ensure_history_table(token, account_id, db_id)
    insert_history(token, account_id, db_id, args.list_id, today, results)
    update_history_prices(token, account_id, db_id, args.list_id, today, results)
    print(f"[history] {len(results)} registros insertados/actualizados para {today}")

    check_and_send_alerts(token, account_id, db_id, today, results)

    if args.list_id == "watchlist":
        update_alert_config_last_run(token, account_id, db_id, datetime.now(timezone.utc).isoformat())

    if errors:
        print(f"[job] Tickers con error: {[t for t, _ in errors[:10]]}")


if __name__ == "__main__":
    main()

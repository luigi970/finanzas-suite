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
    """Precios en tiempo real con fallback chain: CryptoCompare → CoinGecko."""
    syms = [b.upper() for b in bases]

    # 1. CryptoCompare — sin geo-blocking desde data centers
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

    # 2. CoinGecko — API pública sin key
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


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", default="sp500", dest="list_id")
    parser.add_argument("--crypto-limit", type=int, default=20)
    parser.add_argument("--custom-tickers", default="", dest="custom_tickers")
    args = parser.parse_args()

    token = os.environ.get("CF_API_TOKEN") or os.environ.get("CLOUDFLARE_API_TOKEN")
    account_id = os.environ.get("CF_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    db_id = os.environ.get("CF_D1_DB_ID", "b2ff197f-e7e2-47f1-a4a6-5d5ee23e7aa0")

    if not token or not account_id:
        print("ERROR: CF_API_TOKEN y CF_ACCOUNT_ID son requeridos", file=sys.stderr)
        sys.exit(1)

    custom = [t.strip() for t in args.custom_tickers.split(",") if t.strip()] if args.custom_tickers else None
    tickers = get_tickers(args.list_id, custom=custom, crypto_limit=args.crypto_limit)
    print(f"[job] Lista: {args.list_id} — {len(tickers)} tickers")

    # Custom list: clear stale results so only the requested tickers appear
    if args.list_id == "custom":
        d1_query(token, account_id, db_id,
                 "DELETE FROM screener_results WHERE list_id = 'custom'")
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

    if errors:
        print(f"[job] Tickers con error: {[t for t, _ in errors[:10]]}")


if __name__ == "__main__":
    main()

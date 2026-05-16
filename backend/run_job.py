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

from screener import get_tickers, compute_all

CF_API = "https://api.cloudflare.com/client/v4"


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

    for row in results:
        try:
            upsert_result(token, account_id, db_id, run_id, args.list_id, row)
        except Exception as e:
            print(f"[job] ERROR upsert {row.get('ticker')}: {e}", file=sys.stderr)

    finish_run(token, account_id, db_id, run_id, len(results))
    print(f"[job] Done. Run {run_id} marcado como completado.")

    if errors:
        print(f"[job] Tickers con error: {[t for t, _ in errors[:10]]}")


if __name__ == "__main__":
    main()

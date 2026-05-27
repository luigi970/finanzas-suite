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


# ── ntfy alerts ───────────────────────────────────────────────────────────────

SIGNAL_RANK = {"compra_fuerte": 4, "compra": 3, "neutral": 2, "venta": 1, "venta_fuerte": 0}
SIGNAL_EMOJI = {"compra_fuerte": "🟢", "compra": "🟡", "neutral": "⚪", "venta": "🟠", "venta_fuerte": "🔴"}
SIGNAL_TAGS  = {"compra_fuerte": "chart_increasing", "compra": "chart_with_upwards_trend",
                "venta_fuerte": "chart_decreasing", "venta": "chart_with_downwards_trend", "neutral": "white_circle"}


def _fetch_prev_signals(token, account_id, db_id, list_id) -> dict:
    try:
        result = d1_query(token, account_id, db_id,
                          "SELECT ticker, signal, score FROM screener_results WHERE list_id = ?",
                          [list_id])
        rows = result[0]["results"]
        return {r["ticker"]: r["signal"] for r in rows}
    except Exception:
        return {}


def _is_notable(old: str, new: str) -> bool:
    if old == new:
        return False
    return (
        (old == "neutral" and new in ("compra", "compra_fuerte", "venta", "venta_fuerte")) or
        (old == "compra"  and new == "compra_fuerte") or
        (old == "venta"   and new == "venta_fuerte") or
        (new == "neutral" and old in ("compra", "compra_fuerte", "venta", "venta_fuerte"))
    )


def _short_ai_rec(row: dict, groq_key: str) -> str:
    if not groq_key:
        return ""
    try:
        prompt = (
            f"Sos un analista técnico. Respondé en máximo 2 oraciones en español rioplatense, sin markdown.\n"
            f"Ticker: {row['ticker']} | Señal: {row['signal']} | Score: {row['score']} | "
            f"Zona: {row.get('zone','?')} | RSI: {row.get('rsi','?')} | "
            f"Vol ratio: {row.get('vol_ratio','?')} | SL: {row.get('sl','?')} | TP1: {row.get('tp1','?')}\n"
            f"Explicá brevemente por qué cambió la señal y qué debería hacer el trader."
        )
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 100, "temperature": 0.3},
            timeout=15,
        )
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[ntfy] AI error: {e}", file=sys.stderr)
    return ""


def _send_ntfy(topic: str, title: str, body: str, click_url: str, priority: str, tag: str):
    from urllib.parse import quote
    headers = {
        "Title": quote(title, safe=" .,:/!?-_()[]"),
        "Priority": priority,
        "Tags": tag,
    }
    if click_url:
        headers["Click"] = click_url
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), headers=headers, timeout=10)
    except Exception as e:
        print(f"[ntfy] Error enviando: {e}", file=sys.stderr)


def send_alerts(prev: dict, results: list, groq_key: str, ntfy_topic: str, pages_url: str):
    if not ntfy_topic:
        return
    changes = [(r, prev.get(r["ticker"], "neutral"), r["signal"])
               for r in results if _is_notable(prev.get(r["ticker"], "neutral"), r["signal"])]
    if not changes:
        print("[ntfy] Sin cambios de señal relevantes.")
        return
    print(f"[ntfy] {len(changes)} cambio(s) detectado(s).")
    for row, old_sig, new_sig in changes:
        ticker = row["ticker"]
        ai_text = _short_ai_rec(row, groq_key)
        arrow = "↑" if SIGNAL_RANK.get(new_sig, 2) > SIGNAL_RANK.get(old_sig, 2) else "↓"
        title = f"{ticker}: {new_sig.replace('_', ' ')} {arrow}"
        lines = [
            f"{SIGNAL_EMOJI.get(new_sig, '⚪')} {old_sig} → {new_sig} | Score {row['score']} | {str(row.get('zone','?')).upper()}",
        ]
        if ai_text:
            lines.append(ai_text)
        sl  = row.get("sl")
        tp1 = row.get("tp1")
        if sl and tp1:
            lines.append(f"SL {sl} | TP1 {tp1}")
        click_url = f"{pages_url}/?ticker={ticker}" if pages_url else ""
        priority = "high" if "fuerte" in new_sig else "default"
        _send_ntfy(ntfy_topic, title, "\n".join(lines), click_url, priority, SIGNAL_TAGS.get(new_sig, "white_circle"))
        print(f"[ntfy] {ticker}: {old_sig} → {new_sig}")
        time.sleep(0.5)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", default="sp500", dest="list_id")
    parser.add_argument("--crypto-limit", type=int, default=20)
    parser.add_argument("--custom-tickers", default="", dest="custom_tickers")
    parser.add_argument("--test-ntfy", action="store_true", dest="test_ntfy")
    args = parser.parse_args()

    if args.test_ntfy:
        ntfy_topic = os.environ.get("NTFY_TOPIC", "")
        pages_url = os.environ.get("PAGES_URL", "")
        if not ntfy_topic:
            print("ERROR: NTFY_TOPIC no configurado", file=sys.stderr)
            sys.exit(1)
        _send_ntfy(
            ntfy_topic,
            title="maximos - prueba de notificacion",
            body="Si ves esto, las alertas funcionan correctamente.",
            click_url=pages_url or "",
            priority="default",
            tag="white_check_mark",
        )
        print(f"[ntfy] Notificación de prueba enviada a topic '{ntfy_topic}'")
        sys.exit(0)

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

    # Guardar señales anteriores antes de sobreescribir (para alertas)
    prev_signals = _fetch_prev_signals(token, account_id, db_id, args.list_id) if args.list_id != "custom" else {}

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

    today = datetime.now(timezone.utc).date().isoformat()
    ensure_history_table(token, account_id, db_id)
    insert_history(token, account_id, db_id, args.list_id, today, results)
    update_history_prices(token, account_id, db_id, args.list_id, today, results)
    print(f"[history] {len(results)} registros insertados/actualizados para {today}")

    # Alertas ntfy
    send_alerts(
        prev_signals, results,
        groq_key=os.environ.get("GROQ_API_KEY", ""),
        ntfy_topic=os.environ.get("NTFY_TOPIC", ""),
        pages_url=os.environ.get("PAGES_URL", ""),
    )

    if errors:
        print(f"[job] Tickers con error: {[t for t, _ in errors[:10]]}")


if __name__ == "__main__":
    main()

import json


async def get_latest_run(db, list_id: str) -> dict | None:
    cursor = await db.prepare(
        "SELECT id, list_id, status, total, processed, started_at, finished_at "
        "FROM screener_runs WHERE list_id = ? ORDER BY started_at DESC LIMIT 1"
    ).bind(list_id).all()
    for row in cursor.results:
        return row.to_py()
    return None


async def get_results(db, list_id: str, signal: str | None = None) -> list[dict]:
    # updated_at es cuándo se calculó de verdad ese ticker por última vez — si un
    # proveedor de datos falla para un ticker puntual (ver fallback Binance/Coinbase/
    # Kraken en screener.py), su fila en D1 queda con el valor de un run anterior en vez
    # de desaparecer, así que sin esto no habría forma de distinguir un dato fresco de
    # uno viejo que se arrastra. Se inyecta en el dict en vez de venir dentro de `data`
    # porque `data` es el JSON tal cual lo armó run_job.py, sin este campo.
    if signal and signal != "all":
        cursor = await db.prepare(
            "SELECT data, updated_at FROM screener_results WHERE list_id = ? AND signal = ? ORDER BY score DESC"
        ).bind(list_id, signal).all()
    else:
        cursor = await db.prepare(
            "SELECT data, updated_at FROM screener_results WHERE list_id = ? ORDER BY score DESC"
        ).bind(list_id).all()

    out = []
    for row in cursor.results:
        try:
            py_row = row.to_py()
            parsed = json.loads(py_row["data"])
            parsed["updated_at"] = py_row.get("updated_at")
            out.append(parsed)
        except Exception:
            pass
    return out


async def get_lists_meta(db) -> list[dict]:
    cursor = await db.prepare(
        "SELECT list_id, COUNT(*) as count FROM screener_results GROUP BY list_id"
    ).all()
    return [row.to_py() for row in cursor.results]


async def get_history(db, list_id: str, ticker: str, limit: int = 90) -> list[dict]:
    cursor = await db.prepare(
        "SELECT ticker, signal, direction, score, price, recorded_at, pct_5d, pct_10d, pct_20d "
        "FROM signal_history WHERE list_id = ? AND ticker = ? ORDER BY recorded_at DESC LIMIT ?"
    ).bind(list_id, ticker, limit).all()
    return [row.to_py() for row in cursor.results]

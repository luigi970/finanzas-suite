import json


async def get_latest_run(db, list_id: str) -> dict | None:
    result = await db.prepare(
        "SELECT id, list_id, status, total, processed, started_at, finished_at "
        "FROM screener_runs WHERE list_id = ? ORDER BY started_at DESC LIMIT 1"
    ).bind(list_id).first()
    if result is None:
        return None
    return dict(result)


async def get_results(db, list_id: str, signal: str | None = None) -> list[dict]:
    if signal and signal != "all":
        cursor = await db.prepare(
            "SELECT data FROM screener_results WHERE list_id = ? AND signal = ? ORDER BY score DESC"
        ).bind(list_id, signal).all()
    else:
        cursor = await db.prepare(
            "SELECT data FROM screener_results WHERE list_id = ? ORDER BY score DESC"
        ).bind(list_id).all()

    rows = cursor.results
    out = []
    for row in rows:
        try:
            out.append(json.loads(row["data"]))
        except Exception:
            pass
    return out


async def get_lists_meta(db) -> list[dict]:
    cursor = await db.prepare(
        "SELECT list_id, COUNT(*) as count FROM screener_results GROUP BY list_id"
    ).all()
    return [dict(r) for r in cursor.results]

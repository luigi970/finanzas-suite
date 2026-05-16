import json

from workers import Response, fetch

from storage.db import get_latest_run, get_results, get_lists_meta

ALLOWED_ORIGINS = {
    "https://maximos.pages.dev",
    "http://localhost:5173",
    "http://localhost:8000",
}

LIST_IDS = {"sp500", "nasdaq100", "etfs", "adrs_arg", "crypto", "custom"}


def _cors(request) -> dict:
    try:
        origin = request.headers.get("Origin") or ""
    except Exception:
        origin = ""
    if origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
            "Vary": "Origin",
        }
    return {}


def _route(url: str) -> str:
    parts = url.split("/", 3)
    if len(parts) < 4:
        return "/"
    return "/" + parts[3].split("?")[0].rstrip("/") or "/"


def _qs(url: str) -> dict:
    if "?" not in url:
        return {}
    pairs = url.split("?", 1)[1].split("&")
    out = {}
    for p in pairs:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k] = v
    return out


async def on_fetch(request, env):
    method = request.method
    path = _route(request.url)
    qs = _qs(request.url)
    cors = _cors(request)

    def _j(payload: dict, status: int = 200) -> Response:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        headers.update(cors)
        return Response(json.dumps(payload, ensure_ascii=False), status=status, headers=headers)

    if method == "OPTIONS":
        return _j({"ok": True})

    if method == "GET" and path == "/":
        return Response("maximos Worker activo")

    if method == "GET" and path == "/health":
        return _j({"status": "ok"})

    if not hasattr(env, "maximos_db"):
        return _j({"error": "D1 no bindeada"}, status=500)

    db = env.maximos_db

    # GET /api/status?list_id=sp500
    if method == "GET" and path == "/api/status":
        list_id = qs.get("list_id", "sp500")
        run = await get_latest_run(db, list_id)
        if run is None:
            return _j({"status": "idle", "list_id": list_id, "processed": 0, "total_tickers": 0})
        return _j({
            "status": run.get("status", "idle"),
            "list_id": list_id,
            "processed": run.get("processed", 0),
            "total_tickers": run.get("total", 0),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
        })

    # GET /api/stocks?list_id=sp500&signal=all
    if method == "GET" and path == "/api/stocks":
        list_id = qs.get("list_id", "sp500")
        signal = qs.get("signal", "all")
        try:
            rows = await get_results(db, list_id, signal if signal != "all" else None)
        except Exception as e:
            return _j({"error": str(e)}, status=500)
        return _j({"status": "ready", "stocks": rows, "total": len(rows), "list_id": list_id})

    # GET /api/lists
    if method == "GET" and path == "/api/lists":
        try:
            meta = await get_lists_meta(db)
        except Exception as e:
            return _j({"error": str(e)}, status=500)
        return _j({"lists": meta})

    # POST /api/refresh — triggers GitHub Actions workflow via repository_dispatch
    if method == "POST" and path == "/api/refresh":
        try:
            body_text = await request.text()
            body = json.loads(body_text) if body_text else {}
        except Exception:
            body = {}

        list_id = body.get("list_id", "sp500")
        crypto_limit = body.get("crypto_limit", 20)

        gh_token = getattr(env, "GH_PAT", None)
        gh_repo = getattr(env, "GH_REPO", "luigi970/maximos")

        if not gh_token:
            return _j({"error": "GH_PAT no configurado"}, status=500)

        payload = json.dumps({
            "event_type": "run-screener",
            "client_payload": {"list_id": list_id, "crypto_limit": crypto_limit},
        })

        try:
            resp = await fetch(
                f"https://api.github.com/repos/{gh_repo}/dispatches",
                {
                    "method": "POST",
                    "headers": {
                        "Authorization": f"Bearer {gh_token}",
                        "Accept": "application/vnd.github+json",
                        "Content-Type": "application/json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    "body": payload,
                },
            )
            if resp.status == 204:
                return _j({"ok": True, "list_id": list_id, "message": "Job disparado"})
            err_text = await resp.text()
            return _j({"error": f"GitHub API {resp.status}: {err_text}"}, status=500)
        except Exception as e:
            return _j({"error": f"fetch error: {type(e).__name__}: {e}"}, status=500)

    return _j({"error": "not found"}, status=404)

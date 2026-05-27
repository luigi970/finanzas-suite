import json

from workers import Response, fetch

from providers.cf_ai import analyze as cf_analyze
from providers.groq import analyze as groq_analyze
from providers.gemini import analyze as gemini_analyze
from storage.db import get_latest_run, get_results, get_lists_meta, get_history

ALLOWED_ORIGINS = {
    "https://maximos.pages.dev",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8000",
    "http://localhost:8001",
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
        try:
            run = await get_latest_run(db, list_id)
        except Exception as e:
            return _j({"error": str(e), "status": "idle", "list_id": list_id}, status=500)
        if run is None:
            return _j({"status": "idle", "list_id": list_id, "processed": 0, "total_tickers": 0})
        status_map = {"done": "ready", "running": "loading"}
        api_status = status_map.get(run.get("status", "idle"), "idle")
        finished_at = run.get("finished_at")
        last_updated = None
        if finished_at:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                last_updated = int(dt.timestamp())
            except Exception:
                pass
        return _j({
            "status": api_status,
            "list_id": list_id,
            "processed": run.get("processed", 0),
            "total_tickers": run.get("total", 0),
            "started_at": finished_at,
            "finished_at": finished_at,
            "last_updated": last_updated,
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

    # GET /api/history?list_id=sp500&ticker=AAPL
    if method == "GET" and path == "/api/history":
        list_id = qs.get("list_id", "sp500")
        ticker  = qs.get("ticker", "").upper()
        if not ticker:
            return _j({"history": []})
        try:
            rows = await get_history(db, list_id, ticker)
        except Exception as e:
            return _j({"history": [], "error": str(e)})
        return _j({"history": rows})

    # GET /api/lists
    if method == "GET" and path == "/api/lists":
        try:
            meta = await get_lists_meta(db)
        except Exception as e:
            return _j({"error": str(e)}, status=500)
        return _j({"lists": meta})

    # POST /api/analyze — AI recommendation for a single ticker
    if method == "POST" and path == "/api/analyze":
        try:
            body_text = await request.text()
            ticker_data = json.loads(body_text) if body_text else {}
        except Exception:
            return _j({"error": "body inválido"}, status=400)

        if not ticker_data.get("ticker"):
            return _j({"error": "falta 'ticker'"}, status=400)

        cf_ai = getattr(env, "AI", None)
        groq_key = getattr(env, "GROQ_API_KEY", None)
        gemini_key = getattr(env, "GOOGLE_API_KEY", None)

        if not cf_ai and not groq_key and not gemini_key:
            return _j({"error": "No hay proveedor de IA configurado"}, status=500)

        last_err = None
        for provider, arg in [(cf_analyze, cf_ai), (groq_analyze, groq_key), (gemini_analyze, gemini_key)]:
            if not arg:
                continue
            try:
                recommendation = await provider(ticker_data, arg)
                return _j({"ticker": ticker_data["ticker"], "recommendation": recommendation})
            except Exception as e:
                last_err = str(e)

        return _j({"error": last_err or "Error desconocido"}, status=500)

    # POST /api/refresh — triggers GitHub Actions workflow via repository_dispatch
    if method == "POST" and path == "/api/refresh":
        try:
            body_text = await request.text()
            body = json.loads(body_text) if body_text else {}
        except Exception:
            body = {}

        list_id = body.get("list_id", "sp500")
        crypto_limit = body.get("crypto_limit", 20)
        custom_tickers = body.get("custom", [])

        gh_token = getattr(env, "GH_PAT", None)
        gh_repo = getattr(env, "GH_REPO", "luigi970/maximos")

        if not gh_token:
            return _j({"error": "GH_PAT no configurado"}, status=500)

        payload = json.dumps({
            "event_type": "run-screener",
            "client_payload": {
                "list_id": list_id,
                "crypto_limit": crypto_limit,
                "custom_tickers": ",".join(custom_tickers) if custom_tickers else "",
            },
        })

        try:
            resp = await fetch(
                f"https://api.github.com/repos/{gh_repo}/dispatches",
                method="POST",
                headers={
                    "Authorization": f"Bearer {gh_token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "maximos-worker/1.0",
                },
                body=payload,
            )
            if resp.status == 204:
                return _j({"ok": True, "list_id": list_id, "message": "Job disparado"})
            err_text = await resp.text()
            return _j({"error": f"GitHub API {resp.status}: {err_text}"}, status=500)
        except Exception as e:
            return _j({"error": f"{type(e).__name__}: {e}"}, status=500)

    # GET /api/info?ticker=AAPL — company fundamentals via Yahoo Finance
    if method == "GET" and path == "/api/info":
        ticker = qs.get("ticker", "").upper()
        if not ticker:
            return _j({"info": {}})
        try:
            modules = "assetProfile,summaryDetail,defaultKeyStatistics,financialData,quoteType,calendarEvents"
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}&lang=en-US&region=US"
            resp = await fetch(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            })
            data = json.loads(await resp.text())
            results = (data.get("quoteSummary") or {}).get("result") or []
            if not results:
                return _j({"info": {}})
            r = results[0]
            def _raw(d, k):
                v = d.get(k)
                return v.get("raw") if isinstance(v, dict) else v
            profile = r.get("assetProfile") or {}
            stats   = r.get("defaultKeyStatistics") or {}
            summary = r.get("summaryDetail") or {}
            fin     = r.get("financialData") or {}
            qt      = r.get("quoteType") or {}
            cal     = r.get("calendarEvents") or {}

            earnings_date = None
            earnings_list = (cal.get("earnings") or {}).get("earningsDate") or []
            if earnings_list:
                first = earnings_list[0]
                earnings_date = first.get("fmt") if isinstance(first, dict) else str(first)

            return _j({"info": {
                "name":              qt.get("longName") or qt.get("shortName") or ticker,
                "sector":            profile.get("sector") or "",
                "industry":          profile.get("industry") or "",
                "market_cap":        _raw(summary, "marketCap"),
                "trailing_pe":       _raw(summary, "trailingPE"),
                "forward_pe":        _raw(stats,   "forwardPE"),
                "beta":              _raw(summary, "beta"),
                "dividend_yield":    _raw(summary, "dividendYield"),
                "target_price":      _raw(fin,     "targetMeanPrice"),
                "target_high":       _raw(fin,     "targetHighPrice"),
                "target_low":        _raw(fin,     "targetLowPrice"),
                "recommendation_key": fin.get("recommendationKey"),
                "analyst_count":     _raw(fin,     "numberOfAnalystOpinions"),
                "earnings_date":     earnings_date,
            }})
        except Exception as e:
            return _j({"info": {}, "error": str(e)})

    # GET /api/news?ticker=AAPL — Yahoo Finance news search
    if method == "GET" and path == "/api/news":
        ticker = qs.get("ticker", "").upper()
        if not ticker:
            return _j({"news": []})
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={ticker}&newsCount=15&quotesCount=0&lang=en-US&region=US"
            resp = await fetch(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(await resp.text())
            raw_news = data.get("news") or []
            news = []
            for item in raw_news[:15]:
                title = item.get("title", "")
                link  = item.get("link", "")
                if not (title and link):
                    continue
                pub_time = item.get("providerPublishTime")
                thumbnail = None
                for res in (item.get("thumbnail") or {}).get("resolutions") or []:
                    thumbnail = res.get("url"); break
                news.append({
                    "title":     title,
                    "summary":   "",
                    "publisher": item.get("publisher", ""),
                    "time":      pub_time,
                    "link":      link,
                    "thumbnail": thumbnail,
                })
            return _j({"news": news})
        except Exception as e:
            return _j({"news": [], "error": str(e)})

    # GET /api/quotes?tickers=AAPL,BTC-USD — crypto via Binance, stocks via D1
    if method == "GET" and path == "/api/quotes":
        tickers_str = qs.get("tickers", "")
        if not tickers_str:
            return _j({"quotes": {}})
        tickers     = [t.strip() for t in tickers_str.split(",") if t.strip()]
        crypto_list = [t for t in tickers if t.endswith("-USD")]
        stock_list  = [t for t in tickers if not t.endswith("-USD")]
        quotes = {}

        # Crypto: Binance (funciona desde datacenter)
        for t in crypto_list:
            base = t[:-4]
            try:
                resp = await fetch(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={base}USDT",
                    headers={"User-Agent": "maximos/1.0"},
                )
                if resp.status == 200:
                    d = json.loads(await resp.text())
                    if "price" in d:
                        price = round(float(d["price"]), 4)
                        quotes[t] = {"price": price, "change": None, "change_pct": None}
            except Exception:
                pass

        # Stocks / CEDEARs: D1 (datos del último screener run)
        if stock_list:
            try:
                placeholders = ",".join(["?"] * len(stock_list))
                result = await env.DB.prepare(
                    f"SELECT ticker, price FROM screener_results WHERE ticker IN ({placeholders})"
                ).bind(*stock_list).all()
                for row in result.results.to_py():
                    t = row.get("ticker")
                    p = row.get("price")
                    if t and p is not None:
                        quotes[t] = {"price": round(float(p), 4), "change": None, "change_pct": None}
            except Exception:
                pass

        return _j({"quotes": quotes})

    # GET /api/crypto-quotes?symbols=BTC,ETH — precios en tiempo real desde Binance
    if method == "GET" and path == "/api/crypto-quotes":
        symbols_str = qs.get("symbols", "")
        if not symbols_str:
            return _j({"quotes": {}})
        symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
        quotes = {}
        for base in symbols:
            try:
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={base}USDT"
                resp = await fetch(url, headers={"User-Agent": "maximos/1.0"})
                if resp.status == 200:
                    data = json.loads(await resp.text())
                    if "price" in data:
                        quotes[base] = float(data["price"])
            except Exception:
                pass
        return _j({"quotes": quotes})

    # GET /api/dollar — cotizaciones del dólar (dolarapi.com)
    if method == "GET" and path == "/api/dollar":
        try:
            resp = await fetch("https://dolarapi.com/v1/dolares", headers={"User-Agent": "maximos/1.0"})
            data = json.loads(await resp.text())
            return _j({"dollar": data})
        except Exception as e:
            return _j({"dollar": [], "error": str(e)})

    # GET /api/ai-alert?ticker=NVDA — página HTML con recomendación IA (para alertas ntfy)
    if method == "GET" and path == "/api/ai-alert":
        ticker = qs.get("ticker", "").upper()
        if not ticker:
            return Response("Falta ticker", status=400)

        def _html(content: str, status: int = 200) -> Response:
            return Response(content, status=status, headers={"Content-Type": "text/html; charset=utf-8"})

        # Buscar ticker en D1 (en cualquier lista)
        ticker_data = None
        try:
            result = await db.prepare(
                "SELECT data FROM screener_results WHERE ticker = ? ORDER BY score DESC LIMIT 1"
            ).bind(ticker).all()
            for row in result.results:
                ticker_data = json.loads(row.to_py()["data"])
                break
        except Exception as e:
            return _html(f"<p>Error buscando ticker: {e}</p>", 500)

        if not ticker_data:
            return _html(f"<p>Ticker {ticker} no encontrado.</p>", 404)

        # Llamar a IA
        from providers.prompt import build_prompt
        cf_ai     = getattr(env, "AI", None)
        groq_key  = getattr(env, "GROQ_API_KEY", None)
        gemini_key = getattr(env, "GOOGLE_API_KEY", None)
        recommendation = "No se pudo obtener la recomendación."
        for provider, arg in [(cf_analyze, cf_ai), (groq_analyze, groq_key), (gemini_analyze, gemini_key)]:
            if not arg:
                continue
            try:
                recommendation = await provider(ticker_data, arg)
                break
            except Exception:
                continue

        signal = ticker_data.get("signal", "neutral")
        score  = ticker_data.get("score", 0)
        zone   = (ticker_data.get("zone") or "").upper()
        price  = ticker_data.get("price", 0)
        sl     = ticker_data.get("sl")
        tp1    = ticker_data.get("tp1")
        tp2    = ticker_data.get("tp2")

        signal_label = signal.replace("_", " ").upper()
        signal_colors = {
            "compra_fuerte": ("#166534", "#86efac"),
            "compra":        ("#14532d", "#bbf7d0"),
            "neutral":       ("#374151", "#d1d5db"),
            "venta":         ("#7c2d12", "#fdba74"),
            "venta_fuerte":  ("#7f1d1d", "#fca5a5"),
        }
        bg_color, text_color = signal_colors.get(signal, ("#374151", "#d1d5db"))

        sl_tp_html = ""
        if sl and tp1:
            sl_tp_html = f"""
            <div style="display:flex;gap:1rem;margin-top:1rem;font-size:0.9rem;">
              <span style="color:#f87171;">SL ${sl}</span>
              <span style="color:#4ade80;">TP1 ${tp1}</span>
              {"<span style='color:#4ade80;'>TP2 $" + str(tp2) + "</span>" if tp2 else ""}
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ticker} - maximos</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #e2e8f0;
          padding: 1.5rem; max-width: 480px; margin: 0 auto; }}
  .header {{ border-top: 3px solid #f59e0b; padding-top: 1rem; margin-bottom: 1.25rem; }}
  .ticker {{ font-size: 2rem; font-weight: 700; color: #f59e0b; }}
  .price  {{ font-size: 1rem; color: #94a3b8; margin-top: 0.15rem; }}
  .badge  {{ display: inline-block; padding: 0.3rem 0.9rem; border-radius: 999px;
             font-size: 0.8rem; font-weight: 700; margin: 0.75rem 0;
             background: {bg_color}; color: {text_color}; letter-spacing: 0.05em; }}
  .meta   {{ font-size: 0.8rem; color: #64748b; margin-bottom: 1rem; }}
  .rec    {{ line-height: 1.7; color: #cbd5e1; font-size: 0.95rem; }}
  .footer {{ margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #1e293b;
             font-size: 0.75rem; color: #475569; text-align: center; }}
</style>
</head>
<body>
  <div class="header">
    <div class="ticker">{ticker}</div>
    <div class="price">${price}</div>
  </div>
  <div class="badge">{signal_label}</div>
  <div class="meta">Score {score} &middot; {zone}</div>
  <div class="rec">{recommendation}</div>
  {sl_tp_html}
  <div class="footer">maximos &middot; {ticker}</div>
</body>
</html>"""

        return _html(html)

    return _j({"error": "not found"}, status=404)

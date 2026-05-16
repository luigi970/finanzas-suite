# Stock Screener — maximos

App web que analiza acciones, ETFs y criptos. Aplica el sistema **Helper Prime + Helper Pulse** (portado desde Pine Script v6) para asignar un Score 0-100 y clasificar cada activo en 5 señales. Al abrir un ticker muestra una recomendación generada por IA.

## Arquitectura de producción

```
GitHub Actions
├── screener.yml — cron diario (2am UTC lun-vie) + repository_dispatch on-demand
│   └── run_job.py → screener.py → escribe resultados en Cloudflare D1 vía HTTP API
└── deploy.yml — push a main con cambios en worker/** o frontend/**
    ├── npx wrangler deploy (Worker)
    └── npm run build + wrangler pages deploy (Pages)

Cloudflare Worker (Python, Pyodide/WASM)
└── entry.py — REST API que lee D1 + llama a IA

Cloudflare D1 (SQLite)
├── screener_runs — estado del job (running/done)
└── screener_results — resultados por list_id + ticker (UNIQUE)

Cloudflare Pages
└── React + Vite — consume la Worker API
```

## Estructura

```
maximos/
├── .github/workflows/
│   ├── deploy.yml       # CI/CD automático
│   └── screener.yml     # Screener: cron + repository_dispatch + workflow_dispatch
├── backend/
│   ├── main.py          # FastAPI para desarrollo local (no se deploya)
│   ├── screener.py      # Helper Prime + Pulse, get_tickers(), compute_all()
│   ├── run_job.py       # Entry point para GitHub Actions: lee D1 vía CF HTTP API
│   └── requirements.txt
├── frontend/
│   └── src/App.jsx      # UI completa en un solo archivo
├── worker/
│   ├── wrangler.toml    # compatibility_date="2025-01-15", [ai] binding, D1 binding
│   └── src/
│       ├── entry.py     # on_fetch: routing, CORS, endpoints
│       ├── storage/db.py
│       └── providers/
│           ├── prompt.py   # build_prompt() compartido
│           ├── cf_ai.py    # Cloudflare Workers AI (primario)
│           ├── groq.py     # Groq API (fallback 1)
│           └── gemini.py   # Gemini API (fallback 2)
└── start.ps1 / start.sh
```

## Cómo arrancar (desarrollo local)

```powershell
# Backend FastAPI (puerto 8000)
cd backend
uvicorn main:app --reload --port 8000

# Frontend Vite (puerto 5173)
cd frontend
npm run dev
```

En local el frontend no tiene `VITE_API_URL`, así que apunta a `localhost:8000`.
El botón "Analizar" corre el screener directamente en FastAPI (sin GitHub Actions).
La IA usa Groq → Gemini (CF Workers AI no existe fuera del Worker).

El `.env` del backend necesita:
```
GROQ_API_KEY=...
GOOGLE_API_KEY=...
```

## API endpoints

Todos expuestos tanto en el Worker (producción) como en FastAPI (local):

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/status?list_id=sp500` | Estado del último run y progreso |
| GET | `/api/stocks?list_id=sp500&signal=all` | Resultados, filtrable por señal |
| GET | `/api/lists` | Listas disponibles con conteo |
| POST | `/api/refresh` | Dispara screener (GH Actions en prod, background en local) |
| POST | `/api/analyze` | Recomendación IA para un ticker |

Body de `/api/refresh`:
```json
{ "list_id": "sp500", "crypto_limit": 20 }
```
`list_id`: `sp500` · `nasdaq100` · `etfs` · `adrs_arg` · `crypto`

Body de `/api/analyze`: el objeto completo del ticker (todos los campos calculados).

Status del Worker: `"idle"` → `"loading"` → `"ready"` (mapeado desde D1: `running` → `loading`, `done` → `ready`).

## Secrets

### GitHub Actions
- `CF_API_TOKEN` — token de Cloudflare con permisos D1 + Workers + Pages
- `CF_ACCOUNT_ID` — account ID de Cloudflare
- `CF_D1_DB_ID` — ID de la base D1
- `VITE_API_URL` — URL del Worker para el build de Pages

### Cloudflare Worker (dashboard → Settings → Variables and Secrets)
- `GH_PAT` — GitHub PAT con permisos `repo` (para repository_dispatch)
- `GROQ_API_KEY` — fallback IA
- `GOOGLE_API_KEY` — segundo fallback IA
- CF Workers AI vía binding `AI` en wrangler.toml (sin secret)

## Cloudflare Worker — gotchas críticos

- **`from workers import fetch`** — única forma de hacer HTTP desde Python Workers. `urllib`, `requests`, `httpx` no funcionan (no hay sockets en WASM). No usar `from js import fetch`.
- **`compatibility_date = "2025-01-15"`** — versiones anteriores rompen Python Workers + D1.
- **D1 rows son JsProxy** — usar `row.to_py()` para convertir a dict. `dict(row)` falla.
- **`.all()` con LIMIT 1** en vez de `.first()` — `.first()` devuelve un JsProxy no iterable.
- **CORS antes de todo** — si el Worker crashea antes de enviar headers, el browser reporta error de CORS (misleading).
- **`env.AI`** es el binding de Workers AI. `getattr(env, "AI", None)` para chequearlo.

## Screener — gotchas

- **`status="idle"` durante startup**: GitHub Actions tarda 30-60s en crear el run record en D1 después del `repository_dispatch`. El frontend ignora `"idle"` cuando está en estado `"loading"` para no cortar el polling prematuramente.
- **Custom list en D1**: se borran todos los resultados anteriores antes de cada run custom para que no se acumulen tickers de búsquedas anteriores.
- **Matrix de screener**: `[sp500, nasdaq100, etfs, adrs_arg, crypto]`. El cron omite crypto. Custom usa un job separado (`screener-custom`).
- **deploy.yml path filter**: solo corre cuando cambia `worker/**` o `frontend/**`. Cambiar solo `.github/workflows/` no lo dispara — usar `workflow_dispatch`.

## Sistema de scoring — Helper Prime (0-100)

Port directo desde Pine Script v6. Dos scores simétricos (long/short):

| Componente | Pts | Criterio alcista |
|---|---|---|
| EMA 200 | 15 | `close > ema200` |
| Alineación EMA | 15 | `ema20 > ema55 > ema200` (+15), solo `ema20 > ema55` (+8) |
| ADX + DI | 15 | `adx > 20 and DI+ > DI-` (+15), solo `adx > 20` (+8) |
| Momentum RSI-50 | 15 | `mom > 0 and rising` (+15), solo `mom > 0` (+8) |
| MTF proxy | 15 | 4 señales: `price > ema20/55/200, ema20 > ema55`. ≥3 (+15), ==2 (+8) |
| Volatilidad ATR | 10 | `atr > sma(atr,20) * 1.05` |
| Zona estructural | 15 | DISCOUNT o near support o POC (+15) |

### Zonas
- **DISCOUNT**: `close <= lr_basis - lr_dev * 0.35` (regresión lineal 100 períodos, dev×2)
- **FAIR**: zona media
- **PREMIUM**: `close >= lr_basis + lr_dev * 0.35`
- **POC**: precio con mayor volumen acumulado (70 velas, 15 buckets)

### Señales
| Dirección | Score | Señal |
|---|---|---|
| LONG | ≥ 75 | `compra_fuerte` |
| LONG | ≥ 60 | `compra` |
| — | < 60 | `neutral` |
| SHORT | ≥ 60 | `venta` |
| SHORT | ≥ 75 | `venta_fuerte` |

## Helper Pulse — Divergencias RSI

Oscilador: `ema(rsi(14) - 50, 3)`. Detecta sobre los últimos 2 pivots:

| Señal | Condición |
|---|---|
| GIRO UP | Precio lower low + momentum higher low (zona < -15) |
| SIGUE UP | Precio higher low + momentum lower low (mom < 0) |
| GIRO DN | Precio higher high + momentum lower high (zona > 15) |
| SIGUE DN | Precio lower high + momentum higher high (mom > 0) |
| AGOT. SUP | Pivot momentum en zona alta (≥ 15) sin divergencia |
| AGOT. INF | Pivot momentum en zona baja (≤ -15) sin divergencia |

Parámetros: `pivot_len=3`, `min_bars_between=5`, `min_osc_delta=3.0`, `turn_level=15`

## SL / TP

- **SL**: precio − ATR(14) × 1.5
- **TP1**: precio + ATR(14) × 1.5
- **TP2**: precio + ATR(14) × 3.0

## Campos calculados por ticker

`price`, `score`, `long_score`, `short_score`, `direction`, `signal`,
`zone`, `adx`, `mom`, `poc`, `sl`, `tp1`, `tp2`,
`pulse_signal`, `pulse_state`,
`rsi`, `macd_hist`, `vol_ratio`,
`bb_upper`, `bb_lower`, `pct_b`,
`ma50`, `ma200`, `pct_vs_ma50`, `pct_vs_ma200`,
`high_52w`, `low_52w`, `pct_from_high`, `pct_from_low`

## Listas de activos

| ID | Descripción | Fuente |
|---|---|---|
| `sp500` | 503 acciones | CSV GitHub `datasets/s-and-p-500-companies` |
| `nasdaq100` | 100 empresas tech | Hardcodeado en `screener.py` |
| `etfs` | 49 ETFs | Hardcodeado en `screener.py` |
| `adrs_arg` | 17 ADRs argentinos | Hardcodeado en `screener.py` |
| `crypto` | Top N criptos (sin stablecoins) | Hardcodeado, limitado por `crypto_limit` |

## IA — cadena de proveedores

En el Worker (producción): CF Workers AI → Groq → Gemini (loop, primer éxito gana).
En FastAPI (local): Groq → Gemini.

El prompt está en `worker/src/providers/prompt.py` (`build_prompt()`). El backend local tiene el prompt inlineado en `main.py` (misma lógica).

## Decisiones técnicas

- **Descarga bulk**: `yf.download("AAPL MSFT ...", period="1y")` — un solo request HTTP para todos los tickers.
- **Multi-level columns**: yfinance con un solo ticker no genera columnas multi-nivel. `screener.py` maneja ambos casos.
- **Fuente S&P 500**: CSV de GitHub. Wikipedia devuelve 403 con `pd.read_html`.
- **yfinance**: requiere 1.3.0+. Versiones anteriores fallan con `JSONDecodeError`.
- **MTF aproximado**: temporalidades reales (15m/1h/4h) no disponibles con datos diarios. Se usan 4 señales de EMAs diarias.
- **Pine Script originales**: en `c:\Users\Compu\Documents\Dev\Finanzas\suite indicators\`.

## Roadmap

### Features pendientes
- [ ] Gráfico de precio al hacer click en un ticker
- [ ] Alertas por email o Telegram cuando cambia la señal
- [ ] MTF real con descarga intraday para 15m/1h/4h

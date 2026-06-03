# Flujo interno de maximos

## Visión general

```
GitHub Actions  →  Cloudflare D1  →  Cloudflare Worker  →  Browser / Finanzas
   (procesa)         (almacena)           (sirve)              (consume)
```

---

## 1. Disparo del screener

El screener se dispara de dos formas:

- **Automático**: cron en `.github/workflows/screener.yml` — todos los días hábiles a las 2am UTC
- **Manual**: botón "Actualizar" en la UI → Worker recibe POST → llama a GitHub API (`repository_dispatch`) → GitHub Actions arranca

---

## 2. GitHub Actions corre el screener

`.github/workflows/screener.yml` define el job con una matrix de listas: `[sp500, nasdaq100, etfs, adrs_arg, crypto, commodities]`. Cuando se dispara:

1. GitHub clona el repositorio completo en sus servidores
2. Instala dependencias: `pip install -r backend/requirements.txt`
3. Corre `python backend/run_job.py --list <lista>` para cada lista del matrix

**`run_job.py`** es el orquestador:
1. Lee las variables de entorno: `CF_API_TOKEN`, `CF_ACCOUNT_ID`, `CF_D1_DB_ID`
2. Llama a `screener.py` → `compute_all(tickers)`
3. Por cada resultado, hace `upsert_result()` → HTTP POST a la API REST de Cloudflare D1
4. Al terminar, marca el run como `done` en D1
5. Actualiza `signal_history` con precios del día para tracking de rendimiento 5d/10d/20d

Todo el procesamiento ocurre en los **servidores de GitHub**, no en Cloudflare.

---

## 3. screener.py — el motor de cálculo

`screener.py` no sabe nada de Cloudflare. Solo:

1. Recibe una lista de tickers
2. Descarga datos históricos de **Yahoo Finance** vía `yfinance` (1 año de velas diarias, secuencial con sleep para evitar rate limiting)
3. Para **crypto**, usa Binance en lugar de Yahoo Finance (datos más confiables)
4. Para **commodities**, usa tickers de futuros de Yahoo Finance (`GC=F`, `CL=F`, etc.)
5. Por cada ticker calcula:
   - EMAs (20, 55, 200), ADX, RSI, MACD, Bollinger, ATR
   - Score 0-100 (Helper Prime): EMA200, alineación EMAs, ADX+DI, momentum, MTF proxy, volatilidad, zona
   - Divergencias RSI (Helper Pulse): pivots, señales GIRO UP/DN, AGOT. SUP/INF
   - Zona estructural (DISCOUNT / FAIR / PREMIUM) via regresión lineal
   - POC, Pivot points Classic y Fibonacci, patrones de velas, SL/TP

---

## 4. run_job.py sube los datos a Cloudflare D1

Por cada ticker calculado:

```python
INSERT INTO screener_results (list_id, ticker, signal, score, data, updated_at)
VALUES (...)
ON CONFLICT(list_id, ticker) DO UPDATE SET ...
```

- `data` es un JSON con todos los campos calculados (precio, score, señal, zona, MAs, pivots, etc.)
- `screener_results` tiene un índice UNIQUE por `(list_id, ticker)` — cada run sobrescribe el anterior
- También guarda historial en `signal_history` con el precio de cada día

Cloudflare D1 es una base SQLite alojada en Cloudflare. `run_job.py` la escribe via HTTP usando la API REST de Cloudflare.

---

## 5. Cloudflare Worker sirve los datos

`worker/src/entry.py` es una API Python (Pyodide/WASM) que corre dentro de Cloudflare. Expone:

| Endpoint | Fuente | Descripción |
|---|---|---|
| `GET /api/stocks?list_id=sp500` | D1 | Resultados del último screener run |
| `GET /api/status?list_id=sp500` | D1 | Estado del run (running / done) |
| `GET /api/lists` | D1 | Listas disponibles con conteo |
| `GET /api/quotes?tickers=AAPL,BTC-USD` | D1 (stocks) + Binance (crypto) | Precios actuales |
| `GET /api/crypto-quotes?symbols=BTC,ETH` | Binance | Precios crypto en tiempo real |
| `GET /api/dollar` | dolarapi.com | Cotizaciones del dólar (blue, oficial, etc.) |
| `POST /api/refresh` | GitHub API | Dispara un nuevo screener run |
| `POST /api/analyze` | CF Workers AI / Groq / Gemini | Recomendación IA para un ticker |

**Regla importante**: el Worker no puede usar `requests`, `httpx` ni `urllib` (no hay sockets en WASM). Solo puede hacer HTTP via `from workers import fetch`.

---

## 6. Por qué Yahoo Finance no se usa desde el Worker

Yahoo Finance bloquea requests desde IPs de datacenter (Cloudflare). Por eso:

- **Stocks/CEDEARs en `/api/quotes`**: el Worker lee D1 (datos del último screener run de GitHub Actions)
- **Crypto en `/api/quotes` y `/api/crypto-quotes`**: el Worker llama a Binance directamente (Binance no bloquea datacenter)

Yahoo Finance solo se usa desde GitHub Actions, donde corre en servidores normales sin bloqueo.

---

## 7. Finanzas consume el Worker

La app de finanzas personales (`finanzas/`) es independiente pero usa el Worker de maximos para obtener precios:

- **Precios crypto**: `GET /api/crypto-quotes?symbols=BTC,ETH`
- **Precios stocks/CEDEARs/commodities**: `GET /api/quotes?tickers=AAPL,GC=F`
- **Dólar blue**: `GET /api/dollar`

El agente IA de finanzas también usa estos precios para calcular el valor actualizado de la cartera antes de responder.

En el modal de cada ticker del screener hay un botón **TradingView ↗** que abre el chart con el ticker precargado (stocks: símbolo directo, crypto: convertido a formato USDT).

---

## Resumen de archivos clave

| Archivo | Rol |
|---|---|
| `.github/workflows/screener.yml` | Define cuándo y cómo corre el screener en GitHub Actions |
| `backend/screener.py` | Motor de cálculo: descarga Yahoo Finance/Binance, calcula scores y señales |
| `backend/run_job.py` | Orquestador: llama screener.py y sube resultados a Cloudflare D1 |
| `worker/src/entry.py` | API REST en Cloudflare: lee D1 y sirve datos al browser |
| `worker/src/storage/db.py` | Queries SQL contra D1 |
| `worker/src/providers/prompt.py` | Prompt IA compartido para el análisis de tickers |
| `frontend/src/App.jsx` | UI del screener (React + Vite) |
| `finanzas/backend/main.py` | FastAPI finanzas: incluye endpoints de config de API keys |
| `finanzas/backend/routers/agent.py` | Agente IA de finanzas: usa Worker para precios de mercado |
| `finanzas/frontend/src/App.jsx` | UI de finanzas (React + Vite) |

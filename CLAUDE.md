# Stock Screener — maximos

App web que analiza acciones, ETFs y criptos. Aplica el sistema **Helper Prime + Helper Pulse** (portado desde Pine Script v6) para asignar un Score 0-100 y clasificar cada activo en 5 señales. Al abrir un ticker muestra una recomendación generada por IA.

## Arquitectura de producción

```
GitHub Actions
├── screener.yml — cron diario (2am UTC lun-vie) + repository_dispatch on-demand
│   └── maximos/backend/run_job.py → screener.py → escribe resultados en Cloudflare D1 vía HTTP API
└── deploy.yml — push a main con cambios en maximos/worker/** o maximos/frontend/**
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

## Estructura (monorepo finanzas-suite)

```
finanzas-suite/           # repo raíz (github.com/luigi970/finanzas-suite)
├── .github/workflows/
│   ├── deploy.yml        # CI/CD automático
│   └── screener.yml      # Screener: cron + repository_dispatch + workflow_dispatch
├── maximos/              # app screener
│   ├── backend/
│   │   ├── main.py       # FastAPI para desarrollo local (no se deploya)
│   │   ├── screener.py   # Helper Prime + Pulse, get_tickers(), compute_all()
│   │   ├── run_job.py    # Entry point para GitHub Actions: lee D1 vía CF HTTP API
│   │   └── requirements.txt
│   ├── frontend/
│   │   └── src/App.jsx   # UI completa en un solo archivo
│   ├── worker/
│   │   ├── wrangler.toml # compatibility_date="2025-01-15", [ai] binding, D1 binding
│   │   └── src/
│   │       ├── entry.py  # on_fetch: routing, CORS, endpoints
│   │       ├── storage/db.py
│   │       └── providers/
│   │           ├── prompt.py   # build_prompt() compartido
│   │           ├── cf_ai.py    # Cloudflare Workers AI (primario)
│   │           ├── groq.py     # Groq API (fallback 1)
│   │           └── gemini.py   # Gemini API (fallback 2)
│   └── start.ps1 / start.sh
├── finanzas/             # app patrimonio personal
│   ├── backend/          # FastAPI puerto 8001
│   └── frontend/         # Vite puerto 5174
├── fiscal/               # asistente fiscal IA (AFIP/ARCA)
│   ├── backend/          # FastAPI puerto 8002
│   └── frontend/         # Vite puerto 5175
├── launcher/             # home page unificado de la suite
│   ├── backend/          # FastAPI puerto 8099 — config unificado + status de apps
│   │   ├── main.py
│   │   └── requirements.txt
│   └── frontend/         # Vite puerto 5172 — cards + botones + settings
│       └── src/App.jsx
├── start-all.ps1         # arranca los 8 procesos; auto-libera puertos; abre solo el launcher
└── stop-all.ps1          # detiene puertos 8099, 8000-8002, 5172-5175
```

## Cómo arrancar (desarrollo local)

### Todo junto (launcher + maximos + finanzas + fiscal)
```powershell
.\start-all.ps1   # arranca los 8 procesos; auto-libera puertos; abre launcher en browser
.\stop-all.ps1    # detiene todo (puertos 8099, 8000-8002, 5172-5175)
```
El launcher abre en `http://localhost:5172` y desde ahí se accede a las tres apps y se configuran todas las API keys.

### Solo maximos
```powershell
# Backend FastAPI (puerto 8000)
cd maximos/backend
uvicorn main:app --reload --port 8000

# Frontend Vite (puerto 5173)
cd maximos/frontend
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
Las keys también se pueden configurar desde el launcher (⚙️ Configuración) sin tocar el .env manualmente.

## API endpoints

Todos expuestos tanto en el Worker (producción) como en FastAPI (local):

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Health check (usado por el launcher para status) |
| GET | `/api/status?list_id=sp500` | Estado del último run y progreso |
| GET | `/api/stocks?list_id=sp500&signal=all` | Resultados, filtrable por señal |
| GET | `/api/lists` | Listas disponibles con conteo |
| POST | `/api/refresh` | Dispara screener (GH Actions en prod, background en local) |
| POST | `/api/analyze` | Recomendación IA para un ticker |
| GET | `/api/quotes?symbols=AAPL,GGAL` | Precios de acciones/CEDEARs — Worker: desde D1; local: Yahoo Finance |
| GET | `/api/crypto-quotes?symbols=BTC,ETH` | Precios de cripto — Binance API (Worker y local) |
| GET | `/api/dollar` | Dólar blue (Bluelytics) |

Body de `/api/refresh`:
```json
{ "list_id": "sp500", "crypto_limit": 20 }
```
`list_id`: `sp500` · `nasdaq100` · `etfs` · `adrs_arg` · `crypto` · `commodities`

Body de `/api/analyze`: el objeto completo del ticker (todos los campos calculados).

Status del Worker: `"idle"` → `"loading"` → `"ready"` (mapeado desde D1: `running` → `loading`, `done` → `ready`).

## Secrets

### GitHub Actions
- `CF_API_TOKEN` — token de Cloudflare con permisos D1 + Workers + Pages
- `CF_ACCOUNT_ID` — account ID de Cloudflare
- `CF_D1_DB_ID` — ID de la base D1
- `VITE_API_URL` — URL del Worker para el build de Pages
- `COINGECKO_API_KEY` — para el ranking en vivo de la lista `crypto` (opcional: si falta, `get_crypto_tickers_live()` cae a la lista fija vieja sin romper el job)
- `NTFY_TOPIC` — nombre del canal de ntfy.sh para las alertas de señal fuerte (opcional: si falta, `check_and_send_alerts()` no manda nada, no rompe el job). Ver sección "Alertas por señal fuerte" más abajo.

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
- **Yahoo Finance bloqueado desde datacenter**: el Worker no puede pedir precios a Yahoo Finance (devuelve 401/403 desde IPs de Cloudflare). Solución: cripto vía Binance API, acciones/CEDEARs desde D1 (data del último screener).
- **CORS — puertos de finanzas**: `ALLOWED_ORIGINS` incluye `http://localhost:5174` y `http://localhost:8001` para desarrollo local de finanzas.

## Screener — gotchas

- **`status="idle"` durante startup**: GitHub Actions tarda 30-60s en crear el run record en D1 después del `repository_dispatch`. El frontend ignora `"idle"` cuando está en estado `"loading"` para no cortar el polling prematuramente.
- **Custom list en D1**: se borran todos los resultados anteriores antes de cada run custom para que no se acumulen tickers de búsquedas anteriores.
- **Matrix de screener**: `[sp500, nasdaq100, etfs, adrs_arg, crypto, commodities]`. El cron omite crypto. Custom usa un job separado (`screener-custom`).
- **Commodities**: tickers de futuros Yahoo Finance (`GC=F` Gold, `SI=F` Silver, `CL=F` WTI, etc.). `displayTicker()` en el frontend los convierte a nombres legibles via `COMMODITY_NAMES`.
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

`name` (nombre completo — "AAPL" → "Apple"; sp500 sale del CSV de origen, cripto en vivo de CoinGecko, el resto de un mapa a mano en `_TICKER_NAMES`; usado por el frontend para el tooltip al pasar el mouse),
`price`, `score`, `long_score`, `short_score`, `direction`, `signal`,
`zone`, `adx`, `mom`, `poc`, `sl`, `tp1`, `tp2`,
`pulse_signal`, `pulse_state`,
`rsi`, `macd_hist`, `vol_ratio`,
`bb_upper`, `bb_lower`, `pct_b`,
`ma5`, `ma10`, `ma20`, `ma50`, `ma200`,
`pct_vs_ma5`, `pct_vs_ma10`, `pct_vs_ma20`, `pct_vs_ma50`, `pct_vs_ma200`,
`high_52w`, `low_52w`, `pct_from_high`, `pct_from_low`,
`candle_pattern` (dict: `name`, `type` → bullish/bearish/neutral),
`pivots` (dict: `classic` y `fibonacci`, cada uno con P, R1-R3, S1-S3)

## Listas de activos

| ID | Descripción | Fuente |
|---|---|---|
| `sp500` | 503 acciones | CSV GitHub `datasets/s-and-p-500-companies` |
| `nasdaq100` | 100 empresas tech | Hardcodeado en `screener.py` |
| `etfs` | 49 ETFs | Hardcodeado en `screener.py` |
| `adrs_arg` | 19 ADRs argentinos | Hardcodeado en `screener.py` |
| `crypto` | Top N criptos por market cap real (sin stablecoins), limitado por `crypto_limit` | **En vivo** desde CoinGecko (`get_crypto_tickers_live()` en `screener.py`), filtrado contra pares activos en Binance — cae a una lista fija vieja si CoinGecko/Binance fallan |
| `commodities` | 18 futuros: metales, energía y agrícolas | Hardcodeado en `screener.py` con tickers `=F` |

### `crypto` — ranking en vivo (gotchas, 2026-08-26)
- **Antes era 100% hardcodeado** — una lista fija tipeada en el código, que se desactualizaba con el tiempo (tenía monedas de 2020-2021 como SAND/CHZ/WIN/DENT y le faltaban todas las que subieron después, ej. Hyperliquid). Ahora `get_crypto_tickers_live(limit)` pide el ranking real a CoinGecko (`/coins/markets`, requiere `COINGECKO_API_KEY` — la misma key gratuita que ya se usa en finanzas, repartida también a maximos vía el launcher) y devuelve el top N actualizado.
- **El ranking crudo de CoinGecko trae basura**: fondos tokenizados (BUIDL, USYC, JAAA), oro/commodities tokenizados (XAUT, PAXG), stablecoins nuevas no cubiertas por la lista de exclusión, y ocasionalmente símbolos con datos corruptos (se vio un símbolo con caracteres no latinos). Se filtra con: (1) lista de stablecoins conocidas, (2) regex `^[A-Z0-9_-]{1,15}$` para descartar símbolos con formato raro, (3) cruce contra `_get_binance_tradable_symbols()` — solo se incluye un ticker si tiene un par activo contra USDT en Binance, que es de donde el screener saca los precios igual, así se evita listar algo que después no va a tener datos.
- **Límite real, a propósito — solo spot, nunca futuros**: si una moneda no cotiza en Binance **spot**, no va a aparecer en la lista, sin importar cuán alto esté el `crypto_limit`. Caso real: Hyperliquid (HYPE) no tiene par `HYPEUSDT` en spot, solo en futuros/perpetuos (`fapi.binance.com`) — se evaluó agregar futuros como respaldo cuando spot no tiene el símbolo, pero se descartó: el precio de un perpetuo diverge del spot (funding rate, apalancamiento, mechas de liquidación), así que mezclar las dos fuentes entre distintos tickers de la misma lista haría que los scores dejen de ser comparables entre sí — algunos calculados sobre precio "real" y otros sobre precio de futuros. Para incluir monedas futures-only habría que evaluar todo el ticker con datos de futuros de forma consistente (otro cambio de arquitectura, no un ajuste de la lista), o directamente aceptar que quedan afuera.
- Respaldo: si CoinGecko o Binance fallan (rate limit, sin red, sin key), `get_crypto_tickers_live()` cae a la lista fija vieja (`LISTS["crypto"]`) — el screener nunca se queda sin tickers por esto, aunque en ese caso vuelve a ser una lista desactualizada hasta la próxima corrida exitosa.

## Alertas por señal fuerte (2026-09-08)

Aviso push al celular (vía [ntfy.sh](https://ntfy.sh), gratis, sin cuenta) cuando un ticker que el usuario vigila entra o sale de `compra_fuerte`/`venta_fuerte`. Pensado para no tener que abrir la app todos los días — el usuario arma una lista corta de tickers que le importan, y listo.

- **Alcance, a propósito**: solo una lista corta que el usuario arma a mano (tabla `alert_watchlist` en D1, columna `ticker`) — no se avisa de toda la lista sp500/nasdaq100 completa, sería puro ruido. Se gestiona desde la web de maximos (sección "🔔 Alertas", input de tickers separados por coma) — **distinta** del "Watchlist" que ya existía, que vive solo en `localStorage` del navegador y por eso el trabajo diario de GitHub Actions no lo puede leer (corre en la nube, no en el navegador del usuario).
- **Disparador, a propósito — solo señales fuertes, no cualquier cambio**: se compara la señal de hoy contra la de ayer (ya está guardado en `signal_history`, no hace falta ningún dato nuevo). Se avisa únicamente si la señal de HOY o la de AYER es `compra_fuerte`/`venta_fuerte` y cambiaron — cubre entrar a una zona fuerte, salir de una, y el caso raro de flip directo compra_fuerte↔venta_fuerte. Un cambio entre señales débiles (ej. neutral → compra) no dispara nada — el objetivo es señal, no ruido de todos los días.
- **Mensaje "claro y ameno", no un volcado técnico** (pedido explícito): el título usa un emoji + una frase corta ("🚀 PYPL entró en zona de COMPRA FUERTE"), el cuerpo explica en una oración qué pasó y a qué precio, y le pega abajo las 2 noticias más recientes del propio ticker (mismo dato que ya se muestra en la pestaña Noticias del modal — `yf.Ticker(ticker).news`, no es una fuente nueva).
- **No incluye noticias "indirectas"** (una suba de tasas que pega en tech, por ejemplo) — eso se evaluó y se descartó para esta primera versión: solo hay noticias del propio ticker, no hay ninguna fuente de noticias de mercado/sector todavía, así que una IA "juzgando relevancia indirecta" no tendría de qué mercado alimentarse. Queda como posible vuelta de tuerca si las alertas simples resultan útiles.
- **Arquitectura**: `run_job.py` corre `check_and_send_alerts()` al final de cada corrida (una vez por lista, ya con los resultados del día calculados) — la tabla `alert_watchlist` se auto-crea (`CREATE TABLE IF NOT EXISTS`) tanto ahí como en los endpoints del Worker, no depende de aplicar una migración a mano. Todo el bloque está en un único `try/except` grande — un error acá (ntfy caído, D1 con un hipo) nunca debe tirar abajo el job del screener, que ya guardó sus resultados antes de llegar a este punto.
- **Sin `NTFY_TOPIC` configurado, no manda nada** — no es un error, `check_and_send_alerts()` corta al toque. El topic actúa como "contraseña" del canal (cualquiera que lo sepa puede suscribirse) — hay que elegir un nombre largo y random, no algo como `maximos-alertas`.
- **Cómo activarlo**: 1) instalar la app [ntfy](https://ntfy.sh/) (Android/iOS) y suscribirse a un topic random elegido por el usuario; 2) cargar ese mismo nombre como secret `NTFY_TOPIC` en GitHub Actions (Settings → Secrets → Actions) — esto no lo puede hacer Claude, requiere acceso a la config del repo; 3) agregar tickers desde la sección 🔔 Alertas en la web de maximos.
- **Endpoints**: `GET /api/alerts/watchlist` (lista actual), `POST /api/alerts/watchlist` con `{"tickers": [...]}` (reemplaza la lista entera, no hay altas/bajas individuales — máximo 30 tickers).
- **Tickers fuera de las 6 listas fijas (ej. MicroStrategy/MSTR)**: si no está en sp500/nasdaq100/etfs/adrs_arg/crypto/commodities, el screener normal nunca lo procesa y nunca podría alertar nada. Se agregó un job separado, `screener-watchlist` en `screener.yml`, que corre TODOS los días (mismo cron) y llama a `run_job.py --list watchlist` — un modo especial que, en vez de usar `get_tickers()`, lee los tickers directo de `alert_watchlist` en D1 y los procesa con `compute_all()` igual que cualquier otra lista, guardando bajo `list_id='watchlist'` en `screener_results`/`signal_history`. Así CUALQUIER ticker que el usuario cargue en 🔔 Alertas queda cubierto, esté o no en las listas grandes. Si la watchlist está vacía, el job no hace nada (sale al toque, sin gastar tiempo de CI). **A propósito no se agregó como pestaña navegable en la UI** (solo sirve para alertas, no para mirar el análisis técnico en la web).
- **Nombres de tickers fuera de listas**: `_TICKER_NAMES` en `screener.py` tiene una sub-sección de "Extras" para tickers que pueden terminar en una watchlist de alertas sin estar en ninguna lista fija (ej. `MSTR: MicroStrategy`) — si falta, el ticker se analiza y alerta igual de bien, solo se pierde el nombre lindo en el mensaje (queda el ticker pelado).
- **Gap conocido — cripto en la watchlist puede quedar sin analizar (2026-09-11)**: `compute_all()` trae el historial diario de cripto SOLO de Binance (`_fetch_all_binance_daily` en `screener.py`) — Binance geobloquea IPs de datacenter de forma intermitente, y las corridas de GitHub Actions arrancan cada vez en una VM nueva con una IP al azar del pool de Azure, así que un día pasa y otro no (confirmado en vivo: la misma fecha, la lista `crypto` procesó 23/23 tickers pero `watchlist` solo 4/9 — los 5 tickers de cripto se cayeron en silencio esa corrida). Se evaluó un fallback automático a otro proveedor y se descartó a propósito: CryptoCompare ahora exige API key hasta en su tier gratis (probado en vivo, 401 "API key required" — esto probablemente también rompió en silencio el fallback de precio ya existente para la lista `crypto`, `fetch_crypto_prices()` en `run_job.py`, pendiente de revisar), y CoinGecko solo da velas diarias reales (high/low) para los últimos ~30 días gratis — más allá de eso solo da precio de cierre, sin high/low/volumen reales, insuficiente para ATR/ADX/zona sin degradar el análisis en silencio. **Decisión**: preferible no tener análisis ese día a tener uno con apariencia normal pero mal fundado. En vez de eso se agregó un botón manual — "🔄 Reintentar análisis de hoy" en la sección 🔔 Alertas del frontend — que llama a `POST /api/refresh` con `list_id: "watchlist"` (mismo endpoint que ya usa el botón "Analizar" de las otras listas). Esto dispara un `repository_dispatch` que ahora sí cubre `watchlist` (el job `screener-watchlist` en `screener.yml` amplió su condición para aceptarlo, antes solo corría por `schedule`/`workflow_dispatch`) — al ser una VM nueva, hay otra chance de que la IP no esté bloqueada. Sigue siendo un reintento, no una garantía.
- **Cadencia configurable de la watchlist (2026-09-11)**: `watchlist-alerts.yml` corre cada hora (antes: una vez por día) — más chances de esquivar el bloqueo de Binance, y análisis más fresco durante el día. El propio job decide si esa corrida analiza de verdad o sale al toque, según `alert_watchlist_config` en D1 (intervalo mínimo 1 hora + rango horario en ART, ajustable desde el panel 🔔 Alertas de la web vía `GET/POST /api/alerts/config`) — ver `is_watchlist_run_due()` en `run_job.py`. El botón de reintento manual pasa `--force` a `run_job.py` para saltarse esta config (siempre corre, sin importar la hora o cuánto pasó desde la última corrida).
- **Comparación de señal contra la corrida anterior, no contra "ayer" (2026-09-11)**: al subir la cadencia de una vez por día a cada hora apareció un bug real — `get_previous_signal()` comparaba siempre contra la última señal de un DÍA anterior (`signal_history`, un registro por fecha). Con una sola corrida diaria eso era correcto, pero con corridas cada hora rompía en dos direcciones: reavisaba lo mismo muchas veces si un ticker se quedaba varias horas en `compra_fuerte`/`venta_fuerte` (porque cada corrida lo comparaba contra el mismo "ayer" fijo), y podía perderse un vaivén entero dentro del mismo día si a la noche la señal volvía a coincidir con la de ayer. Se reemplazó por una tabla nueva y chica, `alert_last_signal` (`ticker → última señal conocida`, sin fecha), que se actualiza en TODAS las corridas — haya alerta o no — así la comparación siempre es contra el estado real inmediatamente anterior, sea que la corrida anterior fue hace 1 hora o hace 1 día. `signal_history` sigue existiendo tal cual (un registro por día) porque otra parte del código la usa para los % a 5/10/20 días, sin relación con las alertas.
- **Aviso de bienvenida si el ticker ya arranca en zona fuerte (2026-09-11)**: si agregás un ticker a la watchlist y en su primerísima corrida ya está en `compra_fuerte`/`venta_fuerte` (ej. ETH-USD ya veniá pisando fuerte antes de que lo agregaras), antes no avisaba NUNCA — `check_and_send_alerts()` necesita una señal previa para detectar un "cambio", y un ticker recién agregado no tiene ninguna (`prev_signal is None` en `alert_last_signal`). Ahora ese caso puntual manda un aviso distinto y único ("👀 ... ya está en zona de COMPRA/VENTA FUERTE", `build_welcome_alert_message()`), una sola vez — las corridas siguientes mientras se mantenga en la misma señal no repiten nada (se sigue guardando en `alert_last_signal` como de costumbre).

## IA — cadena de proveedores

En el Worker (producción): CF Workers AI → Groq → Gemini (loop, primer éxito gana).
En FastAPI (local): Groq → Gemini.

El prompt está en `worker/src/providers/prompt.py` (`build_prompt()`). El backend local tiene el prompt inlineado en `main.py` (misma lógica).

### Estructura del prompt
- **Persona**: analista experto, español rioplatense, tono amigo exitoso, sin jerga ni markdown
- **Datos incluidos**: señal, dirección, scores, zona, MA5-MA200 (con % distancia), RSI, MACD, Bollinger %B, ADX, vol_ratio, momentum/Pulse, patrón de velas, pivots S1/P/R1, SL/TP
- **Output**: 4-5 oraciones corridas, empezando por la conclusión, 2-3 datos clave, señal de falla, perspectiva de riesgo
- **Modelos**: `openai/gpt-oss-120b` (Groq), `gemini-3.5-flash-lite` (Gemini), `@cf/meta/llama-3.3-70b-instruct-fp8-fast` (CF AI)

## Decisiones técnicas

- **Descarga bulk**: `yf.download("AAPL MSFT ...", period="1y")` — un solo request HTTP para todos los tickers.
- **Multi-level columns**: yfinance con un solo ticker no genera columnas multi-nivel. `screener.py` maneja ambos casos.
- **Fuente S&P 500**: CSV de GitHub. Wikipedia devuelve 403 con `pd.read_html`.
- **yfinance**: pinneado a `==1.3.0` en `requirements.txt` para que local y GitHub Actions usen exactamente la misma versión (versiones anteriores fallan con `JSONDecodeError`; versiones distintas producen scores diferentes).
- **MTF aproximado**: temporalidades reales (15m/1h/4h) no disponibles con datos diarios. Se usan 4 señales de EMAs diarias.
- **Pine Script originales**: en `c:\Users\Compu\Documents\Dev\Finanzas\suite indicators\`.

## UI — diseño actual

- **Acento**: ámbar/dorado (`amber-500`, `#f59e0b`)
- **Header**: `bg-slate-900` con borde top `3px solid #f59e0b` — "máximos" en blanco, status dot
- **Fondo principal**: `bg-gray-50`
- **Modales (BottomSheet)**: `bg-slate-50`
- **TickerModal header**: `bg-slate-900` con borde top amber, texto blanco
- **SummaryCards**: borde izquierdo de color por señal, número en color, `border-l-4`
- **TickerModal layout desktop**: 2 columnas — izquierda (Niveles de Riesgo + Pulse) / derecha (Analistas + Medias Móviles + Pivots)
- **Medias Móviles**: grid MA5→MA200 con badge ↑/↓, barra proporcional, precio y % distancia
- **Pivots**: toggle Classic / Fibonacci, niveles R3→S3 con color coding (rojo=resistencia, verde=soporte)
- **Patrón de velas**: badge con nombre y tipo (alcista/bajista/indecisión) en TickerModal header
- **TradingView ↗**: botón en el modal que abre el chart con el ticker precargado. Crypto: `BTC-USD` → `BTCUSDT`. Futuros: ticker original (`GC=F`)

## Roadmap

### Features completadas recientemente
- [x] Gráfico de precio al hacer click en un ticker (TradingView mini + fullscreen)
- [x] MA5/MA10/MA20 + grilla de medias móviles en el modal
- [x] Pivot points Classic y Fibonacci con toggle
- [x] Patrones de velas detectados (hammer, doji, engulfing, etc.)
- [x] Rediseño UI: header oscuro, acento ámbar, cards con borde de color
- [x] start-all.ps1 / stop-all.ps1 — arranca los 4 procesos sin ventanas de terminal
- [x] Finanzas conectado a Cloudflare Worker para precios (no requiere maximos local)
- [x] Modal ⚙️ en finanzas para alternar fuente de precios online/local
- [x] Agente de finanzas con precios de mercado reales y valuación completa de cartera
- [x] Auto-creación de posiciones al guardar transacciones (individual y batch)
- [x] /api/crypto-quotes en backend local (Binance) y Worker
- [x] Worker: /api/quotes usa D1 para acciones y Binance para cripto (Yahoo Finance bloqueado)
- [x] Lista de commodities (Gold, Silver, WTI, Wheat, etc.) con nombres legibles
- [x] Botón TradingView ↗ en modal de ticker
- [x] Accesos directos en escritorio (Iniciar/Detener Finanzas)
- [x] Panel de API keys en ⚙️ de finanzas (configura ambos backends)
- [x] CEDEARs con ratio en Portfolio y cálculo correcto en Patrimonio
- [x] Fix USDT plazo fijo vs flexible: sync descuenta posiciones fixed_term activas
- [x] Fix avg_price: se preserva cuando hay compras sin unit_price
- [x] Portfolio muestra costo histórico (ARS para CEDEARs, USD para crypto/stocks) + cantidad
- [x] P&L visible en Patrimonio para posiciones flexible con crypto (ETH staking, etc.)
- [x] Labels contextuales en formulario de movimientos para CEDEARs
- [x] Transferencias entre cuentas: formulario crea egreso en origen e ingreso en destino en un solo paso (fix bug edición)
- [x] Portfolio muestra valor de mercado USD actual para crypto/stocks (prices compartidos desde App)
- [x] `_sync_position`: avg_price se recalcula con nueva compra incluso si hay transferencias sin precio en el historial
- [x] Portfolio AccountCard muestra precio promedio de compra y % P&L por posición crypto/stock
- [x] Agente IA: análisis técnico del screener integrado al contexto (RSI, ADX, MACD, EMAs, zona, SL/TP)
- [x] Agente IA: crypto prices directo a Binance desde backend local (evita fallo del Worker con Binance)
- [x] Agente IA: posiciones flexible no-fiat (ETH staking) obtienen precio de mercado real
- [x] Conversación del agente persiste al cambiar de tab
- [x] Fix: env.DB → env.maximos_db en Worker /api/quotes para stocks desde D1
- [x] Agente IA: fundamentales y consenso de analistas (Yahoo Finance /api/info) para stocks y CEDEARs — recommendation_key, target price, PE, beta, earnings date
- [x] Agente IA: sentimiento crypto — Fear & Greed (alternative.me) + CoinGecko global (BTC dominance, market cap) + datos por coin (rank, ATH, market cap) + Binance Futures (funding rate, OI, L/S ratio)
- [x] Panel ⚙️ agrega CoinGecko API key (demo gratuita) con show/hide y badge de estado
- [x] Fix: GET /api/config lee .env directo (dotenv_values) en vez de os.environ — evita que la key desaparezca al reabrir el panel
- [x] Monorepo restructurado: archivos movidos a `maximos/`, GitHub repo renombrado a `finanzas-suite`
- [x] Asistente fiscal `fiscal/` — scaffold completo (FastAPI 8002, Vite 5175, AFIP SDK, teal accent)
- [x] Launcher `launcher/` — home page unificado (FastAPI 8099, Vite 5172) con cards de status, botones Abrir/Iniciar y config unificado de API keys
- [x] `start-all.ps1` arranca los 8 procesos, auto-libera puertos y abre solo el launcher
- [x] `strictPort: true` en todos los vite.config.js — evita que vite cambie puertos silenciosamente
- [x] `/api/health` en maximos backend — necesario para el status check del launcher
- [x] ADRs argentinos: 2 tickers rotos corregidos (PAMP→PAM, TGSU2→TGS) + 4 ADRs reales agregados (TS, TEO, CAAP, AGRO)
- [x] Nombre completo del ticker al pasar el mouse en toda la app (sp500 desde el CSV de origen, cripto en vivo desde CoinGecko, resto en mapa a mano)
- [x] Alertas push (ntfy.sh) por señal fuerte para una lista corta de tickers vigilados, con noticias del propio ticker incluidas

### Features pendientes
- [ ] Alertas: incorporar noticias de mercado/sector (no solo del propio ticker) + juicio de relevancia vía IA — evaluado, requiere primero una fuente de noticias de mercado que hoy no existe
- [ ] MTF real con descarga intraday para 15m/1h/4h
- [ ] Lista personalizada (custom tickers) en la UI

## Launcher — home page de la suite

Panel de control unificado en `launcher/`. Punto de entrada único para toda la suite.

### Puertos
- Backend: `8099` (FastAPI)
- Frontend: `5172` (Vite, `strictPort: true`)

### Funciones
- **Cards de apps**: maximos (amber), finanzas (amber), fiscal (teal). Cada card muestra estado en tiempo real (dot verde/gris para backend y frontend), botón **Abrir** (abre en nueva pestaña) y botón **Iniciar** (lanza backend + frontend via subprocess si no están corriendo).
- **Status polling**: `GET /api/apps/status` cada 3s — health check a los 6 puertos de backends y frontends.
- **Config unificado**: modal ⚙️ con secciones IA (Groq, Google), Mercado (CoinGecko) y Fiscal (AFIP SDK). Las keys se escriben en los `.env` de cada app según `KEYS_MAP`.

### KEYS_MAP (launcher/backend/main.py)
| Key | Destino |
|---|---|
| `GROQ_API_KEY` | maximos · finanzas · fiscal |
| `GOOGLE_API_KEY` | maximos · finanzas · fiscal |
| `COINGECKO_API_KEY` | finanzas |
| `AFIPSDK_ACCESS_TOKEN` | fiscal |

### Gotchas — puertos
- Todos los frontends tienen `strictPort: true` en `vite.config.js` — si el puerto está ocupado vite falla en lugar de moverse silenciosamente a otro puerto.
- El puerto de cada frontend se define **solo** en `vite.config.js`, no en el script `"dev"` de `package.json`. Si se hardcodea `--port` en `package.json`, ese flag overridea el config pero no hereda `strictPort`.
- `start-all.ps1` libera los puertos al inicio filtrando conexiones `TimeWait` (estado TCP del kernel, PID 0, no matables). Si el kill filtrara esas conexiones, vite vería el puerto como ocupado y shiftearía.
- El kill en `start-all.ps1` usa `Where-Object { $_.State -ne 'TimeWait' -and $_.OwningProcess -gt 0 }` para matar solo procesos reales.

## Proyecto relacionado — Finanzas Personales

En `finanzas/` vive una app separada de seguimiento de patrimonio personal (cuentas, posiciones, movimientos, agente IA). Tiene su propio backend FastAPI (puerto 8001), frontend Vite (puerto 5174) y base de datos SQLite local.

Ver [finanzas/CLAUDE.md](finanzas/CLAUDE.md) para documentación técnica y [finanzas/README.md](finanzas/README.md) para instrucciones de uso.

La app de finanzas consume los endpoints de precios de maximos para valuar posiciones. Por defecto usa el **Cloudflare Worker** (no requiere maximos local). Desde ⚙️ en el header de finanzas se puede cambiar a local. Ver detalles de flujo de datos en [FLUJO.md](FLUJO.md).

Endpoints consumidos: `/api/dollar`, `/api/quotes`, `/api/crypto-quotes`.

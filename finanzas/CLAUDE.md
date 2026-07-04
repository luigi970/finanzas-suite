# Finanzas Personales — CLAUDE.md

App web local para seguimiento de patrimonio personal: cuentas, posiciones, movimientos e IA.

## Arquitectura

```
finanzas/
├── backend/
│   ├── main.py              # FastAPI, puerto 8001
│   ├── database.py          # SQLite (finanzas.db) + init_db() con migrations
│   ├── routers/
│   │   ├── accounts.py      # CRUD cuentas
│   │   ├── positions.py     # CRUD posiciones + sync desde transacciones
│   │   ├── transactions.py  # CRUD + batch import + CSV export + P&L + auto-crea posición
│   │   ├── ingest.py        # Extracción IA desde PDF/imagen/CSV/texto
│   │   └── agent.py         # Chat IA con precios de mercado reales y cartera completa
│   └── requirements.txt
├── frontend/
│   └── src/App.jsx          # UI completa en un solo archivo (React + Vite)
└── start.ps1                # Arranca backend (8001) y frontend (5174)
```

## Cómo arrancar

### Todo junto (maximos + finanzas)
```powershell
# Desde la raíz del repo
.\start-all.ps1   # arranca los 4 procesos sin ventanas
.\stop-all.ps1    # detiene todo
# También hay accesos directos en el escritorio: "Iniciar Finanzas" y "Detener Finanzas"
```

### Solo finanzas
```powershell
.\finanzas\start.ps1
# Backend:  http://localhost:8001
# Frontend: http://localhost:5174
```

O manualmente:
```powershell
cd finanzas/backend
python -m uvicorn main:app --reload --port 8001

cd finanzas/frontend
npm run dev  # corre en puerto 5174
```

## Variables de entorno (`finanzas/backend/.env`)

```
GROQ_API_KEY=...          # primario para ingest (texto) y agente
GOOGLE_API_KEY=...        # fallback para ingest (visión) y agente
MAXIMOS_URL=...           # opcional; por defecto usa el Cloudflare Worker de maximos
COINGECKO_API_KEY=...     # demo key gratuita — sentimiento crypto en el agente
```

Las keys también se pueden configurar desde la UI: ⚙️ → sección "API Keys". Se guardan automáticamente en `finanzas/backend/.env` y `backend/.env` (maximos) en simultáneo. `GET /api/config` lee directamente del archivo `.env` (no de `os.environ`) para reflejar siempre el estado real del disco.

## API endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/accounts` | Listar cuentas activas |
| POST | `/api/accounts` | Crear cuenta |
| PATCH | `/api/accounts/{id}` | Editar cuenta |
| DELETE | `/api/accounts/{id}` | Eliminar cuenta (cascade) |
| GET | `/api/positions` | Listar posiciones |
| POST | `/api/positions` | Crear posición |
| PATCH | `/api/positions/{id}` | Editar posición |
| DELETE | `/api/positions/{id}` | Eliminar posición |
| POST | `/api/positions/sync/{account_id}` | Recalcular cantidades desde transacciones (descuenta fixed_term/fund) |
| POST | `/api/positions/create-missing` | Crear posiciones faltantes desde historial de transacciones |
| GET | `/api/transactions` | Listar (limit=500 por defecto) |
| POST | `/api/transactions` | Crear una transacción (auto-crea posición si no existe) |
| PATCH | `/api/transactions/{id}` | Editar transacción (recalcula P&L) |
| DELETE | `/api/transactions/{id}` | Eliminar |
| POST | `/api/transactions/batch` | Importar lote — también auto-crea posiciones faltantes |
| GET | `/api/transactions/export` | Descarga CSV |
| GET | `/api/transactions/summary` | Resumen por mes/categoría/P&L |
| POST | `/api/ingest/text` | Extraer transacciones desde texto |
| POST | `/api/ingest/file` | Extraer desde PDF/imagen/CSV |
| POST | `/api/agent/chat` | Chat IA con contexto financiero completo |
| GET | `/api/config` | Devuelve GROQ, GOOGLE y COINGECKO keys (lee del .env directo) |
| POST | `/api/config` | Escribe keys en .env de finanzas y maximos |
| GET | `/api/maximos/status` | Chequea si maximos local (puerto 8000) está corriendo |
| POST | `/api/maximos/start` | Arranca maximos local (uvicorn en puerto 8000) |

## Base de datos (SQLite)

`database.py` crea las tablas si no existen y corre migrations via `ALTER TABLE ADD COLUMN` en try/except.

### Tablas principales

**accounts**: `id, name, type (bank|exchange|wallet_crypto|wallet|broker|cash|other), color, active`

**positions**: `id, account_id, asset, asset_type (fiat|crypto|stablecoin|stock|cedear|fixed_term|fund|flexible), quantity, avg_price, start_date, end_date, rate, auto_renew, notes`

**transactions**: `id, account_id, date, description, amount, currency, type (income|expense|transfer), category, source, unit_price, realized_pnl, fee, fee_currency`

## Lógica clave

### P&L realizado
- **expense con unit_price**: `realized_pnl = (unit_price - avg_price) × amount` usando el avg_price actual de la posición
- Busca posición con `end_date IS NULL OR end_date = ''` (posiciones activas)
- Solo aplica a activos no fiat (`FIAT_CURRENCIES = {ARS, USD, EUR, BRL, UYU}`)

### `_sync_position` (transactions.py)
Recalcula `quantity` y `avg_price` de la posición desde todos los movimientos. Reglas:
- **Quantity**: suma ingresos - egresos de todas las transacciones del activo en la cuenta, **menos** lo que ya está en posiciones `fixed_term`/`fund` activas (con `end_date` futura). Esto evita que el flexible duplique lo que está en plazo fijo.
- **avg_price**: se recalcula (media ponderada) usando **solo** las transacciones de ingreso que tienen `unit_price > 0`. Las transferencias (sin `unit_price`) se ignoran — no bloquean el cálculo ni distorsionan el promedio. Si no hay ninguna compra con precio, se preserva el `avg_price` existente (puede ser manual).
- Se llama automáticamente después de crear, editar o eliminar una transacción.
- El botón 🔄 por cuenta en Portfolio también lo dispara vía `POST /api/positions/sync/{account_id}`.

### CEDEARs
- `asset_type = 'cedear'`, `asset` = ticker subyacente (ej. `AAPL`)
- **`rate`** = ratio: cuántos CEDEARs equivalen a 1 acción subyacente (ej. 20 para AAPL)
- **`avg_price`** = precio promedio pagado en **ARS** por CEDEAR (no en USD)
- En PatrimonioTab: `priceUSD = stockPriceUSD / ratio`; `costUSD = (qty × avg_price_ARS) / blueRate`
- El Portfolio muestra `ratio N` en vez de `N% anual` para CEDEARs

### Posiciones flexible con crypto
Las posiciones `asset_type = 'flexible'` con activos no-fiat/no-stablecoin (ej. ETH en Nexo staking) obtienen precio de mercado igual que crypto normal. El interés devengado se suma a la cantidad en la moneda nativa antes de calcular el valor en USD.

### Auto-creación de posiciones desde transacciones
Tanto `POST /api/transactions` como `POST /api/transactions/batch` crean automáticamente una posición si el activo no tiene posición activa en esa cuenta.

### Interés devengado (frontend, `calcAccruedInterest`)
- Para `asset_type = 'fixed_term'`, `'fund'` o `'flexible'` con `rate` y `start_date`
- `accrued = quantity × (rate/100) × days_elapsed/365`
- Se suma al valor del activo en el cálculo del patrimonio total

### Ingest IA
- Cadena: Groq (texto/visión) → Gemini (fallback visión)
- El prompt extrae: date, description, amount, currency, type, category, unit_price, fee, fee_currency
- Tipos válidos: `income | expense | transfer` (el batch sanitiza tipos inválidos a 'expense')
- Fechas inválidas (ej. 'N/A') se reemplazan por la fecha actual

### Agente IA (`routers/agent.py`)
- Cadena: Groq → Gemini fallback
- Fuentes de precios:
  - **Crypto** (asset_type `crypto` o `flexible` no-fiat): directo a Binance desde el backend local — evita dependencia del CF Worker que puede tener problemas alcanzando Binance desde datacenter
  - **Stocks / CEDEARs**: `MAXIMOS_URL/api/quotes` → D1 (precio del último screener)
  - **Dólar blue**: `MAXIMOS_URL/api/dollar` → dolarapi.com
- `to_yahoo_ticker`: maneja `flexible` no-fiat como crypto (devuelve `ASSET-USD`)
- `build_price_context()`: valuación completa de cartera con precio actual × cantidad, P&L no realizado (vs precio promedio de compra) y precio promedio explícito en cada posición. End_date/tasa/notas incluidas para plazos fijos.
- `build_technical_context()`: consulta `MAXIMOS_URL/api/stocks` para cada lista relevante (crypto, adrs_arg, sp500) y agrega señal, score, zona, RSI, ADX, MACD, volumen, EMAs MA20/50/200, patrón de velas y SL/TP de cada activo en cartera.
- `build_fundamentals_context()`: consulta `MAXIMOS_URL/api/info` para cada stock/CEDEAR en cartera. Agrega nombre, sector, consensus de analistas (recommendation_key + cantidad), target price con rango, PE forward/trailing, beta, dividendo y próximo earnings date. Solo para asset_type `stock` y `cedear`. Corre en paralelo con los otros contextos.
- `build_crypto_sentiment_context()`: solo si hay crypto/flexible no-fiat en cartera. Fuentes:
  - **Fear & Greed** (alternative.me): índice 0-100 con clasificación
  - **CoinGecko `/global`** (demo API, `COINGECKO_API_KEY`): BTC dominance, market cap total y cambio 24h
  - **CoinGecko `/coins/markets`**: rank, ATH y % desde ATH, market cap y cambio 24h por coin en cartera. `COINGECKO_IDS` mapea symbols a IDs de CoinGecko (BTC→bitcoin, ETH→ethereum, etc.)
  - **Binance Futures** (público, sin key): funding rate, open interest y L/S ratio para BTC/ETH/SOL/BNB/XRP
- `_calc_accrued(p)`: replica el JS `calcAccruedInterest` — `quantity × (rate/100) × days/365`
- Los cuatro contextos corren en paralelo con `asyncio.gather()`
- Contexto enviado al modelo: cuentas, valuación con precios reales y P&L por posición, análisis técnico del screener, fundamentales y consenso de analistas, sentimiento y datos de mercado crypto, últimas 50 transacciones, resumen mensual, P&L realizado acumulado, totales en USD y ARS
- SYSTEM_PROMPT: asesor directo que usa números exactos del usuario, toma posición concreta, no aproxima cuando tiene datos exactos, cruza consensus institucional con señal técnica, calcula upside vs target de analistas, usa funding rate y Fear & Greed como contexto macro, filosofía DCA + largo plazo, contexto argentino (blue, CEDEARs, plazo fijo vs inflación)

### Configuración de API keys (`main.py`)
- `GET /api/config`: devuelve los valores actuales de `GROQ_API_KEY` y `GOOGLE_API_KEY` (texto plano, app local)
- `POST /api/config`: recibe `{groq_key, google_key}`, escribe en `finanzas/backend/.env` y `backend/.env` usando `dotenv.set_key()`, y actualiza `os.environ` en el proceso actual
- El backend maximos requiere reinicio para tomar las nuevas keys

### Maximos status/start (main.py)
- `/api/maximos/status`: hace GET a `http://localhost:8000/api/status` con timeout 2s; devuelve `{"running": bool}`
- `/api/maximos/start`: si no está corriendo, lanza `uvicorn main:app --port 8000` en `backend/` con `CREATE_NEW_CONSOLE` (Windows) o proceso daemon (Unix)

## Gotchas

- El frontend hace proxy al backend via Vite (`vite.config.js` → `/api → localhost:8001`)
- `end_date = ''` (string vacío) ≠ `NULL` en SQLite — siempre usar `(end_date IS NULL OR end_date = '')` para posiciones activas
- `prices[ticker]` en el frontend es un objeto `{ price, change, change_pct }`, no un número plano — acceder con `.price`
- `_sync_position` descuenta posiciones `fixed_term`/`fund` activas (end_date futura) para no duplicar en flexible
- `_sync_position` recalcula `avg_price` solo desde ingresos con `unit_price > 0` — las transferencias sin precio no bloquean el cálculo. Si no hay compras con precio, preserva el avg_price manual.
- CEDEARs: `rate` = ratio (no tasa de interés), `avg_price` en ARS (no USD)
- `$pid` es variable reservada en PowerShell — usar `$procId` en stop-all.ps1
- `Test-NetConnection` es más confiable que `Invoke-WebRequest` para port polling en ventanas ocultas de PowerShell
- **Binance desde CF Worker**: el Worker puede tener problemas alcanzando `api.binance.com` desde datacenter. El agente fetchea crypto directo a Binance desde el backend local para evitarlo.
- **`env.DB` vs `env.maximos_db`**: el binding D1 en el Worker se llama `maximos_db` (ver `wrangler.toml`). Usar siempre `env.maximos_db`, nunca `env.DB`.
- **`flexible` no-fiat en `to_yahoo_ticker`**: posiciones con `asset_type='flexible'` y activo crypto (ej. ETH en Nexo staking) deben devolver `ETH-USD`, no `ETH`. El caso está manejado explícitamente.
- **`GET /api/config` lee del .env directo**: usa `dotenv_values(ENV_PATH)` en cada request para reflejar el estado real del archivo, no `os.environ` que solo refleja lo que había al iniciar el servidor.
- **CoinGecko keyless vs demo**: la API pública sin key tiene rate limits muy bajos (10-30/min, compartido por IP). Usar siempre la demo key gratuita via header `x-cg-demo-api-key`. Se configura en ⚙️ o directamente en `.env` como `COINGECKO_API_KEY`.
- **Binance Futures público**: `fapi.binance.com` es accesible sin API key para datos de mercado (funding rate, OI, L/S ratio). Distinto de `api.binance.com` (spot) que también es público.

## UI

- React + Vite, un solo archivo `App.jsx`
- Tailwind CSS, acento ámbar (`amber-500`)
- Header oscuro (`bg-slate-900`) con borde top `3px solid #f59e0b`
- Tabs sticky: Patrimonio · Portfolio · Movimientos · Cuentas · Agente
- `SettingsModal`: abre con ⚙️; toggle Online/Local para precios; sección API Keys con inputs show/hide para configurar Groq, Google y CoinGecko sin tocar el .env. Las tres son gratuitas.
- Portfolio: botón 🔄 por cuenta para disparar sync de posiciones. Usa `max-w-6xl`.
- Portfolio AccountCard: CEDEARs muestran costo total en ARS + cantidad; crypto/stocks/flexible muestran valor de mercado USD actual + cantidad + línea de precio promedio de compra con % P&L en verde/rojo (`prom. USD X · ±Y%`). Fallback a costo histórico si no hay precio disponible. Scroll activado solo cuando hay más de 10 posiciones.
- `MovimientosTab`: tabla con scroll horizontal (`max-w-6xl`). Columnas: Fecha · Cuenta · Descripción · Categoría · Tipo · Monto · Precio unit. · P&L realizado · Comisión · (✏️ 🗑 on hover). El modal de carga de movimientos no cambió.
- `prices` y `blueRate` viven en `App` y se fetchean una vez al cargar posiciones — compartidos entre `PatrimonioTab` y `PortfolioTab`.
- `chatMessages` vive en `App` (constante `INITIAL_MESSAGES`) — persiste entre tabs sin reiniciar la conversación.
- `PatrimonioTab`: flexible no-fiat obtiene precio de mercado y muestra P&L igual que crypto; CEDEARs usan ratio para calcular priceUSD
- Formulario de movimientos: labels contextuales para CEDEARs (Monto/Cantidad, Moneda/Activo, precio en ARS vs USD)
- Transferencias entre cuentas: el formulario envía `_transfer_to` en un solo `onSave`. `saveTransaction` hace PATCH del egreso en origen y POST del ingreso en destino — evita el bug donde editar a tipo transferencia sobreescribía el mismo registro dos veces.
- Constantes de URL en App.jsx:
  - `MAXIMOS_LOCAL = 'http://localhost:8000'`
  - `MAXIMOS_ONLINE = import.meta.env.VITE_MAXIMOS_URL || 'https://maximos-worker.luchotour.workers.dev'`
- `maximosMode` persiste en `localStorage` ('online' por defecto)

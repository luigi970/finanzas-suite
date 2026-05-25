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
GROQ_API_KEY=...       # primario para ingest (texto) y agente
GOOGLE_API_KEY=...     # fallback para ingest (visión) y agente
MAXIMOS_URL=...        # opcional; por defecto usa el Cloudflare Worker de maximos
```

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
| POST | `/api/positions/sync/{account_id}` | Recalcular cantidades desde transacciones |
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
| GET | `/api/maximos/status` | Chequea si maximos local (puerto 8000) está corriendo |
| POST | `/api/maximos/start` | Arranca maximos local (uvicorn en puerto 8000) |

## Base de datos (SQLite)

`database.py` crea las tablas si no existen y corre migrations via `ALTER TABLE ADD COLUMN` en try/except.

### Tablas principales

**accounts**: `id, name, type (bank|crypto|broker|cash|other), color, active`

**positions**: `id, account_id, asset, asset_type (fiat|crypto|stablecoin|stock|cedear|fixed_term|fund|flexible), quantity, avg_price, start_date, end_date, rate, auto_renew, notes`

**transactions**: `id, account_id, date, description, amount, currency, type (income|expense|transfer), category, source, unit_price, realized_pnl, fee, fee_currency`

## Lógica clave

### P&L realizado (`_apply_unit_price` en transactions.py)
- **income**: actualiza `avg_price` de la posición con media ponderada
- **expense**: calcula `realized_pnl = (unit_price - avg_price) × amount`
- Busca posición con `end_date IS NULL OR end_date = ''` (posiciones activas)
- Solo aplica a activos no fiat (`FIAT_CURRENCIES = {ARS, USD, EUR, BRL, UYU}`)

### Auto-creación de posiciones desde transacciones
Tanto `POST /api/transactions` (individual) como `POST /api/transactions/batch` crean automáticamente una posición si el activo no tiene posición activa en esa cuenta. La cantidad se calcula sumando ingresos y restando egresos del historial. Si la cantidad resultante es ≤ 0, no se crea posición.

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
- Fuente de precios: `MAXIMOS_URL` (env var, por defecto `https://maximos-worker.luchotour.workers.dev`)
  - `GET /api/dollar` → tasa blue ARS/USD
  - `GET /api/quotes?symbols=...` → precios de acciones/CEDEARs desde D1
  - `GET /api/crypto-quotes?symbols=...` → precios de cripto desde Binance
- `build_price_context()`: obtiene todos los precios necesarios para valuar la cartera
- `_calc_accrued(p)`: replica el JS `calcAccruedInterest` — `quantity × (rate/100) × days/365`
- Contexto enviado al modelo: cuentas, posiciones con valor en USD, P&L no realizado, últimas 50 transacciones, resumen mensual, P&L realizado acumulado, totales en USD y ARS
- SYSTEM_PROMPT: asesor financiero personal, español rioplatense, profesional y directo, responde solo lo que se le pregunta, máximo 4 oraciones salvo análisis detallado explícito

### Maximos status/start (main.py)
- `/api/maximos/status`: hace GET a `http://localhost:8000/api/status` con timeout 2s; devuelve `{"running": bool}`
- `/api/maximos/start`: si no está corriendo, lanza `uvicorn main:app --port 8000` en `backend/` con `CREATE_NEW_CONSOLE` (Windows) o proceso daemon (Unix)

## Gotchas

- El frontend hace proxy al backend via Vite (`vite.config.js` → `/api → localhost:8001`)
- `end_date = ''` (string vacío) ≠ `NULL` en SQLite — siempre usar `(end_date IS NULL OR end_date = '')` para posiciones activas
- `prices[ticker]` en el frontend es un objeto `{ price, change, change_pct }`, no un número plano — acceder con `.price`
- El batch endpoint llama `_apply_unit_price` por cada transacción — el orden importa para el avg_price
- Las posiciones de tipo `fixed_term`/`fund`/`flexible` no tienen precio de mercado; el valor se calcula desde la moneda nativa + interés devengado
- `$pid` es variable reservada en PowerShell — usar `$procId` en stop-all.ps1
- `Test-NetConnection` es más confiable que `Invoke-WebRequest` para port polling en ventanas ocultas de PowerShell

## UI

- React + Vite, un solo archivo `App.jsx`
- Tailwind CSS, acento ámbar (`amber-500`)
- Header oscuro (`bg-slate-900`) con borde top `3px solid #f59e0b`
- Tabs sticky: Patrimonio · Portfolio · Movimientos · Cuentas · Agente
- `SettingsModal`: abre con ⚙️ en el header; toggle Online/Local para la fuente de precios; si está en Local, muestra status de maximos y botón para arrancarlo
- Constantes de URL en App.jsx:
  - `MAXIMOS_LOCAL = 'http://localhost:8000'`
  - `MAXIMOS_ONLINE = import.meta.env.VITE_MAXIMOS_URL || 'https://maximos-worker.luchotour.workers.dev'`
- `maximosMode` persiste en `localStorage` ('online' por defecto)
- `PatrimonioTab` recibe `maximosUrl` como prop y está en las deps del `useCallback` de precios para que el cambio de modo recargue los precios automáticamente

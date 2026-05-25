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
│   │   ├── transactions.py  # CRUD + batch import + CSV export + P&L
│   │   ├── ingest.py        # Extracción IA desde PDF/imagen/CSV/texto
│   │   └── agent.py         # Chat IA con contexto financiero del usuario
│   └── requirements.txt
├── frontend/
│   └── src/App.jsx          # UI completa en un solo archivo (React + Vite)
└── start.ps1                # Arranca backend (8001) y frontend (5174)
```

## Cómo arrancar

```powershell
.\start.ps1
# Backend:  http://localhost:8001
# Frontend: http://localhost:5174
```

O manualmente:
```powershell
# Backend
cd backend
python -m uvicorn main:app --reload --port 8001

# Frontend
cd frontend
npm run dev  # corre en puerto 5174
```

## Variables de entorno (`backend/.env`)

```
GROQ_API_KEY=...       # primario para ingest (texto) y agente
GOOGLE_API_KEY=...     # fallback para ingest (visión) y agente
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
| GET | `/api/transactions` | Listar (limit=500 por defecto) |
| POST | `/api/transactions` | Crear una transacción |
| PATCH | `/api/transactions/{id}` | Editar transacción (recalcula P&L) |
| DELETE | `/api/transactions/{id}` | Eliminar |
| POST | `/api/transactions/batch` | Importar lote (desde ingest) |
| GET | `/api/transactions/export` | Descarga CSV |
| GET | `/api/transactions/summary` | Resumen por mes/categoría/P&L |
| POST | `/api/ingest/text` | Extraer transacciones desde texto |
| POST | `/api/ingest/file` | Extraer desde PDF/imagen/CSV |
| POST | `/api/agent/chat` | Chat IA con contexto financiero |

## Base de datos (SQLite)

`database.py` crea las tablas si no existen y corre migrations via `ALTER TABLE ADD COLUMN` en try/except.

### Tablas principales

**accounts**: `id, name, type (bank|crypto|broker|cash|other), color, active`

**positions**: `id, account_id, asset, asset_type (fiat|crypto|stablecoin|stock|cedear|fixed_term|fund), quantity, avg_price, start_date, end_date, rate, auto_renew, notes`

**transactions**: `id, account_id, date, description, amount, currency, type (income|expense|transfer), category, source, unit_price, realized_pnl, fee, fee_currency`

## Lógica clave

### P&L realizado (`_apply_unit_price` en transactions.py)
- **income**: actualiza `avg_price` de la posición con media ponderada
- **expense**: calcula `realized_pnl = (unit_price - avg_price) × amount`
- Busca posición con `end_date IS NULL OR end_date = ''` (posiciones activas)
- Solo aplica a activos no fiat (`FIAT_CURRENCIES = {ARS, USD, EUR, BRL, UYU}`)

### Interés devengado (frontend, `calcAccruedInterest`)
- Para `asset_type = 'fixed_term'` o `'fund'` con `rate` y `start_date`
- `accrued = quantity × (rate/100) × days_elapsed/365`
- Se suma al valor del activo en el cálculo del patrimonio total

### Ingest IA
- Cadena: Groq (texto/visión) → Gemini (fallback visión)
- El prompt extrae: date, description, amount, currency, type, category, unit_price, fee, fee_currency
- Tipos válidos: `income | expense | transfer` (el batch sanitiza tipos inválidos a 'expense')
- Fechas inválidas (ej. 'N/A') se reemplazan por la fecha actual

### Agente IA
- Cadena: Groq → Gemini fallback
- Contexto: cuentas, posiciones (con avg_price y rate), últimas 50 transacciones (con P&L y fees), resumen mensual, P&L realizado acumulado, comisiones totales

## Gotchas

- El frontend hace proxy al backend via Vite (`vite.config.js` → `/api → localhost:8001`)
- `end_date = ''` (string vacío) ≠ `NULL` en SQLite — siempre usar `(end_date IS NULL OR end_date = '')` para posiciones activas
- `prices[ticker]` en el frontend es un objeto `{ price, change, change_pct }`, no un número plano — acceder con `.price`
- El batch endpoint llama `_apply_unit_price` por cada transacción — el orden importa para el avg_price
- Las posiciones de tipo `fixed_term`/`fund` no tienen precio de mercado; el valor se calcula desde la moneda nativa + interés devengado

## UI

- React + Vite, un solo archivo `App.jsx`
- Tailwind CSS, acento ámbar (`amber-500`)
- Header oscuro (`bg-slate-900`) con borde top `3px solid #f59e0b`
- Tabs sticky: Patrimonio · Portfolio · Movimientos · Cuentas · Agente
- Fuentes de precio: maximos en `localhost:8000` (dólar blue + cotizaciones Yahoo Finance)

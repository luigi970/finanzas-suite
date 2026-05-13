# Stock Screener — S&P 500

App web que analiza las 503 acciones del S&P 500 e indica cuáles están en máximo histórico y cuáles en oportunidad de compra.

## Stack

- **Backend**: Python 3.12 + FastAPI + yfinance
- **Frontend**: React 18 + Tailwind CSS 3 + Vite 6

## Estructura

```
maximos/
├── backend/
│   ├── main.py        # API FastAPI (endpoints REST)
│   ├── screener.py    # Lógica: descarga bulk, RSI, clasificación
│   ├── requirements.txt
│   └── .env           # POLYGON_API_KEY (no usar, limitada a 5 req/min)
├── frontend/
│   └── src/
│       └── App.jsx    # UI completa (tabla, filtros, barra de progreso)
└── start.ps1          # Levanta backend y frontend en paralelo
```

## Cómo arrancar

```powershell
# Opción 1 — script automático
.\start.ps1

# Opción 2 — manual (dos terminales)
cd backend && uvicorn main:app --reload --port 8000
cd frontend && npm run dev
```

Frontend: http://localhost:5173  
Backend: http://localhost:8000

## API endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/status` | Estado actual del análisis y progreso |
| GET | `/api/stocks?category=all` | Lista de acciones (filtro: all / maximo / oportunidad / neutral) |
| POST | `/api/refresh` | Dispara un nuevo análisis en background |

## Lógica de clasificación

| Categoría | Criterio |
|---|---|
| `maximo` | Precio actual >= 95% del máximo de 52 semanas |
| `oportunidad` | RSI < 35 **y** precio <= 110% del mínimo de 52 semanas |
| `neutral` | El resto |

## Decisiones técnicas importantes

- **Descarga bulk**: `yf.download("AAPL MSFT ...", period="1y")` descarga los 503 tickers en un solo request HTTP (~15s). Mucho más rápido que requests individuales.
- **threading.Lock en main.py**: el callback `on_result` es llamado desde un thread de background mientras FastAPI lee `_cache["data"]` desde otro. El lock evita corrupción de datos.
- **Fuente de tickers**: CSV público de GitHub (`datasets/s-and-p-500-companies`). Wikipedia devuelve 403.
- **Polygon.io**: cuenta creada pero free tier limitado a 5 requests simultáneos — descartado. yfinance es suficiente.
- **Datos**: Yahoo Finance vía yfinance 1.3.0+ (versiones anteriores fallan con JSONDecodeError).

## Instalación desde cero

```powershell
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

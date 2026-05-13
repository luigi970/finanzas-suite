# Stock Screener

App web que analiza acciones del S&P 500, Nasdaq 100, ETFs, ADRs Argentina y listas personalizadas. Asigna un **Score 0-100** combinando indicadores técnicos profesionales y clasifica cada activo en 5 señales: Compra Fuerte, Compra, Neutral, Venta, Venta Fuerte.

## Stack

- **Backend**: Python 3.12 + FastAPI + yfinance
- **Frontend**: React 18 + Tailwind CSS 3 + Vite 6

## Estructura

```
maximos/
├── backend/
│   ├── main.py          # API FastAPI — endpoints REST + cache en memoria
│   ├── screener.py      # Descarga bulk, indicadores, scoring compuesto
│   ├── requirements.txt
│   └── .env             # POLYGON_API_KEY (no usar — free tier limitado a 5 req/min)
├── frontend/
│   └── src/
│       └── App.jsx      # UI completa: selector de lista, tabla, filtros, modal de ayuda
├── CLAUDE.md
├── README.md
└── start.ps1            # Levanta backend y frontend en paralelo
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
Backend:  http://localhost:8000

## API endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/status` | Estado del análisis, progreso y list_id activo |
| GET | `/api/stocks?signal=all` | Activos filtrados por señal |
| GET | `/api/lists` | Listas disponibles con conteo |
| POST | `/api/refresh` | Lanza análisis en background (`list_id` + `custom[]`) |

### Body de /api/refresh

```json
{ "list_id": "sp500", "custom": [] }
```

`list_id` puede ser: `sp500`, `nasdaq100`, `etfs`, `adrs_arg`, `custom`

## Scoring compuesto (0-100)

| Componente | Pts | Criterio alcista |
|---|---|---|
| Tendencia MA | 30 | Precio > MA200 (+20), MA50 > MA200 (+10) |
| RSI | 20 | Zona 40-60 (+20), <30 (+15), >70 (-10) |
| MACD | 20 | Histograma > 0 (+12), MACD > Signal (+8) |
| Volumen | 15 | Vol ratio ≥ 1.5x (+15), ≥ 1.2x (+8) |
| Bollinger %B | 15 | %B < 0.2 (+15 — cerca de banda inferior) |

### Señales por score

| Score | Señal |
|---|---|
| ≥ 75 | `compra_fuerte` |
| 60-74 | `compra` |
| 40-59 | `neutral` |
| 20-39 | `venta` |
| < 20 | `venta_fuerte` |

## Indicadores calculados por ticker

`price`, `score`, `signal`, `rsi`, `ma50`, `ma200`, `pct_vs_ma50`, `pct_vs_ma200`, `macd_hist`, `vol_ratio`, `bb_upper`, `bb_lower`, `pct_b`, `high_52w`, `low_52w`, `pct_from_high`, `pct_from_low`

## Listas de activos

| ID | Descripción | Fuente |
|---|---|---|
| `sp500` | 503 acciones | CSV GitHub `datasets/s-and-p-500-companies` |
| `nasdaq100` | 100 empresas tech | Hardcodeado en `screener.py` |
| `etfs` | 49 ETFs | Hardcodeado en `screener.py` |
| `adrs_arg` | 17 ADRs argentinos | Hardcodeado en `screener.py` |
| `custom` | Libre | Input del usuario |

## Decisiones técnicas importantes

- **Descarga bulk**: `yf.download("AAPL MSFT ...", period="1y")` trae todos los tickers en un solo request HTTP (~15s para 503 tickers). Las versiones anteriores de yfinance usaban requests individuales — mucho más lento.
- **threading.Lock**: el callback `on_result` es llamado desde un thread de background mientras FastAPI sirve `_cache["data"]` desde otro thread. Sin lock se corrompe la lista durante `append` + `sort` simultáneos.
- **Multi-level columns**: cuando yfinance descarga un solo ticker, las columnas no son multi-nivel. El screener maneja ambos casos explícitamente.
- **Fuente de tickers S&P 500**: CSV público de GitHub. Wikipedia devuelve 403 con `pd.read_html`.
- **Polygon.io**: descartado — free tier limitado a 5 requests simultáneos (429 de inmediato con más workers). yfinance es suficiente.
- **yfinance**: requiere versión 1.3.0+. Versiones anteriores fallan con `JSONDecodeError` al descargar datos.
- **Estado `downloading`**: el backend emite dos estados durante el análisis — `downloading` (descarga bulk, sin progreso) y `loading` (cálculo indicador por indicador, con progreso). El frontend muestra barra pulsante en el primero y barra determinada en el segundo.

## Instalación desde cero

```powershell
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

## Roadmap

- [ ] Deploy: backend en Render, frontend en Vercel
- [ ] Cache persistente con PostgreSQL (análisis diario automático)
- [ ] Gráfico de precio al hacer click en un ticker
- [ ] Alertas por email o Telegram
- [ ] Análisis con IA explicando la señal de cada acción

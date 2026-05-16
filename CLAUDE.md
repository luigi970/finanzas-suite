# Stock Screener

App web que analiza acciones, ETFs y criptos. Aplica el sistema **Helper Prime + Helper Pulse** (portado desde Pine Script v6) para asignar un Score 0-100 y clasificar cada activo en 5 señales: Compra Fuerte, Compra, Neutral, Venta, Venta Fuerte.

## Stack

- **Backend**: Python 3.12 + FastAPI + yfinance
- **Frontend**: React 18 + Tailwind CSS 3 + Vite 6

## Estructura

```
maximos/
├── backend/
│   ├── main.py          # API FastAPI — endpoints REST + cache en memoria
│   ├── screener.py      # Helper Prime + Pulse + descarga bulk yfinance
│   ├── requirements.txt
│   └── .env             # POLYGON_API_KEY (descartado — free tier muy limitado)
├── frontend/
│   └── src/
│       └── App.jsx      # UI completa: selector de lista, tabla, filtros, modal de ayuda
├── CLAUDE.md
├── README.md
├── start.ps1            # Levanta backend y frontend (Windows)
└── start.sh             # Levanta backend y frontend (Linux/macOS)
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
| POST | `/api/refresh` | Lanza análisis en background |

### Body de /api/refresh

```json
{ "list_id": "sp500", "custom": [], "crypto_limit": 20 }
```

`list_id` puede ser: `sp500`, `nasdaq100`, `etfs`, `adrs_arg`, `crypto`, `custom`  
`crypto_limit`: cuántos tickers de la lista crypto usar (1–100, default 20)

## Sistema de scoring — Helper Prime (0-100)

Port directo desde Pine Script v6. Dos scores simétricos (long/short), cada uno hasta 100 pts:

| Componente | Pts | Criterio alcista |
|---|---|---|
| EMA 200 | 15 | `close > ema200` |
| Alineación EMA | 15 | `ema20 > ema55 > ema200` (+15), solo `ema20 > ema55` (+8) |
| ADX + DI | 15 | `adx > 20 and DI+ > DI-` (+15), solo `adx > 20` (+8) |
| Momentum RSI-50 | 15 | `mom > 0 and rising` (+15), solo `mom > 0` (+8) |
| MTF proxy | 15 | 4 señales diarias: `price > ema20/55/200, ema20 > ema55`. ≥3 ok (+15), ==2 (+8) |
| Volatilidad ATR | 10 | `atr > sma(atr,20) * 1.05` (+10) |
| Zona estructural | 15 | DISCOUNT (regresión lineal) o near support o POC volumen (+15) |

### Zonas estructurales

- **DISCOUNT**: `close <= lr_basis - lr_dev * 0.35` (regresión lineal 100 períodos, dev × 2)
- **FAIR**: zona media
- **PREMIUM**: `close >= lr_basis + lr_dev * 0.35`
- **POC**: Point of Control — precio con mayor volumen acumulado (70 velas, 15 buckets)

### Mapeo de señales

| Dirección | Score | Señal |
|---|---|---|
| LONG | ≥ 75 | `compra_fuerte` |
| LONG | ≥ 60 | `compra` |
| LONG / NEUTRAL | < 60 | `neutral` |
| SHORT | ≥ 60 | `venta` |
| SHORT | ≥ 75 | `venta_fuerte` |

## Helper Pulse — Divergencias RSI

Port de Helper Pulse. Oscilador: `ema(rsi(14) - 50, 3)`. Detecta sobre los últimos 2 pivots:

| Señal | Condición |
|---|---|
| GIRO UP | Precio lower low + momentum higher low (zona < -15) |
| SIGUE UP | Precio higher low + momentum lower low (mom < 0) |
| GIRO DN | Precio higher high + momentum lower high (zona > 15) |
| SIGUE DN | Precio lower high + momentum higher high (mom > 0) |
| AGOT. SUP | Pivot de momentum en zona alta (≥ 15) sin divergencia |
| AGOT. INF | Pivot de momentum en zona baja (≤ -15) sin divergencia |

Parámetros: `pivot_len=3`, `min_bars_between=5`, `min_osc_delta=3.0`, `turn_level=15`

## SL / TP

Calculados con ATR(14) × multiplicador desde el precio actual:
- **SL**: ATR × 1.5
- **TP1**: ATR × 1.5
- **TP2**: ATR × 3.0 (no mostrado en tabla, disponible en el resultado JSON)

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
| `crypto` | Top 100 criptos (sin stablecoins) | Hardcodeado, limitado por `crypto_limit` |
| `custom` | Libre | Input del usuario |

## Decisiones técnicas importantes

- **Descarga bulk**: `yf.download("AAPL MSFT ...", period="1y")` trae todos los tickers en un solo request HTTP (~15s para 503 tickers).
- **threading.Lock**: el callback `on_result` es llamado desde un thread de background mientras FastAPI sirve `_cache["data"]` desde otro thread. Sin lock se corrompe la lista durante `append` + `sort` simultáneos.
- **Multi-level columns**: cuando yfinance descarga un solo ticker, las columnas no son multi-nivel. El screener maneja ambos casos explícitamente.
- **Fuente de tickers S&P 500**: CSV público de GitHub. Wikipedia devuelve 403 con `pd.read_html`.
- **Polygon.io**: descartado — free tier limitado a 5 requests simultáneos. yfinance es suficiente.
- **yfinance**: requiere versión 1.3.0+. Versiones anteriores fallan con `JSONDecodeError`.
- **Estado `downloading`**: el backend emite dos estados — `downloading` (descarga bulk, sin progreso) y `loading` (cálculo indicador por indicador, con progreso).
- **MTF aproximado**: las 4 temporalidades reales (15m/1h/4h/1D) no están disponibles con datos diarios. Se aproximan con 4 señales de EMAs diarias: `price > ema20`, `price > ema55`, `price > ema200`, `ema20 > ema55`.
- **Helper Prime/Pulse originales**: los indicadores Pine Script están en `c:\Users\Compu\Documents\Dev\Finanzas\suite indicators\`. El port a Python está en `screener.py`.

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

### Deploy serverless (próximo)

Reemplazar la arquitectura actual (servidor persistente + cache en memoria) por:

1. **KV store** (Vercel KV o Cloudflare KV) para guardar resultados del screener
2. **Cron job** (1x día, o on-demand) que corre `run_screener` y escribe en KV
3. **API serverless** que solo lee del KV — respuesta instantánea, sin timeout
4. **Frontend** en Vercel Pages o Cloudflare Pages

Flujo nuevo:
```
Cron (diario) → run_screener() → guarda en KV
Usuario → "Analizar" → dispara job → polling → lee del KV
```

Cambios necesarios en el código:
- `_cache` dict → KV store
- `BackgroundTasks` de FastAPI → cron job de Vercel/Cloudflare
- `threading.Lock` → innecesario (KV es atómico)
- Agregar endpoint para triggerear el job manualmente

### Features pendientes

- [ ] Gráfico de precio al hacer click en un ticker
- [ ] Alertas por email o Telegram cuando cambia la señal
- [ ] Análisis con IA explicando la señal de cada activo
- [ ] MTF real con descarga intraday para 15m/1h/4h

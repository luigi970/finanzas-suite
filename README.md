# Stock Screener — maximos

> Analizá acciones, ETFs y criptomonedas con indicadores técnicos profesionales portados desde TradingView. Resultados pre-calculados diariamente, disponibles al instante.

![Frontend](https://img.shields.io/badge/Frontend-React%20%2B%20Tailwind-61DAFB?style=flat-square&logo=react)
![Worker](https://img.shields.io/badge/API-Cloudflare%20Workers-F38020?style=flat-square&logo=cloudflare)
![DB](https://img.shields.io/badge/DB-Cloudflare%20D1-F38020?style=flat-square&logo=cloudflare)
![CI](https://img.shields.io/badge/Screener-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions)

**Producción:** https://maximos.pages.dev

---

## ¿Qué hace?

Descarga datos de Yahoo Finance y aplica el sistema **Helper Prime + Helper Pulse** para asignar un **Score 0–100** a cada activo y clasificarlo en 5 señales de trading. Al abrir cualquier ticker muestra una **recomendación generada por IA**.

### Señales por score

| Score | Dirección | Señal |
|---|---|---|
| ≥ 75 | LONG | Compra Fuerte |
| 60–74 | LONG | Compra |
| — | — | Neutral |
| 60–74 | SHORT | Venta |
| ≥ 75 | SHORT | Venta Fuerte |

### Listas disponibles

| Lista | Activos |
|---|---|
| S&P 500 | 503 acciones |
| Nasdaq 100 | 100 empresas tech |
| ETFs | 49 ETFs (sectores, renta fija, commodities) |
| ADRs Argentina | GGAL, YPF, MELI, GLOB, VIST y más |
| Crypto | Top 10–100 por market cap (slider ajustable) |

---

## Arquitectura

```
GitHub Actions (cron diario + on-demand)
    └── screener.py — descarga yfinance + calcula indicadores
    └── run_job.py  — escribe resultados en Cloudflare D1

Cloudflare Worker (Python)
    └── Lee D1 y expone REST API
    └── /api/analyze — IA con CF Workers AI → Groq → Gemini

Cloudflare Pages (React + Vite)
    └── Consume la Worker API
    └── Deploy automático en cada push a main
```

El screener corre en **GitHub Actions** (tiene acceso a pandas, numpy, yfinance).
El Worker es solo lectura — respuesta instantánea sin cálculos.

---

## Fork & deploy propio

Para correr tu propia instancia:

1. **Crear los recursos en Cloudflare**
   ```bash
   # Crear base D1
   npx wrangler d1 create maximos-db
   # Aplicar schema
   npx wrangler d1 execute maximos-db --file=worker/migrations/0001_init.sql
   ```

2. **Configurar wrangler.toml**
   ```bash
   cp worker/wrangler.example.toml worker/wrangler.toml
   # Editar wrangler.toml con tu database_id
   ```

3. **Agregar secrets al Worker**
   ```bash
   npx wrangler secret put GH_PAT
   npx wrangler secret put GROQ_API_KEY
   npx wrangler secret put GOOGLE_API_KEY
   ```

4. **Agregar secrets a GitHub Actions** (Settings → Secrets → Actions):
   - `CF_API_TOKEN` — token de Cloudflare
   - `CF_ACCOUNT_ID` — tu account ID
   - `CF_D1_DB_ID` — el ID de la base creada en el paso 1
   - `VITE_API_URL` — URL de tu Worker tras el primer deploy

5. **Hacer push** — los workflows de GitHub Actions se encargan del resto.

---

## Desarrollo local

### Requisitos
- Python 3.12+
- Node.js 18+

### Setup

```powershell
# Backend (FastAPI local)
cd backend
pip install -r requirements.txt
# Crear backend/.env con:
# GROQ_API_KEY=...
# GOOGLE_API_KEY=...

# Frontend
cd ../frontend
npm install
```

### Levantar

```powershell
# Windows — script automático
.\start.ps1

# O manualmente en dos terminales
cd backend && uvicorn main:app --reload --port 8000
cd frontend && npm run dev
```

- Frontend: http://localhost:5173
- Backend:  http://localhost:8000

En local el botón "Analizar" corre el screener directamente en el backend (sin GitHub Actions). La IA usa Groq → Gemini como fallback (CF Workers AI no está disponible fuera del Worker).

---

## Deployment

El deploy es automático vía GitHub Actions al hacer push a `main`.

| Cambio | Workflow | Resultado |
|---|---|---|
| `worker/**` o `frontend/**` | `deploy.yml` | Redeploy del Worker y/o rebuild de Pages |
| Botón "Analizar" en la app | `screener.yml` | Corre el screener y escribe en D1 |
| Cron 2am UTC (lun–vie) | `screener.yml` | Actualiza automáticamente sp500/nasdaq100/etfs/adrs_arg |

### Secrets necesarios en GitHub

| Secret | Descripción |
|---|---|
| `CF_API_TOKEN` | Token de API de Cloudflare |
| `CF_ACCOUNT_ID` | ID de cuenta Cloudflare |
| `CF_D1_DB_ID` | ID de la base D1 |
| `VITE_API_URL` | URL del Worker (`https://maximos-worker.luchotour.workers.dev`) |

### Secrets en Cloudflare Worker

| Secret | Descripción |
|---|---|
| `GH_PAT` | GitHub Personal Access Token (para disparar workflows) |
| `GROQ_API_KEY` | API key de Groq (fallback IA) |
| `GOOGLE_API_KEY` | API key de Gemini (segundo fallback IA) |

---

## API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/status?list_id=sp500` | Estado y progreso del último análisis |
| `GET` | `/api/stocks?list_id=sp500&signal=all` | Resultados filtrados por señal |
| `GET` | `/api/lists` | Listas con conteo de activos |
| `POST` | `/api/refresh` | Dispara un nuevo análisis vía GitHub Actions |
| `POST` | `/api/analyze` | Recomendación IA para un ticker |

Body de `/api/refresh`:
```json
{ "list_id": "sp500", "crypto_limit": 20 }
```

---

## Sistema de indicadores

### Helper Prime — Score 0-100

| Componente | Pts | Criterio alcista |
|---|---|---|
| EMA 200 | 15 | `close > ema200` |
| Alineación EMA 20/55/200 | 15 | Estructura alcista completa |
| ADX + DI+/DI- | 15 | Tendencia activa con dirección |
| Momentum RSI-50 | 15 | Impulso positivo y creciendo |
| MTF proxy | 15 | Alineación en múltiples temporalidades |
| Volatilidad ATR | 10 | ATR por encima de su promedio |
| Zona estructural | 15 | DISCOUNT / soporte / POC de volumen |

### Helper Pulse — Divergencias RSI

| Señal | Descripción |
|---|---|
| GIRO UP | Divergencia alcista regular — posible reversión al alza |
| SIGUE UP | Divergencia alcista oculta — continuación alcista |
| GIRO DN | Divergencia bajista regular — posible reversión a la baja |
| SIGUE DN | Divergencia bajista oculta — continuación bajista |
| AGOT. SUP | Agotamiento en zona alta — precaución en longs |
| AGOT. INF | Agotamiento en zona baja — posible rebote |

### IA — Recomendación automática

Al abrir un ticker el modal llama a `/api/analyze`. La cadena de proveedores es:

1. **Cloudflare Workers AI** — `llama-3.3-70b-instruct-fp8-fast` (edge, sin costo adicional)
2. **Groq** — `llama-3.3-70b-versatile` (fallback)
3. **Gemini** — `gemini-2.0-flash-lite` (segundo fallback)

---

## Estructura del repositorio

```
maximos/
├── .github/workflows/
│   ├── deploy.yml       # CI/CD: Worker + Pages en cada push
│   └── screener.yml     # Screener: cron diario + on-demand
├── backend/
│   ├── main.py          # FastAPI local (desarrollo)
│   ├── screener.py      # Helper Prime + Pulse + descarga yfinance
│   ├── run_job.py       # Job para GitHub Actions → escribe en D1
│   └── requirements.txt
├── frontend/
│   └── src/App.jsx      # UI React + Tailwind
├── worker/
│   ├── wrangler.toml
│   └── src/
│       ├── entry.py     # Worker: routing + endpoints
│       ├── storage/db.py
│       └── providers/
│           ├── cf_ai.py
│           ├── groq.py
│           ├── gemini.py
│           └── prompt.py
└── start.ps1 / start.sh
```

---

<p align="center">Hecho con <a href="https://claude.ai">Claude</a></p>

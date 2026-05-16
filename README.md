# 📈 Stock Screener

> Analizá acciones, ETFs y criptomonedas en segundos con un sistema de indicadores técnicos profesionales portado desde TradingView.

![Stack](https://img.shields.io/badge/Frontend-React%20%2B%20Tailwind-61DAFB?style=flat-square&logo=react)
![Stack](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python-009688?style=flat-square&logo=fastapi)
![Data](https://img.shields.io/badge/Datos-Yahoo%20Finance-purple?style=flat-square)
![License](https://img.shields.io/badge/Licencia-MIT-green?style=flat-square)

---

## ¿Qué hace?

Descarga datos históricos de Yahoo Finance y aplica el sistema **Helper Prime + Helper Pulse** para asignar un **Score 0-100** a cada activo y clasificarlo en 5 señales de trading.

### Helper Prime — Score de estructura (0-100)

| Componente | Pts | Qué evalúa |
|---|---|---|
| EMA 200 | 15 | Precio sobre la tendencia principal |
| Alineación EMA 20/55/200 | 15 | Estructura alcista completa |
| ADX + DI+/DI- | 15 | Fuerza y dirección de la tendencia |
| Momentum RSI-50 | 15 | Impulso alcista o bajista |
| MTF proxy | 15 | Alineación en múltiples temporalidades (aproximado) |
| Volatilidad ATR | 10 | ATR activo por encima de su promedio |
| Zona estructural | 15 | DISCOUNT / soporte / POC de volumen |

### Helper Pulse — Señales de divergencia

| Señal | Tipo | Descripción |
|---|---|---|
| GIRO UP | Alcista | Divergencia regular: precio baja, momentum sube |
| SIGUE UP | Alcista | Divergencia oculta: continuación alcista |
| GIRO DN | Bajista | Divergencia regular: precio sube, momentum baja |
| SIGUE DN | Bajista | Divergencia oculta: continuación bajista |
| AGOT. SUP | Precaución | Agotamiento en zona alta |
| AGOT. INF | Oportunidad | Agotamiento en zona baja |

### Señales por score

| Score | Dirección | Señal |
|---|---|---|
| ≥ 75 | LONG | 🟢 **Compra Fuerte** |
| 60–74 | LONG | 🟩 **Compra** |
| 40–59 | — | ⬜ **Neutral** |
| 60–74 | SHORT | 🟧 **Venta** |
| ≥ 75 | SHORT | 🔴 **Venta Fuerte** |

---

## Listas disponibles

| Lista | Activos |
|---|---|
| 🇺🇸 **S&P 500** | 503 acciones |
| 💻 **Nasdaq 100** | 100 empresas tech |
| 📦 **ETFs** | 49 ETFs (sectores, renta fija, commodities) |
| 🇦🇷 **ADRs Argentina** | GGAL, YPF, MELI, GLOB, VIST y más |
| 🪙 **Crypto** | Top 10–100 por market cap (slider ajustable) |
| ✏️ **Personalizada** | Los tickers que vos elijas |

---

## Stack técnico

```
maximos/
├── backend/
│   ├── main.py          # API REST con FastAPI
│   ├── screener.py      # Helper Prime + Pulse portados a Python
│   └── requirements.txt
├── frontend/
│   └── src/
│       └── App.jsx      # UI completa en React + Tailwind
├── start.ps1            # Script para levantar todo (Windows)
└── start.sh             # Script para levantar todo (Linux/macOS)
```

---

## Instalación y uso

### Requisitos
- Python 3.12+
- Node.js 18+

### 1. Clonar el repo

```bash
git clone https://github.com/luigi970/maximos.git
cd maximos
```

### 2. Instalar dependencias

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 3. Levantar la app

**Windows**
```powershell
.\start.ps1
```

**Linux / macOS**
```bash
chmod +x start.sh
./start.sh
```

O manualmente en dos terminales:

```bash
# Terminal 1 — Backend
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
```

### 4. Abrir en el browser

```
http://localhost:5173
```

---

## Cómo usar

1. **Elegí una lista** — S&P 500, Nasdaq, Crypto (ajustá el slider), etc.
2. **Presioná Analizar** — descarga y procesa los datos (~15s para el S&P 500)
3. **Filtrá por Compra Fuerte** y revisá que Dir sea LONG
4. **Chequeá la Zona** — DISCOUNT o FAIR son las mejores entradas
5. **Confirmá ADX > 25** y vs MA200 positivo
6. **Si el Pulse muestra GIRO UP o SIGUE UP** → mayor confluencia
7. **Usá SL/TP1** para dimensionar el riesgo antes de entrar

> Presioná **? Cómo usar** dentro de la app para la guía completa.

---

## API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/status` | Estado del análisis y progreso |
| `GET` | `/api/stocks?signal=compra_fuerte` | Lista filtrada por señal |
| `GET` | `/api/lists` | Listas disponibles |
| `POST` | `/api/refresh` | Lanza un nuevo análisis |

Body de `/api/refresh`:
```json
{ "list_id": "sp500", "custom": [], "crypto_limit": 20 }
```

`list_id`: `sp500` · `nasdaq100` · `etfs` · `adrs_arg` · `crypto` · `custom`

---

## Decisiones técnicas

- **Descarga bulk**: `yf.download()` trae todos los tickers en un solo request HTTP (~15s para 503 tickers)
- **Threading lock**: protege el cache compartido durante escrituras concurrentes
- **Helper Prime portado**: sistema de scoring propio originalmente desarrollado en Pine Script v6 para TradingView
- **MTF aproximado**: las 4 temporalidades (15m/1h/4h/1D) se aproximan con señales de EMAs diarias
- **Sin base de datos**: cache en memoria, simple y sin dependencias externas

---

## Roadmap

### 🚀 Deploy (próximo)

Arquitectura serverless en Vercel o Cloudflare:

```
Cron job (1x día)
    └── corre el screener en background
    └── guarda resultados en KV / DB

API (serverless, respuesta instantánea)
    └── lee del KV — no hace cálculos
    └── el frontend no espera nada

Frontend (Vercel / Cloudflare Pages)
    └── "Analizar" dispara el job y hace polling
    └── los resultados ya están pre-calculados
```

- [ ] Migrar cache en memoria → Vercel KV o Cloudflare KV
- [ ] Convertir `run_screener` en un job asincrónico (cron diario)
- [ ] Deploy frontend en Vercel / Cloudflare Pages
- [ ] Deploy backend como funciones serverless Python

### 🔮 Features

- [ ] Gráfico de precio al hacer click en un ticker
- [ ] Alertas por email o Telegram cuando cambia la señal
- [ ] Análisis con IA explicando la señal de cada activo
- [ ] MTF real con descarga intraday para 15m/1h/4h

---

<p align="center">
  Hecho con 🧠 y <a href="https://claude.ai">Claude</a>
</p>

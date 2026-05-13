# 📈 Stock Screener

> Analizá cientos de acciones en segundos y encontrá las mejores oportunidades de compra y venta con indicadores técnicos profesionales.

![Stack](https://img.shields.io/badge/Frontend-React%20%2B%20Tailwind-61DAFB?style=flat-square&logo=react)
![Stack](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python-009688?style=flat-square&logo=fastapi)
![Data](https://img.shields.io/badge/Datos-Yahoo%20Finance-purple?style=flat-square)
![License](https://img.shields.io/badge/Licencia-MIT-green?style=flat-square)

---

## ¿Qué hace?

Descarga datos históricos de Yahoo Finance, calcula indicadores técnicos y asigna un **Score 0-100** a cada acción combinando:

| Indicador | Peso | Qué mide |
|-----------|------|----------|
| Tendencia (MA50 / MA200) | 30 pts | Si la acción está en uptrend o downtrend |
| RSI | 20 pts | Sobreventa / sobrecompra |
| MACD | 20 pts | Momentum y dirección del movimiento |
| Volumen relativo | 15 pts | Si el movimiento está confirmado |
| Bollinger Bands | 15 pts | Posición dentro del rango de volatilidad |

---

## Señales

| Score | Señal | Descripción |
|-------|-------|-------------|
| 75–100 | 🟢 **Compra Fuerte** | Confluencia alcista en todos los indicadores |
| 60–74 | 🟩 **Compra** | Señales positivas, buen momento de entrada |
| 40–59 | ⬜ **Neutral** | Sin dirección clara, mejor esperar |
| 20–39 | 🟧 **Venta** | Presión bajista, evitar comprar |
| 0–19 | 🔴 **Venta Fuerte** | Señales bajistas alineadas |

---

## Listas disponibles

- 🇺🇸 **S&P 500** — 503 acciones
- 💻 **Nasdaq 100** — Las 100 empresas tech más grandes
- 📦 **ETFs** — Mercado amplio, sectores, renta fija, commodities
- 🇦🇷 **ADRs Argentina** — GGAL, YPF, MELI, GLOB, VIST y más
- ✏️ **Lista personalizada** — Escribís los tickers que querés

---

## Stack técnico

```
maximos/
├── backend/
│   ├── main.py          # API REST con FastAPI
│   ├── screener.py      # Descarga bulk + cálculo de indicadores
│   └── requirements.txt
├── frontend/
│   └── src/
│       └── App.jsx      # UI completa en React + Tailwind
└── start.ps1            # Script para levantar todo
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
pip install -r requirements.txt   # Linux/Mac: pip3 install -r requirements.txt

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

**Cualquier sistema con PowerShell instalado (pwsh)**
```powershell
pwsh start.ps1
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

1. **Elegí una lista** (S&P 500, Nasdaq, ETFs, etc.)
2. **Presioná Analizar** — descarga y procesa los datos (~15s para el S&P 500)
3. **Filtrá por señal** — enfocate en Compra Fuerte o Compra
4. **Ordená por Score** de mayor a menor
5. **Verificá** que `vs MA200` sea positivo y `Vol ×` mayor a 1.2x
6. Las que pasen estos filtros son las candidatas más sólidas

> Presioná **? Cómo usar** dentro de la app para ver la guía completa.

---

## API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/status` | Estado del análisis y progreso |
| `GET` | `/api/stocks?signal=compra_fuerte` | Lista filtrada por señal |
| `GET` | `/api/lists` | Listas disponibles |
| `POST` | `/api/refresh` | Lanza un nuevo análisis |

---

## Decisiones técnicas

- **Descarga bulk**: `yf.download()` trae los 503 tickers en un solo request HTTP (~15s vs ~3min individual)
- **Threading lock**: protege el cache compartido entre los workers y el servidor FastAPI
- **Scoring compuesto**: 5 indicadores ponderados evitan señales falsas de un solo indicador
- **Sin base de datos**: cache en memoria, simple y sin dependencias externas

---

## Roadmap

- [ ] Deploy en Render (backend) + Vercel (frontend)
- [ ] Cache persistente con PostgreSQL
- [ ] Actualización automática diaria (cron job)
- [ ] Gráfico de precio al hacer click en un ticker
- [ ] Alertas por email o Telegram
- [ ] Análisis con IA explicando la señal

---

<p align="center">
  Hecho con 🧠 y <a href="https://claude.ai">Claude</a>
</p>

# Finanzas Personales

App web local para seguimiento de patrimonio personal. Corre en tu máquina, los datos se guardan en un SQLite local.

## Qué hace

- **Patrimonio**: ve el total de tus activos en USD y ARS (dólar blue), agrupados por tipo. Incluye P&L no realizado, P&L realizado e interés devengado de plazos fijos y staking.
- **Portfolio**: manejá tus posiciones por cuenta — cripto, acciones, plazos fijos, fiat. Los plazos fijos calculan el interés automáticamente.
- **Movimientos**: importá transacciones desde PDF, imagen, CSV o texto pegado. La IA las extrae y te muestra una preview editable antes de guardar. También podés filtrar, buscar y exportar a CSV.
- **Agente**: hacé preguntas sobre tus finanzas en lenguaje natural. Tiene acceso a todas tus cuentas y movimientos.

## Requisitos

- Python 3.10+
- Node.js 18+
- Claves de API: `GROQ_API_KEY` (requerida) y `GOOGLE_API_KEY` (fallback)

## Instalación

```powershell
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # completar con las API keys

# Frontend
cd frontend
npm install
```

## Arrancar

```powershell
.\start.ps1
```

Abre `http://localhost:5174` en el navegador.

## Variables de entorno (`backend/.env`)

```
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...
```

## Estructura

```
finanzas/
├── backend/
│   ├── main.py          # FastAPI (puerto 8001)
│   ├── database.py      # SQLite + migraciones automáticas
│   ├── finanzas.db      # Base de datos local (no commitear)
│   └── routers/
│       ├── accounts.py
│       ├── positions.py
│       ├── transactions.py
│       ├── ingest.py    # Extracción IA
│       └── agent.py     # Chat IA
└── frontend/
    └── src/App.jsx      # UI completa
```

## Notas

- Los datos son completamente locales. Nada sale a internet salvo las llamadas a las APIs de IA para extraer transacciones o responder preguntas.
- Los precios de activos se obtienen desde [maximos](../README.md) corriendo en `localhost:8000`.
- Ver [CLAUDE.md](CLAUDE.md) para documentación técnica de desarrollo.

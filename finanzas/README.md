# Finanzas Personales

App web local para seguimiento de patrimonio personal. Corre en tu máquina, los datos se guardan en un SQLite local.

## Qué hace

- **Patrimonio**: ve el total de tus activos en USD y ARS (dólar blue), agrupados por tipo. Incluye P&L no realizado, P&L realizado e interés devengado de plazos fijos y staking.
- **Portfolio**: manejá tus posiciones por cuenta — cripto, acciones, plazos fijos, fiat. Los plazos fijos calculan el interés automáticamente.
- **Movimientos**: importá transacciones desde PDF, imagen, CSV o texto pegado. La IA las extrae y te muestra una preview editable antes de guardar. Al guardar, se crea automáticamente la posición en el portfolio si no existe.
- **Agente**: hacé preguntas sobre tus finanzas en lenguaje natural. Tiene acceso a todas tus cuentas, posiciones con precios reales de mercado, P&L, transacciones y resumen mensual.

## Requisitos

- Python 3.10+
- Node.js 18+
- Claves de API: `GROQ_API_KEY` (requerida) y `GOOGLE_API_KEY` (fallback)

## Instalación

```powershell
# Backend
cd finanzas/backend
pip install -r requirements.txt
cp .env.example .env   # completar con las API keys

# Frontend
cd finanzas/frontend
npm install
```

## Arrancar

### Opción 1 — Todo junto (recomendado)

Desde la raíz del repositorio:

```powershell
.\start-all.ps1
```

Arranca los 4 procesos (backend + frontend de maximos y finanzas) sin abrir ventanas de terminal.
Los logs quedan en `logs/`. Para detener todo:

```powershell
.\stop-all.ps1
```

### Opción 2 — Solo finanzas

```powershell
.\finanzas\start.ps1
```

Abre `http://localhost:5174` en el navegador.

## Variables de entorno (`finanzas/backend/.env`)

```
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...
# Opcional: override de la URL de maximos (por defecto usa Cloudflare Worker)
# MAXIMOS_URL=http://localhost:8000
```

## Precios de mercado

Los precios de activos se obtienen desde **Cloudflare Worker de maximos** por defecto (no requiere correr maximos local). Esto incluye dólar blue, cotizaciones de acciones/CEDEARs y criptos.

Desde la configuración (⚙️ en el header) podés cambiar entre:
- **Online** (por defecto): usa `https://maximos-worker.luchotour.workers.dev`
- **Local**: usa `http://localhost:8000` — requiere tener maximos corriendo. La app puede arrancarlo automáticamente si está instalado.

## Estructura

```
finanzas/
├── backend/
│   ├── main.py          # FastAPI (puerto 8001) + endpoints /api/maximos/status y /start
│   ├── database.py      # SQLite + migraciones automáticas
│   ├── finanzas.db      # Base de datos local (no commitear)
│   └── routers/
│       ├── accounts.py
│       ├── positions.py
│       ├── transactions.py  # Auto-crea posición al guardar transacción
│       ├── ingest.py        # Extracción IA desde PDF/imagen/CSV/texto
│       └── agent.py         # Chat IA con precios reales y cartera completa
└── frontend/
    └── src/App.jsx      # UI completa
```

## Notas

- Los datos de cartera son completamente locales (SQLite). Nada sale a internet salvo las llamadas a las APIs de IA y a Cloudflare Worker para precios.
- Ver [CLAUDE.md](CLAUDE.md) para documentación técnica de desarrollo.

# Asistente Fiscal Inteligente — CLAUDE.md

App local para análisis y gestión fiscal personal en Argentina. Combina datos de ARCA (via AFIP SDK automations), datos patrimoniales de `finanzas/` y una IA especializada en fiscalidad argentina para responder preguntas concretas sobre la situación del usuario.

## Arquitectura

```
fiscal/
├── backend/
│   ├── main.py              # FastAPI, puerto 8002
│   ├── database.py          # SQLite (fiscal.db) + migrations
│   ├── routers/
│   │   ├── profile.py       # CRUD perfil fiscal del usuario
│   │   ├── arca.py          # AFIP SDK: sync de automatizaciones
│   │   ├── agent.py         # Chat IA con contexto fiscal completo
│   │   └── documents.py     # Upload + extracción de PDFs/imágenes
│   └── requirements.txt
├── frontend/
│   └── src/App.jsx          # UI completa en un solo archivo
├── CLAUDE.md
├── README.md
└── start.ps1
```

## Puertos

- Backend: `8002`
- Frontend: `5175`

## Variables de entorno (`fiscal/backend/.env`)

```
GROQ_API_KEY=...              # primario para agente e ingest
GOOGLE_API_KEY=...            # fallback
AFIPSDK_ACCESS_TOKEN=...      # token del proyecto en afipsdk.com
FINANZAS_URL=http://localhost:8001  # para obtener datos patrimoniales
```

Las keys se configuran desde ⚙️ en la UI. La Clave Fiscal del usuario NUNCA se persiste — se pide en cada sincronización y se usa solo en memoria.

## Cómo arrancar

```powershell
cd fiscal/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8002

cd fiscal/frontend
npm install
npm run dev  # puerto 5175
```

## AFIP SDK — Integración

Documentación: https://afipsdk.com/docs/automations/introduction/

### Automatizaciones disponibles (16 total, las relevantes para el asistente):

| Automation | Datos que devuelve | Frecuencia sugerida |
|---|---|---|
| `nuestra-parte` | Condición fiscal, patrimonio, inversiones, quebrantos, facturación, mensajes de cumplimiento | Semanal |
| `monotributo-info` | Categoría actual, monto facturado, próximo vencimiento, límite | Semanal |
| `mis-retenciones` | Retenciones y percepciones de Ganancias, Bienes Personales, IVA | Mensual |
| `domicilio-fiscal-electronico` | Notificaciones e intimaciones de ARCA | Semanal |
| `ccma` | Cuenta corriente, deuda, movimientos por período | Mensual |
| `mis-comprobantes` | Comprobantes emitidos y recibidos | Mensual |
| `mis-facilidades` | Planes de pago activos | Mensual |

### Patrón de llamada (Python via httpx):

```python
async def run_automation(automation: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.afipsdk.com/v1/automations",
            headers={"Authorization": f"Bearer {AFIPSDK_ACCESS_TOKEN}"},
            json={"automation": automation, "data": data, "wait": True}
        )
        r.raise_for_status()
        return r.json()["data"]
```

### Credenciales requeridas para automatizaciones:
- `cuit`: CUIT del contribuyente (string, sin guiones)
- `username`: CUIT de login (usualmente el mismo)
- `password`: Clave Fiscal nivel 2 o 3

La Clave Fiscal se pide en el frontend al momento de sincronizar, se envía al backend solo para la duración de la request, y NUNCA se guarda en DB ni en `.env`.

## Base de datos (SQLite — `fiscal.db`)

### Tablas

**fiscal_profile** — un solo registro por usuario
```sql
id, cuit, razon_social, condicion (monotributo|responsable_inscripto|relacion_dependencia|otro),
categoria_monotributo (A-K), tiene_inmuebles, tiene_vehiculos, tiene_inversiones,
opera_cripto, opera_cedears, usa_broker, tiene_caja_ahorro_usd,
periodo_fiscal (año), notas, updated_at
```

**arca_cache** — resultados de automatizaciones
```sql
id, automation, periodo, data (JSON), fetched_at, expires_at
```
TTL sugerido: 7 días para `nuestra-parte`, 30 días para `mis-retenciones`.

**documents** — documentos subidos por el usuario
```sql
id, name, type (ddjj|recibo|constancia|otro), period, content (texto extraído), file_path, created_at
```

**chat_messages** — historial del agente
```sql
id, role (user|assistant), content, created_at
```

**obligations** — vencimientos fiscales calculados
```sql
id, name, type (presentacion|pago), due_date, status (pending|completed|overdue),
applies_to (condicion que aplica), notes
```

## API Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/profile` | Perfil fiscal del usuario |
| POST | `/api/profile` | Crear/actualizar perfil |
| POST | `/api/arca/sync` | Ejecutar automatizaciones con ARCA. Body: `{automation, cuit, password, periodo?}` |
| GET | `/api/arca/cache` | Datos cacheados por automatización |
| GET | `/api/arca/cache/{automation}` | Datos de una automatización específica |
| DELETE | `/api/arca/cache/{automation}` | Invalidar cache |
| POST | `/api/documents/upload` | Subir PDF/imagen, extraer texto con IA |
| GET | `/api/documents` | Listar documentos |
| DELETE | `/api/documents/{id}` | Eliminar documento |
| POST | `/api/agent/chat` | Chat con el agente IA fiscal |
| DELETE | `/api/agent/chat` | Limpiar historial |
| GET | `/api/obligations` | Vencimientos del usuario |
| POST | `/api/obligations/recalculate` | Recalcular vencimientos según perfil |
| GET | `/api/config` | API keys configuradas |
| POST | `/api/config` | Guardar API keys |
| GET | `/api/health` | Status del backend |

## Agente IA (`routers/agent.py`)

### Cadena de proveedores
Groq (`llama-3.3-70b-versatile`) → Gemini (`gemini-2.0-flash-lite`)

### Contexto que recibe el agente

1. **Perfil fiscal** — condición, categoría, bienes declarables
2. **Datos ARCA** (`nuestra-parte`, `monotributo-info`, `mis-retenciones`, `ccma`) — lo que ARCA sabe del usuario
3. **Datos patrimoniales** — desde `finanzas/` vía HTTP (patrimonio real, crypto, CEDEARs, dólares)
4. **Documentos** — texto extraído de DDJJs y constancias subidas
5. **Vencimientos** — obligaciones pendientes y próximas
6. **Base de conocimiento fiscal** — embebida en el system prompt (ver abajo)

### Sistema de conocimiento fiscal embebido

El SYSTEM_PROMPT incluye:
- Monotributo: categorías A-K con límites vigentes, fechas de recategorización (Enero y Julio), qué incluye cada categoría
- Bienes Personales: quién debe presentar, umbrales de mínimo no imponible, alícuotas, fecha de vencimiento (Junio, escalonado por CUIT)
- Ganancias 4ta categoría: deducciones admitidas, escala de alícuotas, deducciones especiales para empleados en relación de dependencia
- Crypto: tratamiento en Bienes Personales (bien del exterior si en exchange extranjero, bien en país si en exchange local), costo computable
- CEDEARs: bien en el país, valuación al último precio de mercado
- Dólares: billetes vs cuentas bancarias, diferencia entre bien en país y exterior
- Calendario fiscal 2026: todos los vencimientos relevantes
- Criterio: el agente NO da asesoramiento legal definitivo pero sí orientación concreta basada en la situación real del usuario

### Formato de respuesta del agente
- Español rioplatense, tono de contador de confianza
- Respuestas directas, sin rodeos
- Cita normativa cuando es relevante (RG AFIP XXXX)
- Distingue entre "esto es claro" vs "esto requiere un profesional"
- Cuando detecta inconsistencias entre datos ARCA y datos reales → alerta explícita

## UI — Tabs

| Tab | Descripción |
|---|---|
| **Dashboard** | Resumen de situación fiscal: alertas activas, próximos vencimientos, último sync ARCA |
| **Perfil** | CUIT, condición, bienes registrables, datos del contribuyente |
| **ARCA** | Panel de sincronización: botón sync con Clave Fiscal, estado de cada automatización, datos cacheados |
| **Documentos** | Upload de DDJJs, constancias, recibos. Extracción de texto con IA |
| **Agente** | Chat con el asesor fiscal IA |
| **Vencimientos** | Calendario de obligaciones fiscales personalizadas según perfil |

## UI — Diseño

- Stack: React + Vite + Tailwind CSS
- Acento: teal/verde (`teal-500`, `#14b8a6`) — diferencia visual de maximos (amber) y finanzas (amber)
- Header: `bg-slate-900` con borde top `3px solid #14b8a6`, "fiscal" en blanco
- Fondo: `bg-gray-50`

## Seguridad — Clave Fiscal

La Clave Fiscal es la credencial más sensible del sistema. Reglas:
- **NUNCA** se guarda en DB, `.env`, localStorage ni ningún storage persistente
- Se recibe en el frontend, se envía al backend vía HTTPS (local → localhost), se usa para llamar a AFIP SDK y se descarta
- El backend no la loguea
- En el panel de sync, se pide con un campo `type="password"` que se limpia al cerrar el modal

## Roadmap

### MVP (v0.1)
- [ ] Perfil fiscal básico (CUIT, condición)
- [ ] Sync con ARCA: `nuestra-parte` + `monotributo-info`
- [ ] Agente IA con contexto de perfil + datos ARCA + patrimonio de finanzas
- [ ] Dashboard con alertas básicas y próximo vencimiento

### v0.2
- [ ] `mis-retenciones` + `ccma` + `domicilio-fiscal-electronico`
- [ ] Upload de documentos (DDJJs anteriores)
- [ ] Calendario de vencimientos personalizado
- [ ] Detección de inconsistencias ARCA vs realidad

### v0.3
- [ ] Generación de borradores de DDJJ (pre-completado)
- [ ] Simulaciones "qué pasa si..." (optimización fiscal)
- [ ] `mis-facilidades` + `mis-comprobantes`

## Proyecto relacionado — Finanzas Personales

`fiscal/` consume datos patrimoniales de `finanzas/` vía HTTP:
- `GET /api/positions` — posiciones actuales (crypto, CEDEARs, stocks, plazos fijos)
- `GET /api/accounts` — cuentas y saldos
- Precio dólar blue vía maximos Worker

## Gotchas

- AFIP SDK timeout: las automatizaciones pueden tardar 30-120 segundos (browser automation). Usar `timeout=120` en httpx y feedback visual en frontend.
- AFIP SDK rate: plan Free = 10 automatizaciones/mes. Cachear siempre, nunca repetir si el cache es válido.
- `nuestra-parte` requiere el año como `periodo` (ej: `"2025"`).
- `mis-retenciones` tiene paginación — iterar hasta cubrir el período deseado.
- Clave Fiscal nivel 2 mínimo para la mayoría de las automatizaciones.
- `ccma` solo aplica a monotributistas y autónomos, no a relación de dependencia.

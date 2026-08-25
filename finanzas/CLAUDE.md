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
│   │   ├── transactions.py  # CRUD + batch import + CSV export + P&L + auto-crea posición
│   │   ├── ingest.py        # Extracción IA desde PDF/imagen/CSV/texto
│   │   └── agent.py         # Chat IA con precios de mercado reales y cartera completa
│   └── requirements.txt
├── frontend/
│   └── src/App.jsx          # UI completa en un solo archivo (React + Vite)
└── start.ps1                # Arranca backend (8001) y frontend (5174)
```

## Cómo arrancar

### Todo junto (maximos + finanzas)
```powershell
# Desde la raíz del repo
.\start-all.ps1   # arranca los 4 procesos sin ventanas
.\stop-all.ps1    # detiene todo
# También hay accesos directos en el escritorio: "Iniciar Finanzas" y "Detener Finanzas"
```

### Solo finanzas
```powershell
.\finanzas\start.ps1
# Backend:  http://localhost:8001
# Frontend: http://localhost:5174
```

O manualmente:
```powershell
cd finanzas/backend
python -m uvicorn main:app --reload --port 8001

cd finanzas/frontend
npm run dev  # corre en puerto 5174
```

## Variables de entorno (`finanzas/backend/.env`)

```
GROQ_API_KEY=...          # primario para ingest (texto) y agente
GOOGLE_API_KEY=...        # fallback para ingest (visión) y agente
MAXIMOS_URL=...           # opcional; por defecto usa el Cloudflare Worker de maximos
COINGECKO_API_KEY=...     # demo key gratuita — sentimiento crypto en el agente
```

Las keys también se pueden configurar desde la UI: ⚙️ → sección "API Keys". Se guardan automáticamente en `finanzas/backend/.env` y `backend/.env` (maximos) en simultáneo. `GET /api/config` lee directamente del archivo `.env` (no de `os.environ`) para reflejar siempre el estado real del disco.

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
| POST | `/api/positions/sync/{account_id}` | Recalcular cantidades desde transacciones (descuenta fixed_term/fund) |
| POST | `/api/positions/create-missing` | Crear posiciones faltantes desde historial de transacciones |
| GET | `/api/transactions` | Listar (limit=500 por defecto) |
| POST | `/api/transactions` | Crear una transacción (auto-crea posición si no existe) |
| PATCH | `/api/transactions/{id}` | Editar transacción (recalcula P&L) |
| DELETE | `/api/transactions/{id}` | Eliminar |
| POST | `/api/transactions/batch` | Importar lote — también auto-crea posiciones faltantes |
| GET | `/api/transactions/export` | Descarga CSV |
| GET | `/api/transactions/summary` | Resumen por mes/categoría/P&L |
| POST | `/api/ingest/text` | Extraer transacciones desde texto |
| POST | `/api/ingest/file` | Extraer desde PDF/imagen/CSV |
| POST | `/api/agent/chat` | Chat IA con contexto financiero completo |
| POST | `/api/agent/weekly-report` | Genera el análisis semanal de cartera on-demand y lo guarda en historial |
| GET | `/api/agent/weekly-report` | Lista el historial de análisis semanales guardados |
| DELETE | `/api/agent/weekly-report/{id}` | Elimina un análisis del historial |
| GET | `/api/agent/profile` | Devuelve el perfil de inversión guardado (texto libre) |
| POST | `/api/agent/profile` | Guarda/actualiza el perfil de inversión — se le da prioridad sobre conclusiones técnicas genéricas en chat y en el reporte semanal |
| GET | `/api/config` | Devuelve GROQ, GOOGLE y COINGECKO keys (lee del .env directo) |
| POST | `/api/config` | Escribe keys en .env de finanzas y maximos |
| GET | `/api/maximos/status` | Chequea si maximos local (puerto 8000) está corriendo |
| POST | `/api/maximos/start` | Arranca maximos local (uvicorn en puerto 8000) |

## Base de datos (SQLite)

`database.py` crea las tablas si no existen y corre migrations via `ALTER TABLE ADD COLUMN` en try/except.

### Tablas principales

**accounts**: `id, name, type (bank|exchange|wallet_crypto|wallet|broker|cash|other), color, active`

**positions**: `id, account_id, asset, asset_type (fiat|crypto|stablecoin|stock|cedear|cedear_usd|fixed_term|fund|flexible), quantity, avg_price, start_date, end_date, rate, auto_renew, notes`

**transactions**: `id, account_id, date, description, amount, currency, type (income|buy|expense|sell|transfer), category, source (manual|swap|transfer|opening_balance|avg_price_anchor), unit_price, realized_pnl, fee, fee_currency`

**weekly_reports**: `id, created_at, content` — historial de análisis semanales generados on-demand

**app_settings**: `key, value` — clave-valor genérico; hoy solo se usa para `investment_profile` (perfil de inversión en texto libre)

## Lógica clave

### P&L realizado
- **expense con unit_price**: `realized_pnl = (unit_price - avg_price) × amount` usando el avg_price actual de la posición
- Busca posición con `end_date IS NULL OR end_date = ''` (posiciones activas)
- Solo aplica a activos no fiat (`FIAT_CURRENCIES = {ARS, USD, EUR, BRL, UYU}`)
- **Gotcha real (corregido 2026-08-17)**: `update_transaction` (PATCH) nunca recalculaba ni limpiaba `realized_pnl` al editar una transacción — si una venta (`expense`, con `realized_pnl` calculado) se editaba a compra (`income`, ej. corrigiendo un error de carga durante una reconciliación histórica), el `realized_pnl` viejo quedaba pegado en una transacción que ya no es una venta. Encontrado en producción: 2 transacciones de compra de BTC con `realized_pnl` de -USD 8.18 y -USD 25.51, inflando el "P&L realizado" reportado por el agente en -USD 33.69 (mostraba -169.18 en vez de -135.49) durante toda la sesión. Fix: el PATCH ahora, cuando se toca `type`/`unit_price`/`amount`/`currency`, recalcula `realized_pnl` con `_calc_realized_pnl` si el tipo resultante es `expense`/`sell`, o lo limpia a `NULL` si no — nunca en ediciones que no tocan esos campos (no se debe recalcular con el avg_price de HOY un P&L histórico ya fijado en el momento de la venta).

### `_sync_position` (transactions.py)
Recalcula `quantity` y `avg_price` de la posición desde todos los movimientos. Reglas:
- **Quantity**: suma ingresos - egresos de todas las transacciones del activo en la cuenta, **menos** lo que ya está en posiciones `fixed_term`/`fund` activas (con `end_date` futura). Esto evita que el flexible duplique lo que está en plazo fijo.
- **avg_price**: se recalcula (media ponderada) usando **solo** las transacciones de ingreso que tienen `unit_price > 0`. Las transferencias (sin `unit_price`) se ignoran — no bloquean el cálculo ni distorsionan el promedio. Si no hay ninguna compra con precio, se preserva el `avg_price` existente (puede ser manual).
- Se llama automáticamente después de crear, editar o eliminar una transacción.
- El botón 🔄 por cuenta en Portfolio también lo dispara vía `POST /api/positions/sync/{account_id}`.

### Portfolio manda — `_update_opening_balance` (positions.py, decisión de diseño 2026-08-25)
El usuario no carga cada movimiento (gastos chicos, compras sin cargar, correcciones contra el saldo real de la wallet/banco) — corrige directo en Portfolio (✏️ o el formulario de posición). Esa corrección tiene que ser la que manda, sobrevivir a que se carguen más movimientos después, y los movimientos nuevos se suman/restan **a partir de ahí**, nunca recalculando todo desde cero ignorando la corrección.

- **Cómo se ancla la cantidad**: al crear o editar una posición (`POST`/`PATCH /api/positions/{id}`), si se toca `quantity`, se crea/ajusta una transacción sintética `source='opening_balance'` que tapa exactamente la diferencia entre lo que las transacciones reales explican y lo que el usuario puso. Funciona en las **dos direcciones**: `type='income'` si los movimientos reales explican MENOS que el target (hay que sumar — depositó algo sin cargarlo), `type='expense'` si explican MÁS (hay que restar — gastó algo sin cargarlo). **Gotcha real (corregido 2026-08-25)**: originalmente solo existía la dirección "sumar" — la dirección "restar" (la más común, típicamente gastos del día a día) no anclaba nada, dejando la posición a un movimiento nuevo de distancia de saltar a un valor viejo y equivocado. Se encontraron 4 posiciones reales en ese estado (BBVA ARS a 3 millones de pesos de diferencia) — auditar periódicamente con el script de comparación (ver abajo).
- **Cómo se ancla el precio promedio**: si además se pasa `avg_price` en el PATCH/POST, se reparte el costo que falta entre las filas "rellenables" — la fila `opening_balance` de arriba (si quedó con cantidad > 0) y cualquier compra real sin precio cargado (`unit_price IS NULL`, nunca una transferencia). Esas filas quedan marcadas `source='avg_price_anchor'`, así una segunda edición del promedio puede volver a rellenarlas (si no, el segundo ajuste no encuentra nada que tocar y no se guarda). **Límite de diseño, a propósito**: si la posición ya está 100% explicada por compras reales con precio genuino (nada que rellenar), el `avg_price` NO se ancla — anclarlo ahí exigiría reescribir el precio de una transacción real, falsificando el historial. En ese caso, la corrección correcta es editar la transacción puntual que está mal, no forzarlo desde Portfolio.
- **Auditoría rápida** (correr cuando se sospeche una posición desincronizada): comparar `positions.quantity` contra `SUM(CASE WHEN type IN ('income','buy') THEN amount ELSE -amount END)` de sus transacciones — si difieren, la posición NO está anclada y un movimiento nuevo la va a pisar. Se usó para encontrar y arreglar 4 posiciones reales el 2026-08-25.
- Al crear una posición nueva vía swap/transferencia/`create-missing`, si el activo tenía transacciones VIEJAS sin posición asociada (huérfanas), `create-missing` las suma TODAS de una — pueden aparecer sorpresas (caso real: un año de compras/ventas de ETH en Binance de 2025 que nunca tuvieron posición, reactivadas de golpe al registrar una transferencia en 2026-08-25).

### Swaps (frontend, `saveTransaction` en App.jsx)
Un swap se carga como UNA transacción en el formulario (tipo "Swap / Cambio") pero se guarda como DOS filas ligadas (`source='swap'`): una `sell`/`expense` en la cuenta que entrega el activo, una `buy` en la que recibe. La comisión siempre va en la pata que entrega.

- **Precio de cada pata**: si uno de los dos activos es stablecoin/fiat, el precio de AMBAS patas sale implícito de la relación `from_amount / to_amount` (≈ 1:1 el lado estable). Si **ninguno** de los dos es estable (ej. swap ETH → BTC), no hay relación implícita — hasta el 2026-08-25 esas patas se guardaban sin `unit_price`, lo que significa que la venta no generaba `realized_pnl` y el activo recibido entraba "gratis" (sin costo), distorsionando su `avg_price` hacia abajo.
- **Fix (2026-08-25)**: cuando ninguno de los dos lados es estable, se busca el precio de mercado real en USD de cada activo (`fetchCryptoPriceUSD` — primero mira `prices` si ya está cargado por tener una posición, si no lo pide directo a Binance) y se usa como `unit_price` de cada pata. Así la venta muestra P&L realizado real y el activo recibido entra con su costo correcto.

### CEDEARs
- `asset_type = 'cedear'` (segmento en pesos) o `'cedear_usd'` (segmento en dólares, ticker con sufijo D en el broker) — `asset` = ticker subyacente sin el sufijo (ej. `AAPL`) en ambos casos
- **`rate`** = ratio: cuántos CEDEARs equivalen a 1 acción subyacente (ej. 20 para AAPL) — aplica igual a los dos asset_type
- **`avg_price`**: para `cedear` es el precio promedio pagado en **ARS** por CEDEAR; para `cedear_usd` ya está en **USD** — no se convierte
- En PatrimonioTab/PortfolioTab/agent.py: `priceUSD = stockPriceUSD / ratio` (ambos tipos); `costUSD` para `cedear` = `(qty × avg_price_ARS) / cclRate`, para `cedear_usd` = `qty × avg_price` directo
- El Portfolio muestra `ratio N` en vez de `N% anual` para ambos tipos de CEDEAR
- **Gotcha (bug real, corregido 2026-08-17)**: `build_price_context()` comparaba `avg_price` en ARS contra `market_price` en USD sin convertir — daba pérdidas fantasma de ~99.9% en cada CEDEAR y una pérdida total absurda en el reporte semanal. Siempre convertir `avg_price` de `cedear` a USD con el dólar CCL antes de compararlo contra `market_price`.

### Posiciones flexible con crypto
Las posiciones `asset_type = 'flexible'` con activos no-fiat/no-stablecoin (ej. ETH en Nexo staking) obtienen precio de mercado igual que crypto normal. El interés devengado se suma a la cantidad en la moneda nativa antes de calcular el valor en USD.

### Auto-creación de posiciones desde transacciones
Tanto `POST /api/transactions` como `POST /api/transactions/batch` crean automáticamente una posición si el activo no tiene posición activa en esa cuenta.

### Interés devengado (frontend, `calcAccruedInterest`)
- Para `asset_type = 'fixed_term'`, `'fund'` o `'flexible'` con `rate` y `start_date`
- `accrued = quantity × (rate/100) × days_elapsed/365`
- Se suma al valor del activo en el cálculo del patrimonio total

### Ingest IA
- Cadena: Groq (texto/visión) → Gemini (fallback visión)
- El prompt extrae: date, description, amount, currency, type, category, unit_price, fee, fee_currency
- Tipos válidos: `income | expense | transfer` (el batch sanitiza tipos inválidos a 'expense')
- Fechas inválidas (ej. 'N/A') se reemplazan por la fecha actual

### Agente IA (`routers/agent.py`)
- Cadena: Groq → Gemini fallback
- Fuentes de precios:
  - **Crypto** (asset_type `crypto` o `flexible` no-fiat): directo a Binance desde el backend local — evita dependencia del CF Worker que puede tener problemas alcanzando Binance desde datacenter
  - **Stocks / CEDEARs**: `MAXIMOS_URL/api/quotes` → D1 (precio del último screener)
  - **Dólar CCL** (contado con liquidación): `MAXIMOS_URL/api/dollar` → dolarapi.com, casa `contadoconliqui`. Es el tipo de cambio que usa toda la app para ARS↔USD (no el blue) porque es al que se arbitran los CEDEARs.
- `to_yahoo_ticker`: maneja `flexible` no-fiat como crypto (devuelve `ASSET-USD`)
- `build_price_context()`: valuación completa de cartera con precio actual × cantidad, P&L no realizado (vs precio promedio de compra) y precio promedio explícito en cada posición. End_date/tasa/notas incluidas para plazos fijos. Si el mismo activo está repartido en más de una cuenta (ej. BTC en Binance y Nexo), agrega una sección "CONSOLIDADO POR ACTIVO" con cantidad total, precio promedio ponderado y P&L consolidado — para que el agente dé un solo veredicto por activo en vez de uno contradictorio por cuenta. También suma en Python (no le pide al modelo que sume) un `P&L NO REALIZADO TOTAL` y lo agrega ya calculado junto al `TOTAL CARTERA` — **gotcha real (corregido 2026-08-17)**: el modelo, sumando a mano el P&L de ~12 posiciones, inventó un total de +USD 2,447 cuando el real era -USD 227. Ningún prompt de "sumá con precisión" alcanza para que un LLM sume bien muchas líneas de forma confiable — cualquier total que dependa de sumar varias posiciones tiene que calcularse en código y pasarse ya hecho, nunca pedírselo al modelo.
- **Gotcha real (corregido 2026-08-17)**: el "CONSOLIDADO POR ACTIVO" ponderaba el `avg_price` YA GUARDADO por posición × cantidad remanente por cuenta — pero cuando cripto se transfiere entre cuentas propias, la transacción de entrada hereda el `avg_price` de la cuenta origen (`source='transfer'` con `unit_price` seteado, para que esa cuenta sola tenga un costo real — ver [[Transfer-inherited cost]] arriba). Ponderar por esas dos cuentas cuenta ese costo dos veces. El resultado: BTC daba avg $70,390 combinado en el agente vs. $75,766 en "Promedio combinado" de Patrimonio (que ya estaba bien desde antes). Fix: el consolidado ahora agrupa las compras REALES de todas las cuentas del activo (excluyendo `source='transfer'`) y divide costo total/cantidad comprada total — el mismo cálculo, línea por línea, que ya usa el frontend en `PatrimonioTab`. Cualquier cálculo cross-cuenta de avg_price tiene que ignorar `source='transfer'`, nunca usar el `avg_price` de la tabla `positions` directo.
- **Gotcha real (corregido 2026-08-17)**: la detección de "mismo activo en más de una cuenta" para el consolidado solo trackeaba posiciones con `avg_price` cargado — un activo repartido en dos cuentas donde UNA no tiene `avg_price` (ej. XRP: 20 en Binance con precio, 17 en Nexo sin precio) no se detectaba como multi-cuenta, y la cuenta sin precio desaparecía silenciosamente del reporte (el agente reportó "XRP -1.2%" contando solo los 20 de Binance, ignorando los 17 de Nexo). Fix: el tracking de multi-cuenta ahora se hace para TODA posición con precio de mercado conocido, tenga o no `avg_price` — el `avg_price`/P&L sigue siendo opcional, pero la cantidad/valor de cada cuenta ya no se pierde.
- **Gotcha real (corregido 2026-08-17)**: arreglar el `avg_price` mostrado en "CONSOLIDADO POR ACTIVO" (ver arriba) NO arregló el `P&L NO REALIZADO TOTAL` — ese total se seguía sumando desde el P&L naive por posición (con el `avg_price` contaminado por costo heredado de transferencia). Resultado: para un usuario con BTC en 2 cuentas, el total general quedaba inflado ~USD 400 de más (mostraba +590 cuando el real era +184). Fix: `build_price_context()` ahora, para cada activo multi-cuenta, resta del total la contribución naive (`naive_pnl`, trackeada por posición) y suma en su lugar el P&L consolidado correcto — antes de imprimir `TOTAL CARTERA`/`P&L NO REALIZADO TOTAL`, no después. Cualquier total agregado que dependa de `avg_price` por posición tiene que pasar por esta corrección si el activo puede estar repartido en más de una cuenta.
- **Mismo bug, en el frontend (corregido 2026-08-17)**: el número "No realizado" del header de `PatrimonioTab` (`totalPnl`) tenía el mismo problema — sumaba `p.pnlUSD` de TODAS las posiciones directo, sin la corrección que "Promedio combinado" ya aplicaba solo a su propia UI. Fix: se extrajo el cálculo de "Promedio combinado" a un objeto `consolidatedPnl` (calculado una sola vez, antes de `totalPnl`), y `totalPnl` ahora resta la contribución naive de cada activo multi-cuenta y suma la del `consolidatedPnl` en su lugar — mismo patrón que el backend, y ahora ambos leen del mismo cálculo (antes estaban duplicados y podían divergir, que es justo lo que pasó).
- **Ídem, pero en la ficha INDIVIDUAL de cada posición (corregido 2026-08-17)**: no alcanzaba con arreglar los totales — la ficha de "BTC en Nexo" sola (en el desglose por tipo de activo de Patrimonio) seguía usando el `avg_price` local de esa cuenta ($68.000, contaminado) y mostraba +16.7% de ganancia cuando el real, contra el promedio ponderado real ($75.766), es +4.5%. Fix definitivo en `PatrimonioTab` (`App.jsx`): se separó `enriched` en dos pasadas — la primera solo calcula precio/valor de mercado; entre pasadas se arma `consolidatedPnl` (mismo cálculo de "Promedio combinado"); la segunda pasada usa, para CUALQUIER posición de un activo multi-cuenta (no solo el total), el promedio ponderado real de `consolidatedPnl` en vez de `p.avg_price`. Mismo fix aplicado en `build_price_context()` del backend (`agent.py`) — reestructurado en dos pasadas por la misma razón, así las líneas individuales que ve el agente en el chat/reporte también quedan consistentes con el consolidado.
- **Bug de interés devengado en `build_price_context()` (corregido 2026-08-17, backend únicamente)**: la fórmula de P&L por posición era `upnl = (market_price - avg_usd) * qty`, pero el "valor" mostrado en la misma línea usa `qty + interés devengado`. El interés devengado no tiene costo (es ganancia pura, ver "Posiciones flexible con crypto"), así que debería contar como P&L — pero al multiplicar `market_price * qty` (sin el interés) en vez de restar del `value_usd` ya calculado (que sí lo incluye), esa porción de ganancia se perdía. Para BTC en Nexo esto era ~USD 12 de diferencia (visible recién al comparar la suma de las líneas individuales contra el consolidado, que sí lo hacía bien). Fix: `upnl = value_usd - avg_usd * qty` (restar del valor ya calculado, no recalcular con `market_price * qty`) — mismo criterio que ya usaba correctamente el frontend (`pnlUSD = valueUSD - costUSD`) y la propia sección CONSOLIDADO. Si se toca esta fórmula de nuevo, verificar que la suma de las líneas individuales de un activo multi-cuenta coincida EXACTO con su línea consolidada — si no coincide, hay interés devengado (u otra cosa) que no se está contando igual en los dos lados.
- **Gotcha de fondo — no todas las compras quedan cargadas como transacción**: el usuario a veces corrige una posición directo en Portfolio (✏️) sin dejar una transacción de respaldo. Esto rompe cualquier cálculo que solo mire `transactions` para reconstruir el costo real. `pooled_avg_usd()` en `build_price_context()` (y su equivalente `consolidatedPnl` en `PatrimonioTab` del frontend) manejan esto con un cálculo de DOS PASOS que NO se puede colapsar en uno solo:
  1. **Pool global de cuentas CON compras propias** (excluyendo `source='transfer'`): costo total comprado / cantidad total comprada = un promedio único (weighted-average-cost estándar, no cambia al vender) — se aplica a la cantidad que esas cuentas tienen HOY.
  2. **Fallback por cuenta SIN ninguna compra propia con precio**: usa el `avg_price` guardado de esa posición (manual o lo que sea) tal cual, ponderado por su cantidad actual — se suma aparte, no se mezcla en el pool del punto 1.
  - **Error real cometido y revertido en el camino (mismo día)**: la primera versión de este fix ponderaba el promedio "limpio" de CADA cuenta por su cantidad ACTUAL en vez de por su cantidad COMPRADA — eso rompe la matemática en cuanto una cuenta recibió parte de su saldo por transferencia (su cantidad actual no es la misma que compró directamente). Dio BTC a $68.870 en vez de $75.766. La forma de detectar este tipo de error: la suma de las líneas individuales de un activo multi-cuenta SIEMPRE tiene que coincidir centavo a centavo con su línea consolidada — si no coincide, está mal.
- **Gotcha real (corregido 2026-08-17)**: el modelo, con el contexto completo y correcto de ETH (P&L -30.5% bien calculado), directamente omitió la fila de ETH en la tabla de veredictos de un reporte semanal — sin ningún motivo, con 13 activos en la tabla se "olvidó" uno. No era un problema de datos, era el modelo salteándose una fila. Fix: `build_price_context()` ahora agrega un `CHECKLIST` explícito al final con la lista exacta de tickers que tienen que tener una fila, y el prompt le pide contar contra esa lista antes de cerrar la sección. Ningún prompt "no te olvides de nada" genérico alcanza — hay que darle al modelo la lista concreta a chequear, mismo principio que ya se aplicó para las sumas de P&L.
- **Gotcha real, frontend (corregido 2026-08-25)**: "Promedio combinado" en `PatrimonioTab` calculaba `avg_price`/P&L para CUALQUIER activo multi-cuenta, incluyendo stablecoins (USDT/USDC) — que valen ~1:1 siempre y no tienen costo de compra real. Con un `avg_price` viejo/erróneo cargado por error en una posición de USDT (encontrado: $1.4991, copiado de otro activo), esto generó un P&L fantasma de "+671%" en una stablecoin. Fix: las stablecoins ahora se muestran en "Promedio combinado" (para ver cuánto hay repartido entre wallets) pero con `avgPrice`/`totalPnL` siempre `null` — nunca se les calcula precio promedio ni P&L, sea cual sea el dato guardado. El backend (`agent.py`) ya excluía stablecoins de este cálculo desde el principio; el bug era solo del puerto a `App.jsx`.
- **Gotcha real de razonamiento, no de cálculo (corregido 2026-08-25)**: el prompt le decía "ganancia/pérdida = P&L realizado + no realizado", correcto para hablar de la CARTERA completa — pero el modelo aplicó la misma suma al veredicto de UNA posición puntual (ej. "ETH tiene una pérdida total de -506" = -353 no realizado + -154 realizado de una venta vieja). El realizado ya pasó, no cambia si vendés lo que tenés ahora — sumarlo infla el número y empuja a vender en base a plata que ya no está en juego. Fix: se agregó una regla explícita en ambos prompts (chat y reporte semanal) — el veredicto de una posición usa SOLO su P&L no realizado; el realizado se puede mencionar aparte pero nunca se suma para justificar la decisión de esa posición.
- `build_technical_context()`: consulta `MAXIMOS_URL/api/stocks` para cada lista relevante (crypto, adrs_arg, sp500) y agrega señal, score, zona, RSI, ADX, MACD, volumen, EMAs MA20/50/200, patrón de velas y SL/TP de cada activo en cartera.
- `build_fundamentals_context()`: consulta `MAXIMOS_URL/api/info` para cada stock/CEDEAR en cartera. Agrega nombre, sector, consensus de analistas (recommendation_key + cantidad), target price con rango, PE forward/trailing, beta, dividendo y próximo earnings date. Solo para asset_type `stock` y `cedear`. Corre en paralelo con los otros contextos.
- `build_crypto_sentiment_context()`: solo si hay crypto/flexible no-fiat en cartera. Fuentes:
  - **Fear & Greed** (alternative.me): índice 0-100 con clasificación
  - **CoinGecko `/global`** (demo API, `COINGECKO_API_KEY`): BTC dominance, market cap total y cambio 24h
  - **CoinGecko `/coins/markets`**: rank, ATH y % desde ATH, market cap y cambio 24h por coin en cartera. `COINGECKO_IDS` mapea symbols a IDs de CoinGecko (BTC→bitcoin, ETH→ethereum, etc.)
  - **Binance Futures** (público, sin key): funding rate, open interest y L/S ratio para BTC/ETH/SOL/BNB/XRP
- `_calc_accrued(p)`: replica el JS `calcAccruedInterest` — `quantity × (rate/100) × days/365`
- Los cuatro contextos corren en paralelo con `asyncio.gather()`
- Contexto enviado al modelo: cuentas, valuación con precios reales y P&L por posición, análisis técnico del screener, fundamentales y consenso de analistas, sentimiento y datos de mercado crypto, últimas 50 transacciones, resumen mensual, P&L realizado acumulado, totales en USD y ARS
- SYSTEM_PROMPT: asesor directo que usa números exactos del usuario, toma posición concreta, no aproxima cuando tiene datos exactos, cruza consensus institucional con señal técnica, calcula upside vs target de analistas, usa funding rate y Fear & Greed como contexto macro, filosofía DCA + largo plazo, contexto argentino (CCL, CEDEARs, plazo fijo vs inflación)

### Configuración de API keys (`main.py`)
- `GET /api/config`: devuelve los valores actuales de `GROQ_API_KEY` y `GOOGLE_API_KEY` (texto plano, app local)
- `POST /api/config`: recibe `{groq_key, google_key}`, escribe en `finanzas/backend/.env` y `backend/.env` usando `dotenv.set_key()`, y actualiza `os.environ` en el proceso actual
- El backend maximos requiere reinicio para tomar las nuevas keys

### Maximos status/start (main.py)
- `/api/maximos/status`: hace GET a `http://localhost:8000/api/status` con timeout 2s; devuelve `{"running": bool}`
- `/api/maximos/start`: si no está corriendo, lanza `uvicorn main:app --port 8000` en `backend/` con `CREATE_NEW_CONSOLE` (Windows) o proceso daemon (Unix)

## Gotchas

- El frontend hace proxy al backend via Vite (`vite.config.js` → `/api → localhost:8001`)
- `end_date = ''` (string vacío) ≠ `NULL` en SQLite — siempre usar `(end_date IS NULL OR end_date = '')` para posiciones activas
- `prices[ticker]` en el frontend es un objeto `{ price, change, change_pct }`, no un número plano — acceder con `.price`
- `_sync_position` descuenta posiciones `fixed_term`/`fund` activas (end_date futura) para no duplicar en flexible
- `_sync_position` recalcula `avg_price` solo desde ingresos con `unit_price > 0` — las transferencias sin precio no bloquean el cálculo. Si no hay compras con precio, preserva el avg_price manual.
- CEDEARs: `rate` = ratio (no tasa de interés). `avg_price` en ARS para `asset_type='cedear'`, en USD para `asset_type='cedear_usd'` (segmento en dólares, ticker con sufijo D en el broker) — no mezclar los dos al comparar contra market_price
- `$pid` es variable reservada en PowerShell — usar `$procId` en stop-all.ps1
- `Test-NetConnection` es más confiable que `Invoke-WebRequest` para port polling en ventanas ocultas de PowerShell
- **Binance desde CF Worker**: el Worker puede tener problemas alcanzando `api.binance.com` desde datacenter. El agente fetchea crypto directo a Binance desde el backend local para evitarlo.
- **`env.DB` vs `env.maximos_db`**: el binding D1 en el Worker se llama `maximos_db` (ver `wrangler.toml`). Usar siempre `env.maximos_db`, nunca `env.DB`.
- **`flexible` no-fiat en `to_yahoo_ticker`**: posiciones con `asset_type='flexible'` y activo crypto (ej. ETH en Nexo staking) deben devolver `ETH-USD`, no `ETH`. El caso está manejado explícitamente.
- **`GET /api/config` lee del .env directo**: usa `dotenv_values(ENV_PATH)` en cada request para reflejar el estado real del archivo, no `os.environ` que solo refleja lo que había al iniciar el servidor.
- **CoinGecko keyless vs demo**: la API pública sin key tiene rate limits muy bajos (10-30/min, compartido por IP). Usar siempre la demo key gratuita via header `x-cg-demo-api-key`. Se configura en ⚙️ o directamente en `.env` como `COINGECKO_API_KEY`.
- **Binance Futures público**: `fapi.binance.com` es accesible sin API key para datos de mercado (funding rate, OI, L/S ratio). Distinto de `api.binance.com` (spot) que también es público.

## UI

- React + Vite, un solo archivo `App.jsx`
- Tailwind CSS, acento ámbar (`amber-500`)
- Header oscuro (`bg-slate-900`) con borde top `3px solid #f59e0b`
- Tabs sticky: Patrimonio · Portfolio · Movimientos · Cuentas · Agente
- `SettingsModal`: abre con ⚙️; toggle Online/Local para precios; sección API Keys con inputs show/hide para configurar Groq, Google y CoinGecko sin tocar el .env. Las tres son gratuitas.
- Portfolio: botón 🔄 por cuenta para disparar sync de posiciones. Usa `max-w-6xl`.
- Portfolio AccountCard: CEDEARs muestran costo total en ARS + cantidad; crypto/stocks/flexible muestran valor de mercado USD actual + cantidad + línea de precio promedio de compra con % P&L en verde/rojo (`prom. USD X · ±Y%`). Fallback a costo histórico si no hay precio disponible. Scroll activado solo cuando hay más de 10 posiciones.
- `MovimientosTab`: tabla con scroll horizontal (`max-w-6xl`). Columnas: Fecha · Cuenta · Descripción · Categoría · Tipo · Monto · Precio unit. · P&L realizado · Comisión · (✏️ 🗑 on hover). El modal de carga de movimientos no cambió.
- `prices` y `cclRate` (dólar CCL, no blue) viven en `App` y se fetchean una vez al cargar posiciones — compartidos entre `PatrimonioTab` y `PortfolioTab`.
- `chatMessages` vive en `App` (constante `INITIAL_MESSAGES`) — persiste entre tabs sin reiniciar la conversación.
- `PatrimonioTab`: flexible no-fiat obtiene precio de mercado y muestra P&L igual que crypto; CEDEARs usan ratio para calcular priceUSD
- Formulario de movimientos: labels contextuales para CEDEARs (Monto/Cantidad, Moneda/Activo, precio en ARS vs USD)
- Transferencias entre cuentas: el formulario envía `_transfer_to` en un solo `onSave`. `saveTransaction` hace PATCH del egreso en origen y POST del ingreso en destino — evita el bug donde editar a tipo transferencia sobreescribía el mismo registro dos veces.
- Constantes de URL en App.jsx:
  - `MAXIMOS_LOCAL = 'http://localhost:8000'`
  - `MAXIMOS_ONLINE = import.meta.env.VITE_MAXIMOS_URL || 'https://maximos-worker.luchotour.workers.dev'`
- `maximosMode` persiste en `localStorage` ('online' por defecto)

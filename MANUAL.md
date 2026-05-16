# Manual de uso — Stock Screener

> Guía completa para entender y usar el screener en https://maximos.pages.dev

---

## ¿Qué es y para qué sirve?

El Stock Screener analiza automáticamente cientos de acciones, ETFs y criptomonedas usando indicadores técnicos y les asigna un **puntaje del 0 al 100**. El objetivo es ayudarte a encontrar rápidamente los activos con mejor setup técnico para operar, sin tener que revisar cada gráfico uno por uno.

Los resultados se actualizan **automáticamente todos los días hábiles** (2am UTC). También podés pedir una actualización manual cuando quieras con el botón **Analizar**.

---

## Cómo usar la app paso a paso

### 1. Elegí una lista

En la parte superior hay botones para seleccionar qué activos querés analizar:

| Lista | Qué incluye |
|---|---|
| **S&P 500** | Las 503 empresas más grandes de EE.UU. |
| **Nasdaq 100** | Las 100 empresas tech más importantes |
| **ETFs** | 49 fondos cotizados (sectores, bonos, commodities, etc.) |
| **ADRs Argentina** | GGAL, YPF, MELI, GLOB, VIST, BBAR y más |
| **Crypto** | Las principales criptos por market cap (sin stablecoins) |

Para **Crypto** aparece un slider que te permite elegir cuántas criptos incluir (10 a 100).

### 2. Presioná "Analizar"

Al hacer click el screener se pone en marcha. Dependiendo de la lista puede tardar:

- ADRs Argentina: ~1-2 minutos
- ETFs / Nasdaq 100: ~2-3 minutos
- S&P 500: ~5-8 minutos
- Crypto: ~3-5 minutos

Una barra de progreso muestra cuántos activos se procesaron. **No cierres la pestaña** — el análisis corre en el servidor, podés minimizar el browser sin problema.

### 3. Filtrá los resultados

Una vez terminado el análisis tenés dos formas de filtrar:

**Por señal** — los botones de colores en la barra de filtros:
- Todas, Compra Fuerte, Compra, Neutral, Venta, Venta Fuerte

**Por ticker** — el campo de búsqueda de texto. Escribí el símbolo (ej: "AAPL") para encontrarlo al instante en la lista activa.

También podés hacer click en el encabezado de cualquier columna para ordenar por ese valor.

### 4. Revisá el detalle de un ticker

Hacé click en cualquier fila de la tabla para abrir el **panel de detalle**. Ahí vas a ver:

- Score completo (Long y Short)
- Todos los indicadores técnicos
- Niveles de Stop Loss y Take Profit
- Señal del Helper Pulse
- **Recomendación generada por IA** (se carga automáticamente)

---

## Cómo leer la tabla

### Score y Señal

La columna **Score** muestra una barra de progreso con el puntaje (0-100) y debajo la dirección (LONG / SHORT / NEUTRAL).

La columna **Señal** resume todo en un badge de color:

| Color | Señal | Qué significa |
|---|---|---|
| Verde oscuro | **Compra Fuerte** | Score ≥ 75 en dirección LONG. Todos los indicadores alineados. Alta convicción. |
| Verde | **Compra** | Score 60-74 en LONG. Mayoría de señales positivas. |
| Gris | **Neutral** | Score bajo en ambas direcciones. Sin setup definido. |
| Naranja | **Venta** | Score 60-74 en SHORT. Evitar comprar. |
| Rojo | **Venta Fuerte** | Score ≥ 75 en SHORT. Confluencia bajista total. |

### Zona

La zona estructural indica dónde está el precio respecto a su rango histórico reciente:

| Zona | Qué significa | ¿Conviene entrar? |
|---|---|---|
| **DISCOUNT** | Precio por debajo de la regresión lineal — zona de valor | Sí, mejor relación riesgo/beneficio |
| **FAIR** | Precio en zona media | Neutral, depende del setup |
| **PREMIUM** | Precio extendido, por encima de la regresión | No, ya subió mucho — riesgo de corrección |

### RSI

Índice de fuerza relativa. Mide si el activo está sobrecomprado o sobrevendido:

- **< 30** → Sobreventa extrema. Posible rebote técnico.
- **30-50** → Momentum débil o recuperándose.
- **50-70** → Momentum positivo normal.
- **> 70** → Sobrecompra. Riesgo de corrección a corto plazo.

### ADX

Mide la **fuerza** de la tendencia (no la dirección):

- **< 20** → Tendencia débil o mercado lateral. Mayor riesgo de señales falsas.
- **20-30** → Tendencia activa, señales más confiables.
- **> 30** → Tendencia muy fuerte. Alta probabilidad de continuación.

### vs MA200

Diferencia porcentual del precio respecto a su media móvil de 200 días:

- **Positivo** → Precio por encima del MA200. Tendencia principal alcista.
- **Negativo** → Precio por debajo del MA200. Tendencia principal bajista.

### Vol ×

Volumen de hoy comparado con el promedio de los últimos 20 días:

- **1.5x o más** → Volumen alto. El movimiento tiene confirmación institucional.
- **0.7x o menos** → Volumen bajo. Mayor riesgo de fakeout (movimiento falso).

### % Máx / % Mín 52s

Distancia al máximo y mínimo de las últimas 52 semanas:

- **% Máx cerca de 0%** → El precio está en máximos del año. Momentum fuerte pero recorrido limitado.
- **% Mín bajo (ej: +5%)** → El precio está cerca del piso anual. Posible soporte.

### MACD

Indicador de momentum de tendencia:

- **▲ (positivo)** → Momentum alcista.
- **▼ (negativo)** → Momentum bajista.

### Pulse

Señal del Helper Pulse (ver sección siguiente).

### SL / TP1

Stop Loss y Take Profit calculados automáticamente usando el ATR (volatilidad promedio del activo):

- **SL** = precio actual − ATR × 1.5 (para posiciones largas)
- **TP1** = precio actual + ATR × 1.5

---

## Helper Pulse — señales de divergencia

El Helper Pulse detecta divergencias entre el precio y el momentum del RSI. Es una señal de segunda capa que agrega contexto a la dirección del activo.

### ¿Qué es una divergencia?

Cuando el precio y el momentum van en **direcciones opuestas**, hay una divergencia. Suele preceder a un cambio de tendencia o confirmar una continuación.

### Tipos de señal

| Señal | Color | Qué significa |
|---|---|---|
| **GIRO UP** | Cyan | El precio hizo un mínimo más bajo, pero el momentum hizo uno más alto. Señal clásica de reversión alcista. Alta calidad. |
| **SIGUE UP** | Amarillo | El precio hizo un mínimo más alto y el momentum uno más bajo. Confirma la continuación de la tendencia alcista. |
| **GIRO DN** | Rojo | El precio hizo un máximo más alto, pero el momentum hizo uno más bajo. Señal de reversión bajista. Alta calidad. |
| **SIGUE DN** | Naranja | El precio hizo un máximo más bajo y el momentum uno más alto. Confirma la continuación bajista. |
| **AGOT. SUP** | Rosa | El momentum llegó a zona alta sin divergencia. Precaución con posiciones largas — posible agotamiento. |
| **AGOT. INF** | Azul | El momentum llegó a zona baja sin divergencia. Posible piso de momentum — vigilar entrada. |

---

## Recomendación de IA

Al abrir el detalle de cualquier ticker, la app genera automáticamente un análisis en texto usando inteligencia artificial. El modelo recibe todos los indicadores calculados y produce un párrafo de 3-4 oraciones en español con:

- Resumen del setup
- Puntos clave del momentum y zona
- Sugerencia operativa

La IA usa tres proveedores en cascada: primero intenta con **Cloudflare Workers AI** (muy rápido, en el borde de la red), si falla usa **Groq**, y si también falla usa **Gemini**.

---

## Flujo de trabajo recomendado

### Para encontrar oportunidades de compra

1. Seleccioná la lista que te interesa y presioná **Analizar**
2. Filtrá por **Compra Fuerte**
3. Chequeá que **Dir** sea LONG y **Zona** sea DISCOUNT o FAIR
4. Confirmá **ADX > 20** (idealmente > 25)
5. Verificá **vs MA200 positivo** (precio sobre la media de largo plazo)
6. Si el **Pulse** muestra GIRO UP o SIGUE UP → mayor confluencia
7. Hacé click en el ticker para ver el detalle completo y la recomendación de IA
8. Usá el **SL/TP1** para calcular el tamaño de tu posición

### Para monitorear activos que ya tenés

1. Cargá la lista correspondiente
2. Buscá el ticker en el campo de búsqueda
3. Revisá si el score se mantiene o cayó desde que entraste
4. Si la señal pasó a Neutral o Venta y el precio está cerca del TP1, considerá cerrar

### Señales de alerta para salir

- La dirección cambió de LONG a SHORT
- El ADX cayó por debajo de 20 (tendencia perdiendo fuerza)
- El Pulse muestra GIRO DN o AGOT. SUP
- El precio cruzó por debajo del MA200

---

## Frecuencia de actualización

| Lista | Actualización automática |
|---|---|
| S&P 500 | Lunes a viernes, 2am UTC (11pm ARG) |
| Nasdaq 100 | Lunes a viernes, 2am UTC |
| ETFs | Lunes a viernes, 2am UTC |
| ADRs Argentina | Lunes a viernes, 2am UTC |
| Crypto | Solo cuando presionás **Analizar** manualmente |

Podés pedir una actualización manual de cualquier lista en cualquier momento con el botón **Analizar**. Los resultados anteriores se muestran instantáneamente mientras el nuevo análisis corre en segundo plano.

---

## Preguntas frecuentes

**¿Cuándo debo usar "Analizar" manualmente?**
Los datos se actualizan solos de lunes a viernes. Si querés ver el estado actual en medio del día, o si querés analizar Crypto (que no está en el cron automático), presioná Analizar.

**¿Por qué tarda tanto?**
El screener descarga datos de Yahoo Finance para todos los tickers de la lista y calcula más de 20 indicadores por activo. Para 503 tickers del S&P 500 eso toma unos minutos. ADRs Argentina son solo 17 tickers, por eso es mucho más rápido.

**¿Por qué la primera pantalla está vacía?**
Porque nunca se corrió el screener para esa lista. Presioná Analizar y esperá. La próxima vez que entres ya van a estar los datos precalculados.

**¿Los datos son en tiempo real?**
No. Los precios y datos históricos vienen de Yahoo Finance con datos del cierre del día anterior. El screener trabaja con datos diarios, no intraday.

**¿Por qué a veces la recomendación de IA tarda?**
La IA intenta tres proveedores en cascada. Normalmente responde en 2-3 segundos con Cloudflare Workers AI. Si tarda más es porque cayó al fallback de Groq.

**¿Las señales son recomendaciones financieras?**
No. El screener es una herramienta de filtrado técnico. Siempre realizá tu propio análisis antes de operar. Ninguna señal técnica garantiza resultados.

**¿Puedo buscar un ticker específico?**
Sí. Cargá la lista que corresponde (ej: S&P 500 para acciones de EE.UU.) y usá el campo de búsqueda para filtrar al instante por símbolo.

---

## Glosario

| Término | Definición |
|---|---|
| **Score** | Puntaje 0-100 que resume la calidad del setup técnico |
| **LONG** | Dirección alcista — el sistema indica que el activo tiene más fuerza compradora |
| **SHORT** | Dirección bajista — más fuerza vendedora |
| **EMA** | Media móvil exponencial. La EMA 200 representa la tendencia principal |
| **ADX** | Average Directional Index — mide la fuerza de la tendencia |
| **RSI** | Relative Strength Index — mide si el activo está sobrecomprado o sobrevendido |
| **MACD** | Moving Average Convergence Divergence — indicador de momentum |
| **ATR** | Average True Range — mide la volatilidad promedio del activo |
| **Bollinger %B** | Posición del precio dentro de las Bandas de Bollinger (0% = banda inferior, 100% = superior) |
| **POC** | Point of Control — precio con mayor volumen acumulado en los últimos 70 días |
| **Divergencia** | Cuando el precio y el momentum van en direcciones opuestas |
| **SL** | Stop Loss — nivel de precio donde salís si el trade va en tu contra |
| **TP1** | Take Profit 1 — primer objetivo de precio para cerrar la posición |
| **MTF** | Multi-TimeFrame — análisis en múltiples temporalidades |
| **Regresión lineal** | Canal estadístico que representa el rango "justo" del precio en los últimos 100 días |

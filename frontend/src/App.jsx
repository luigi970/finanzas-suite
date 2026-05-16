import { useState, useEffect, useCallback } from "react";

function generateRecommendation(s) {
  const parts = [];
  const { signal, zone, pulse_signal: pulse, pulse_state, adx, mom,
          rsi, macd_hist, vol_ratio, pct_b, pct_from_high, pct_from_low,
          long_score, short_score, poc, price } = s;

  // ── 1. Apertura: calidad del setup ────────────────────────────────────────
  if (signal === "compra_fuerte")
    parts.push(`Setup alcista de alta calidad (Long ${long_score}/100). Múltiples señales alineadas — alta convicción.`);
  else if (signal === "compra")
    parts.push(`Setup alcista moderado (Long ${long_score}/100). Mayoría de señales positivas, pero no todas confirmadas.`);
  else if (signal === "neutral")
    parts.push(`Sin dirección operativa clara (Long ${long_score} / Short ${short_score}). Mercado en equilibrio.`);
  else if (signal === "venta")
    parts.push(`Sesgo bajista moderado (Short ${short_score}/100). Evitar compras en este nivel.`);
  else if (signal === "venta_fuerte")
    parts.push(`Setup bajista de alta calidad (Short ${short_score}/100). No comprar — presión vendedora dominante.`);

  // ── 2. Zona estructural ───────────────────────────────────────────────────
  if (zone === "discount")
    parts.push("Zona DISCOUNT: precio por debajo de la regresión lineal — excelente relación riesgo/beneficio para longs.");
  else if (zone === "premium")
    parts.push("Zona PREMIUM: precio extendido por encima de la regresión lineal — comprar acá implica pagar caro.");
  else if (zone === "fair")
    parts.push("Zona FAIR: precio en zona media de la regresión — entrada neutra, sin ventaja estructural marcada.");

  if (poc != null && price != null) {
    const distPct = ((price - poc) / poc * 100).toFixed(1);
    if (Math.abs(price - poc) / poc < 0.02)
      parts.push(`Precio muy cerca del POC ($${poc.toFixed(2)}) — nivel de mayor concentración de volumen, zona de decisión clave.`);
    else if (price > poc)
      parts.push(`Precio ${distPct}% sobre el POC ($${poc.toFixed(2)}) — el soporte volumétrico queda abajo.`);
    else
      parts.push(`Precio ${Math.abs(distPct)}% bajo el POC ($${poc.toFixed(2)}) — resistencia volumétrica arriba.`);
  }

  // ── 3. Momentum ───────────────────────────────────────────────────────────
  const momentumParts = [];
  if (rsi != null) {
    if (rsi < 30)        momentumParts.push(`RSI ${rsi} en sobreventa extrema — posible rebote técnico`);
    else if (rsi < 40)   momentumParts.push(`RSI ${rsi} en zona de sobreventa — momentum débil pero mejorando`);
    else if (rsi > 70)   momentumParts.push(`RSI ${rsi} en sobrecompra — riesgo de corrección a corto plazo`);
    else if (rsi > 60)   momentumParts.push(`RSI ${rsi} con momentum positivo pero vigilar sobrecompra`);
    else                 momentumParts.push(`RSI ${rsi} en zona neutral`);
  }
  if (mom != null) {
    if (Math.abs(mom) >= 15)
      momentumParts.push(`momentum RSI-50 ${mom > 0 ? "+" : ""}${mom} (zona de potencia ${mom > 0 ? "alcista" : "bajista"})`);
    else if (mom !== 0)
      momentumParts.push(`momentum RSI-50 ${mom > 0 ? "+" : ""}${mom}`);
  }
  if (macd_hist != null)
    momentumParts.push(`MACD histograma ${macd_hist > 0 ? "positivo ▲" : "negativo ▼"}`);
  if (momentumParts.length)
    parts.push(momentumParts.join(", ") + ".");

  // ── 4. Volumen ────────────────────────────────────────────────────────────
  if (vol_ratio != null) {
    if (vol_ratio >= 2.0)
      parts.push(`Volumen ${vol_ratio.toFixed(1)}x el promedio — movimiento fuertemente confirmado.`);
    else if (vol_ratio >= 1.5)
      parts.push(`Volumen ${vol_ratio.toFixed(1)}x el promedio — confirmación sólida del movimiento.`);
    else if (vol_ratio >= 1.2)
      parts.push(`Volumen ${vol_ratio.toFixed(1)}x el promedio — confirmación moderada.`);
    else if (vol_ratio < 0.7)
      parts.push(`Volumen ${vol_ratio.toFixed(1)}x el promedio — movimiento sin confirmación de volumen, mayor riesgo de fakeout.`);
  }

  // ── 5. Bollinger %B ───────────────────────────────────────────────────────
  if (pct_b != null) {
    if (pct_b < 0.1)
      parts.push(`%B ${(pct_b * 100).toFixed(0)}%: precio tocando la banda inferior de Bollinger — sobreventa técnica, posible rebote.`);
    else if (pct_b < 0.25)
      parts.push(`%B ${(pct_b * 100).toFixed(0)}%: precio cerca de la banda inferior — zona de valor técnico.`);
    else if (pct_b > 0.9)
      parts.push(`%B ${(pct_b * 100).toFixed(0)}%: precio tocando la banda superior de Bollinger — sobrecompra técnica.`);
    else if (pct_b > 0.75)
      parts.push(`%B ${(pct_b * 100).toFixed(0)}%: precio cerca de la banda superior — zona extendida.`);
  }

  // ── 6. Distancia 52 semanas ───────────────────────────────────────────────
  if (pct_from_high != null && pct_from_low != null) {
    if (pct_from_high > -5)
      parts.push(`En máximos del año (${pct_from_high.toFixed(1)}% del techo) — momentum fuerte pero recorrido limitado al alza.`);
    else if (pct_from_high < -40)
      parts.push(`${Math.abs(pct_from_high).toFixed(0)}% debajo del máximo anual — amplio recorrido potencial si recupera tendencia.`);
    else if (pct_from_low < 15)
      parts.push(`Solo ${pct_from_low.toFixed(1)}% sobre el mínimo anual — zona de piso, vigilar soporte.`);
  }

  // ── 7. ADX y fuerza de tendencia ─────────────────────────────────────────
  if (adx != null) {
    if (adx >= 30)
      parts.push(`ADX ${adx}: tendencia muy fuerte — alta probabilidad de continuación.`);
    else if (adx >= 20)
      parts.push(`ADX ${adx}: tendencia activa con fuerza suficiente.`);
    else
      parts.push(`ADX ${adx} por debajo de 20 — tendencia débil o mercado lateral, mayor riesgo de señales falsas.`);
  }

  // ── 8. Helper Pulse ───────────────────────────────────────────────────────
  if (pulse_state === "ALCISTA FUERTE")
    parts.push("Pulse en estado ALCISTA FUERTE: momentum RSI-50 en zona de potencia y creciendo.");
  else if (pulse_state === "BAJISTA FUERTE")
    parts.push("Pulse en estado BAJISTA FUERTE: momentum RSI-50 en zona de potencia negativa y cayendo.");

  if (pulse === "GIRO UP")
    parts.push("Pulse detecta divergencia alcista regular (GIRO UP): precio marcó mínimo más bajo pero el momentum no — señal clásica de reversión al alza.");
  else if (pulse === "SIGUE UP")
    parts.push("Pulse detecta divergencia alcista oculta (SIGUE UP): el momentum confirma continuación de la tendencia alcista.");
  else if (pulse === "GIRO DN")
    parts.push("Pulse detecta divergencia bajista regular (GIRO DN): precio marcó máximo más alto pero el momentum no — señal de reversión a la baja.");
  else if (pulse === "SIGUE DN")
    parts.push("Pulse detecta divergencia bajista oculta (SIGUE DN): el momentum confirma continuación de la tendencia bajista.");
  else if (pulse === "AGOT. SUP")
    parts.push("Pulse en agotamiento superior: momentum en zona alta sin divergencia — precaución con posiciones largas.");
  else if (pulse === "AGOT. INF")
    parts.push("Pulse en agotamiento inferior: posible piso de momentum — vigilar señal de entrada.");

  // ── 9. Cierre operativo ───────────────────────────────────────────────────
  if (signal === "compra_fuerte" || signal === "compra") {
    if (zone === "premium" && (rsi == null || rsi > 65))
      parts.push("Considerar esperar retroceso a zona FAIR antes de entrar para mejorar el R/R.");
    else
      parts.push("Entrada válida respetando el SL definido por ATR.");
  } else if (signal === "neutral") {
    parts.push("Esperar que el score supere 60 con dirección definida antes de operar.");
  } else {
    parts.push("No operar en largo hasta que las condiciones mejoren.");
  }

  return parts.length ? parts : ["Datos insuficientes para generar recomendación."];
}

function TickerModal({ stock: s, onClose }) {
  if (!s) return null;

  const sigCfg = {
    compra_fuerte: { label: "Compra Fuerte", color: "bg-emerald-500" },
    compra:        { label: "Compra",        color: "bg-green-400" },
    neutral:       { label: "Neutral",       color: "bg-gray-400" },
    venta:         { label: "Venta",         color: "bg-orange-400" },
    venta_fuerte:  { label: "Venta Fuerte",  color: "bg-red-500" },
  }[s.signal] ?? { label: "—", color: "bg-gray-400" };

  const zoneCfg = {
    discount: { label: "DISCOUNT", cls: "bg-teal-100 text-teal-800" },
    fair:     { label: "FAIR",     cls: "bg-gray-100 text-gray-600" },
    premium:  { label: "PREMIUM",  cls: "bg-purple-100 text-purple-800" },
  }[s.zone] ?? { label: "—", cls: "bg-gray-100 text-gray-600" };

  const pulseCfg = {
    "GIRO UP":   "bg-cyan-100 text-cyan-800",
    "SIGUE UP":  "bg-yellow-100 text-yellow-800",
    "GIRO DN":   "bg-red-100 text-red-800",
    "SIGUE DN":  "bg-orange-100 text-orange-800",
    "AGOT. SUP": "bg-pink-100 text-pink-800",
    "AGOT. INF": "bg-blue-100 text-blue-800",
  }[s.pulse_signal] ?? "bg-gray-100 text-gray-500";

  const pct = (val, base) => base ? ((val - base) / base * 100).toFixed(2) : null;
  const slPct  = s.sl  ? pct(s.sl,  s.price) : null;
  const tp1Pct = s.tp1 ? pct(s.tp1, s.price) : null;
  const tp2Pct = s.tp2 ? pct(s.tp2, s.price) : null;

  const rrRatio = (slPct && tp1Pct)
    ? Math.abs(tp1Pct / slPct).toFixed(1)
    : null;
  const rr2Ratio = (slPct && tp2Pct)
    ? Math.abs(tp2Pct / slPct).toFixed(1)
    : null;

  const recommendation = generateRecommendation(s);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-gray-100">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-2xl font-bold text-gray-900">{s.ticker}</h2>
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold text-white ${sigCfg.color}`}>
                  {sigCfg.label}
                </span>
              </div>
              <div className="text-xl font-semibold text-gray-700">${s.price?.toFixed(2)}</div>
              <div className="flex items-center gap-2 mt-1.5">
                <span className={`text-xs font-bold ${s.direction === "LONG" ? "text-green-600" : s.direction === "SHORT" ? "text-red-600" : "text-gray-400"}`}>
                  {s.direction === "LONG" ? "↑ LONG" : s.direction === "SHORT" ? "↓ SHORT" : "● NEUTRAL"}
                </span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${zoneCfg.cls}`}>{zoneCfg.label}</span>
                {s.adx != null && <span className="text-xs text-gray-500">ADX {s.adx}</span>}
              </div>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none mt-1">✕</button>
          </div>
        </div>

        <div className="p-5 space-y-5">

          {/* Score */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Helper Prime Score</span>
              <span className="text-2xl font-bold text-gray-900">{s.score}<span className="text-sm text-gray-400">/100</span></span>
            </div>
            <div className="space-y-1.5">
              <div>
                <div className="flex justify-between text-xs text-gray-500 mb-0.5">
                  <span className="text-green-600 font-medium">↑ Long</span>
                  <span>{s.long_score}</span>
                </div>
                <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-2 bg-green-400 rounded-full" style={{ width: `${s.long_score}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs text-gray-500 mb-0.5">
                  <span className="text-red-500 font-medium">↓ Short</span>
                  <span>{s.short_score}</span>
                </div>
                <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-2 bg-red-400 rounded-full" style={{ width: `${s.short_score}%` }} />
                </div>
              </div>
            </div>
          </div>

          {/* Métricas */}
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Métricas</div>
            <div className="grid grid-cols-3 gap-2">
              {[
                ["RSI",       s.rsi?.toFixed(1),     s.rsi < 30 ? "text-blue-600" : s.rsi > 70 ? "text-red-600" : "text-gray-700"],
                ["vs MA200",  s.pct_vs_ma200 != null ? (s.pct_vs_ma200 >= 0 ? "+" : "") + s.pct_vs_ma200?.toFixed(2) + "%" : "—", s.pct_vs_ma200 >= 0 ? "text-green-600" : "text-red-600"],
                ["Vol ×",     s.vol_ratio != null ? s.vol_ratio?.toFixed(2) + "x" : "—", s.vol_ratio >= 1.5 ? "text-indigo-600 font-semibold" : "text-gray-700"],
                ["% Máx 52s", s.pct_from_high != null ? s.pct_from_high?.toFixed(2) + "%" : "—", s.pct_from_high >= 0 ? "text-green-600" : "text-red-600"],
                ["% Mín 52s", s.pct_from_low  != null ? "+" + s.pct_from_low?.toFixed(2) + "%" : "—", "text-green-700"],
                ["MACD",      s.macd_hist != null ? (s.macd_hist > 0 ? "▲" : "▼") + " " + Math.abs(s.macd_hist)?.toFixed(3) : "—", s.macd_hist > 0 ? "text-green-600" : "text-red-600"],
                ["Bollinger %B", s.pct_b != null ? (s.pct_b * 100).toFixed(0) + "%" : "—", s.pct_b < 0.2 ? "text-blue-600" : s.pct_b > 0.8 ? "text-red-600" : "text-gray-700"],
                ["Momentum",  s.mom != null ? (s.mom > 0 ? "+" : "") + s.mom : "—", s.mom > 0 ? "text-green-600" : s.mom < 0 ? "text-red-600" : "text-gray-400"],
                ["POC",       s.poc != null ? "$" + s.poc?.toFixed(2) : "—", "text-gray-700"],
              ].map(([label, val, cls]) => (
                <div key={label} className="bg-gray-50 rounded-lg p-2 text-center">
                  <div className="text-[10px] text-gray-400 mb-0.5">{label}</div>
                  <div className={`text-sm font-semibold tabular-nums ${cls}`}>{val ?? "—"}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Niveles SL / TP */}
          {(s.sl || s.tp1) && (
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Niveles de Riesgo</div>
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between items-center py-1 border-b border-gray-50">
                  <span className="text-gray-500">Entrada</span>
                  <span className="font-semibold tabular-nums">${s.price?.toFixed(2)}</span>
                </div>
                {s.sl && (
                  <div className="flex justify-between items-center py-1 border-b border-gray-50">
                    <span className="text-red-500 font-medium">Stop Loss</span>
                    <span className="tabular-nums">
                      <span className="font-semibold">${s.sl.toFixed(2)}</span>
                      {slPct && <span className="text-xs text-red-400 ml-1">({slPct}%)</span>}
                    </span>
                  </div>
                )}
                {s.tp1 && (
                  <div className="flex justify-between items-center py-1 border-b border-gray-50">
                    <span className="text-green-500 font-medium">TP1</span>
                    <span className="tabular-nums">
                      <span className="font-semibold">${s.tp1.toFixed(2)}</span>
                      {tp1Pct && <span className="text-xs text-green-400 ml-1">(+{tp1Pct}%)</span>}
                      {rrRatio && <span className="text-xs text-gray-400 ml-2">R/R 1:{rrRatio}</span>}
                    </span>
                  </div>
                )}
                {s.tp2 && (
                  <div className="flex justify-between items-center py-1">
                    <span className="text-green-600 font-medium">TP2</span>
                    <span className="tabular-nums">
                      <span className="font-semibold">${s.tp2.toFixed(2)}</span>
                      {tp2Pct && <span className="text-xs text-green-400 ml-1">(+{tp2Pct}%)</span>}
                      {rr2Ratio && <span className="text-xs text-gray-400 ml-2">R/R 1:{rr2Ratio}</span>}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Helper Pulse */}
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Helper Pulse</div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-700">{s.pulse_state ?? "—"}</span>
              {s.pulse_signal && (
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${pulseCfg}`}>
                  {s.pulse_signal}
                </span>
              )}
              {s.mom != null && (
                <span className={`text-xs ml-auto tabular-nums ${s.mom > 0 ? "text-green-600" : s.mom < 0 ? "text-red-600" : "text-gray-400"}`}>
                  mom {s.mom > 0 ? "+" : ""}{s.mom}
                </span>
              )}
            </div>
          </div>

          {/* Recomendación */}
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4">
            <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">Recomendación</div>
            <div className="space-y-1">
              {recommendation.map((line, i) => (
                <p key={i} className="text-sm text-indigo-900 leading-snug">{line}</p>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function HelpModal({ onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 overflow-y-auto max-h-[90vh]" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900">Cómo usar el Screener</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
        </div>

        <div className="space-y-5 text-sm text-gray-700">

          <section>
            <h3 className="font-semibold text-gray-900 mb-1">1. Elegí una lista</h3>
            <p>Seleccioná qué activos analizar: S&P 500, Nasdaq 100, ETFs, ADRs Argentina, o ingresá tus propios tickers. Luego presioná <strong>Analizar</strong>.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-2">2. Sistema de Score — Helper Prime</h3>
            <p className="mb-2">El Score (0-100) combina 7 componentes del sistema Helper Prime:</p>
            <div className="space-y-1 text-xs">
              {[
                ["EMA 200",    "15 pts", "Precio sobre EMA 200 = tendencia alcista principal"],
                ["Alineación", "15 pts", "EMA 20 > EMA 55 > EMA 200 = estructura alcista completa"],
                ["ADX + DI",   "15 pts", "ADX > 20 con DI+ > DI- confirma dirección con fuerza"],
                ["Momentum",   "15 pts", "RSI-50 positivo y creciendo = impulso alcista"],
                ["MTF proxy",  "15 pts", "4 señales de alineación temporal (approximado con EMAs diarias)"],
                ["Volatilidad","10 pts", "ATR por encima de su promedio 20 = volatilidad activa"],
                ["Zona",       "15 pts", "Precio en DISCOUNT, cerca de soporte, o POC de volumen"],
              ].map(([name, pts, desc]) => (
                <div key={name} className="flex gap-2 items-start">
                  <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 shrink-0">{pts}</span>
                  <div><span className="font-medium">{name}:</span> {desc}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 space-y-1">
              {[
                ["bg-emerald-500", "75-100 → Compra Fuerte", "Todos los componentes alineados. Alta convicción."],
                ["bg-green-400",   "60-74 → Compra",         "Mayoría de señales positivas."],
                ["bg-gray-300",    "40-59 → Neutral",         "Sin dirección clara. Esperar."],
                ["bg-orange-400",  "20-39 → Venta",           "Sesgo bajista, evitar comprar."],
                ["bg-red-500",     "0-19 → Venta Fuerte",     "Confluencia bajista total."],
              ].map(([color, label, desc]) => (
                <div key={label} className="flex gap-2 items-start">
                  <div className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${color}`} />
                  <div><span className="font-medium">{label}:</span> {desc}</div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-2">3. Helper Pulse — señales de divergencia</h3>
            <div className="space-y-1 text-xs">
              {[
                ["GIRO UP",    "text-cyan-700 bg-cyan-50",   "Divergencia alcista regular: precio baja, momentum sube (en zona de sobreventa). Señal de reversión."],
                ["SIGUE UP",   "text-yellow-700 bg-yellow-50", "Divergencia alcista oculta: precio sube, momentum cae. Continuación alcista en tendencia."],
                ["GIRO DN",    "text-red-700 bg-red-50",     "Divergencia bajista regular: precio sube, momentum baja (sobrecompra). Señal de reversión."],
                ["SIGUE DN",   "text-orange-700 bg-orange-50","Divergencia bajista oculta: precio baja, momentum sube. Continuación bajista en tendencia."],
                ["AGOT. SUP",  "text-pink-700 bg-pink-50",   "Agotamiento en zona alta: pivot de momentum en zona de potencia. Precaución en longs."],
                ["AGOT. INF",  "text-blue-700 bg-blue-50",   "Agotamiento en zona baja: pivot de momentum en zona de sobreventa. Posible rebote."],
              ].map(([label, cls, desc]) => (
                <div key={label} className="flex gap-2 items-start">
                  <span className={`font-mono px-1.5 py-0.5 rounded font-bold shrink-0 ${cls}`}>{label}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-2">4. Columnas clave</h3>
            <div className="space-y-1.5 text-xs">
              {[
                ["Zona",    "DISCOUNT = precio bajo la regresión lineal (zona de valor). FAIR = zona media. PREMIUM = zona extendida (cara)."],
                ["Dir",     "LONG = setup alcista, SHORT = setup bajista. El Score mide la fuerza de esa dirección."],
                ["SL / TP1","Stop Loss y Take Profit 1 calculados con ATR × 1.5 desde el precio actual."],
                ["ADX",     "Fuerza de la tendencia. Sobre 20 es condición mínima. Sobre 30 es tendencia fuerte."],
                ["Pulse",   "Última señal del oscilador de divergencias (Helper Pulse)."],
                ["RSI",     "Sobreventa (<30) o sobrecompra (>70)."],
                ["vs MA200","Qué tan lejos está del promedio de 200 días. Positivo = tendencia principal alcista."],
                ["Vol ×",   "Volumen de hoy vs promedio 20 días. 1.5x+ confirma movimiento."],
              ].map(([col, desc]) => (
                <div key={col} className="flex gap-2">
                  <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 shrink-0 self-start">{col}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-1">5. Flujo de trabajo recomendado</h3>
            <ol className="list-decimal list-inside space-y-1 text-gray-700">
              <li>Filtrá por <strong>Compra Fuerte</strong>.</li>
              <li>Verificá que <strong>Dir</strong> sea LONG y <strong>Zona</strong> sea DISCOUNT o FAIR.</li>
              <li>Confirmá <strong>ADX &gt; 25</strong> y <strong>vs MA200 positivo</strong>.</li>
              <li>Si el <strong>Pulse</strong> muestra GIRO UP o SIGUE UP → mayor confluencia.</li>
              <li>Revisá el <strong>SL/TP1</strong> para dimensionar tu riesgo antes de entrar.</li>
            </ol>
          </section>

          <section className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            <strong>Importante:</strong> Herramienta de filtrado técnico, no una recomendación financiera. Siempre realizá tu propio análisis antes de operar.
          </section>

        </div>
      </div>
    </div>
  );
}

const SIGNAL_CONFIG = {
  compra_fuerte: { label: "Compra Fuerte", color: "bg-emerald-100 text-emerald-800", bar: "bg-emerald-500" },
  compra:        { label: "Compra",        color: "bg-green-100 text-green-700",     bar: "bg-green-400" },
  neutral:       { label: "Neutral",       color: "bg-gray-100 text-gray-600",       bar: "bg-gray-300" },
  venta:         { label: "Venta",         color: "bg-orange-100 text-orange-700",   bar: "bg-orange-400" },
  venta_fuerte:  { label: "Venta Fuerte",  color: "bg-red-100 text-red-700",         bar: "bg-red-500" },
};

const FILTER_OPTIONS = [
  { key: "all",          label: "Todas" },
  { key: "compra_fuerte",label: "Compra Fuerte" },
  { key: "compra",       label: "Compra" },
  { key: "neutral",      label: "Neutral" },
  { key: "venta",        label: "Venta" },
  { key: "venta_fuerte", label: "Venta Fuerte" },
];

const LIST_CONFIG = [
  { id: "sp500",     label: "S&P 500" },
  { id: "nasdaq100", label: "Nasdaq 100" },
  { id: "etfs",      label: "ETFs" },
  { id: "adrs_arg",  label: "ADRs Argentina" },
  { id: "crypto",    label: "Crypto" },
  { id: "custom",    label: "Personalizada" },
];

const PULSE_CONFIG = {
  "GIRO UP":   { color: "bg-cyan-100 text-cyan-800",     title: "Divergencia alcista regular" },
  "SIGUE UP":  { color: "bg-yellow-100 text-yellow-800", title: "Continuación alcista (hidden)" },
  "GIRO DN":   { color: "bg-red-100 text-red-800",       title: "Divergencia bajista regular" },
  "SIGUE DN":  { color: "bg-orange-100 text-orange-800", title: "Continuación bajista (hidden)" },
  "AGOT. SUP": { color: "bg-pink-100 text-pink-800",     title: "Agotamiento superior" },
  "AGOT. INF": { color: "bg-blue-100 text-blue-800",     title: "Agotamiento inferior" },
};

function SignalBadge({ signal }) {
  const cfg = SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.neutral;
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function ScoreBar({ value, direction, signal }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const cfg = signal ? (SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.neutral) : SIGNAL_CONFIG.neutral;
  return (
    <div>
      <div className="flex items-center gap-2">
        <div className="w-14 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div className={`h-2 rounded-full ${cfg.bar}`} style={{ width: `${value}%` }} />
        </div>
        <span className="text-sm tabular-nums font-medium">{value}</span>
      </div>
      {direction && (
        <div className={`text-[10px] font-bold mt-0.5 ${
          direction === "LONG"  ? "text-green-600" :
          direction === "SHORT" ? "text-red-600"   : "text-gray-400"
        }`}>
          {direction === "LONG" ? "↑ LONG" : direction === "SHORT" ? "↓ SHORT" : "● NEUTRAL"}
        </div>
      )}
    </div>
  );
}

function RsiBar({ value }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const color = value < 30 ? "bg-blue-500" : value > 70 ? "bg-red-500" : "bg-gray-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-10 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-sm tabular-nums">{value}</span>
    </div>
  );
}

function PctCell({ value, invertColors = false }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const positive = invertColors ? value <= 0 : value >= 0;
  const sign = value >= 0 ? "+" : "";
  return (
    <span className={`tabular-nums font-medium ${positive ? "text-green-600" : "text-red-600"}`}>
      {sign}{value.toFixed(2)}%
    </span>
  );
}

function ZoneBadge({ zone }) {
  if (!zone) return <span className="text-gray-400">—</span>;
  const cfg = {
    discount: "bg-teal-100 text-teal-800",
    fair:     "bg-gray-100 text-gray-600",
    premium:  "bg-purple-100 text-purple-800",
  };
  const label = { discount: "DISCOUNT", fair: "FAIR", premium: "PREMIUM" };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${cfg[zone] ?? cfg.fair}`}>
      {label[zone] ?? zone.toUpperCase()}
    </span>
  );
}

function PulseBadge({ signal }) {
  if (!signal) return <span className="text-gray-400 text-xs">—</span>;
  const cfg = PULSE_CONFIG[signal];
  if (!cfg) return <span className="text-gray-500 text-xs">{signal}</span>;
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${cfg.color}`} title={cfg.title}>
      {signal}
    </span>
  );
}

function SlTpCell({ sl, tp1, direction }) {
  if (!sl || !tp1) return <span className="text-gray-400">—</span>;
  return (
    <div className="text-[10px] leading-tight tabular-nums">
      <div className="text-red-600 font-medium">SL {sl.toFixed(2)}</div>
      <div className="text-green-600 font-medium">TP {tp1.toFixed(2)}</div>
    </div>
  );
}

function SummaryCard({ signal, count, active, onClick }) {
  const cfg = SIGNAL_CONFIG[signal];
  return (
    <button
      onClick={onClick}
      className={`p-3 rounded-xl border text-left transition bg-white hover:shadow-sm ${active ? "ring-2 ring-indigo-500" : ""}`}
    >
      <div className="text-xl font-bold text-gray-900">{count}</div>
      <div className={`text-xs font-semibold mt-0.5 ${cfg.color.split(" ")[1]}`}>{cfg.label}</div>
    </button>
  );
}

export default function App() {
  const [stocks, setStocks] = useState([]);
  const [status, setStatus] = useState("idle");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [signalFilter, setSignalFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState("score");
  const [sortDir, setSortDir] = useState("desc");
  const [processed, setProcessed] = useState(0);
  const [totalTickers, setTotalTickers] = useState(0);
  const [selectedList, setSelectedList] = useState("sp500");
  const [customInput, setCustomInput] = useState("");
  const [cryptoLimit, setCryptoLimit] = useState(20);
  const [activeListId, setActiveListId] = useState("sp500");
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  const fetchStocks = useCallback(async () => {
    try {
      const res = await fetch(`/api/stocks?signal=${signalFilter}`);
      const data = await res.json();
      setStocks(data.stocks ?? []);
      setStatus(data.status);
      setLastUpdated(data.last_updated);
    } catch { }
  }, [signalFilter]);

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      setStatus(data.status);
      setProcessed(data.processed ?? 0);
      setTotalTickers(data.total_tickers ?? 0);
      if (data.status === "ready") fetchStocks();
    } catch { }
  }, [fetchStocks]);

  useEffect(() => { checkStatus(); }, [checkStatus]);

  useEffect(() => {
    if (status !== "loading" && status !== "downloading") return;
    const interval = setInterval(() => {
      checkStatus();
      if (status === "loading") fetchStocks();
    }, 3000);
    return () => clearInterval(interval);
  }, [status, checkStatus, fetchStocks]);

  useEffect(() => {
    if (status === "ready") fetchStocks();
  }, [signalFilter, status, fetchStocks]);

  const handleRefresh = async () => {
    setLoading(true);
    const custom = selectedList === "custom"
      ? customInput.split(/[\s,]+/).filter(Boolean)
      : [];
    await fetch("/api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ list_id: selectedList, custom, crypto_limit: cryptoLimit }),
    });
    setActiveListId(selectedList);
    setStocks([]);
    setStatus("downloading");
    setLoading(false);
  };

  const handleSort = (key) => {
    if (sortKey === key) setSortDir((d) => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("desc"); }
  };

  const filtered = stocks
    .filter((s) => s.ticker.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const va = a[sortKey] ?? -Infinity;
      const vb = b[sortKey] ?? -Infinity;
      if (typeof va === "string") return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      return sortDir === "asc" ? va - vb : vb - va;
    });

  const isBusy = status === "loading" || status === "downloading";

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>;
  };

  const th = (label, col) => (
    <th
      className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"
      onClick={() => handleSort(col)}
    >
      {label}<SortIcon col={col} />
    </th>
  );

  const thStatic = (label) => (
    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
      {label}
    </th>
  );

  const activeListLabel = LIST_CONFIG.find(l => l.id === activeListId)?.label ?? "";

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-screen-2xl mx-auto">

        {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}
        {selectedTicker && <TickerModal stock={selectedTicker} onClose={() => setSelectedTicker(null)} />}

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Stock Screener</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {lastUpdated
                ? `${activeListLabel} · Actualizado: ${new Date(lastUpdated * 1000).toLocaleString("es-AR")}`
                : "Seleccioná una lista y presioná Analizar"}
            </p>
          </div>
          <button
            onClick={() => setShowHelp(true)}
            className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-300 rounded-lg hover:bg-indigo-50 transition"
          >
            ? Cómo usar
          </button>
        </div>

        {/* Selector de lista + botón */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <div className="flex flex-wrap items-center gap-2">
            {LIST_CONFIG.map((l) => (
              <button
                key={l.id}
                onClick={() => setSelectedList(l.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  selectedList === l.id
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {l.label}
              </button>
            ))}
            <button
              onClick={handleRefresh}
              disabled={loading || isBusy || (selectedList === "custom" && !customInput.trim())}
              className="ml-auto px-5 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {isBusy ? "Analizando…" : `Analizar ${LIST_CONFIG.find(l => l.id === selectedList)?.label ?? ""}`}
            </button>
          </div>
          {selectedList === "crypto" && (
            <div className="mt-3 flex items-center gap-4">
              <span className="text-sm text-gray-600 shrink-0">Top</span>
              <input
                type="range"
                min={10} max={100} step={10}
                value={cryptoLimit}
                onChange={(e) => setCryptoLimit(Number(e.target.value))}
                className="flex-1 accent-indigo-600"
              />
              <span className="text-sm font-semibold text-indigo-700 w-12 text-right">
                {cryptoLimit} cripto{cryptoLimit > 1 ? "s" : ""}
              </span>
            </div>
          )}
          {selectedList === "custom" && (
            <textarea
              rows={2}
              placeholder="Escribí los tickers separados por coma o espacio. Ej: AAPL, MSFT, TSLA"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              className="w-full mt-3 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
            />
          )}
        </div>

        {/* Loading banner */}
        {isBusy && (
          <div className="mb-4 p-4 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-700">
            <div className="flex items-center gap-2 mb-2">
              <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>
                {status === "downloading"
                  ? "Descargando datos de Yahoo Finance…"
                  : `Calculando indicadores… ${processed} / ${totalTickers}`}
              </span>
            </div>
            <div className="w-full bg-indigo-100 rounded-full h-2 overflow-hidden">
              {status === "downloading" ? (
                <div className="h-2 bg-indigo-400 rounded-full animate-pulse w-full" />
              ) : (
                <div
                  className="bg-indigo-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${totalTickers > 0 ? Math.round((processed / totalTickers) * 100) : 0}%` }}
                />
              )}
            </div>
            <p className="text-xs text-indigo-500 mt-1 text-right">
              {status === "downloading" ? "Conectando…" : `${Math.round((processed / totalTickers) * 100)}%`}
            </p>
          </div>
        )}

        {/* Resumen por señal */}
        {stocks.length > 0 && (
          <div className="grid grid-cols-5 gap-3 mb-6">
            {Object.keys(SIGNAL_CONFIG).map((key) => (
              <SummaryCard
                key={key}
                signal={key}
                count={stocks.filter(s => s.signal === key).length}
                active={signalFilter === key}
                onClick={() => setSignalFilter(signalFilter === key ? "all" : key)}
              />
            ))}
          </div>
        )}

        {/* Filtros */}
        <div className="flex flex-wrap gap-3 mb-4">
          <input
            type="text"
            placeholder="Buscar ticker…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 w-40"
          />
          <div className="flex flex-wrap gap-1">
            {FILTER_OPTIONS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setSignalFilter(key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  signalFilter === key
                    ? "bg-indigo-600 text-white"
                    : "bg-white border border-gray-300 text-gray-600 hover:bg-gray-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Tabla */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {filtered.length === 0 && !isBusy ? (
            <div className="p-12 text-center text-gray-400">
              {stocks.length === 0
                ? "Seleccioná una lista y presioná Analizar."
                : "Sin resultados para este filtro."}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {th("Ticker",    "ticker")}
                    {th("Precio",    "price")}
                    {th("Score",     "score")}
                    {thStatic("Zona")}
                    {th("RSI",       "rsi")}
                    {th("ADX",       "adx")}
                    {th("vs MA200",  "pct_vs_ma200")}
                    {th("Vol ×",     "vol_ratio")}
                    {th("% Máx 52s", "pct_from_high")}
                    {th("% Mín 52s", "pct_from_low")}
                    {th("MACD",      "macd_hist")}
                    {thStatic("Pulse")}
                    {thStatic("SL / TP1")}
                    {thStatic("Señal")}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((s) => (
                    <tr
                      key={s.ticker}
                      className="hover:bg-indigo-50 transition cursor-pointer"
                      onClick={() => setSelectedTicker(s)}
                    >
                      <td className="px-3 py-3 font-semibold text-gray-900 underline decoration-dotted underline-offset-2">{s.ticker}</td>
                      <td className="px-3 py-3 tabular-nums">${s.price.toFixed(2)}</td>
                      <td className="px-3 py-3">
                        <ScoreBar value={s.score} direction={s.direction} signal={s.signal} />
                      </td>
                      <td className="px-3 py-3"><ZoneBadge zone={s.zone} /></td>
                      <td className="px-3 py-3"><RsiBar value={s.rsi} /></td>
                      <td className="px-3 py-3 tabular-nums text-xs">
                        {s.adx != null
                          ? <span className={s.adx >= 25 ? "font-semibold text-indigo-700" : "text-gray-600"}>
                              {s.adx.toFixed(1)}
                            </span>
                          : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-3 py-3"><PctCell value={s.pct_vs_ma200} /></td>
                      <td className="px-3 py-3 tabular-nums">
                        {s.vol_ratio != null
                          ? <span className={s.vol_ratio >= 1.5 ? "font-semibold text-indigo-600" : "text-gray-700"}>
                              {s.vol_ratio.toFixed(2)}x
                            </span>
                          : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-3 py-3"><PctCell value={s.pct_from_high} /></td>
                      <td className="px-3 py-3"><PctCell value={s.pct_from_low} /></td>
                      <td className="px-3 py-3 tabular-nums">
                        {s.macd_hist != null
                          ? <span className={s.macd_hist > 0 ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
                              {s.macd_hist > 0 ? "▲" : "▼"} {Math.abs(s.macd_hist).toFixed(3)}
                            </span>
                          : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-3 py-3"><PulseBadge signal={s.pulse_signal} /></td>
                      <td className="px-3 py-3">
                        <SlTpCell sl={s.sl} tp1={s.tp1} direction={s.direction} />
                      </td>
                      <td className="px-3 py-3"><SignalBadge signal={s.signal} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-3 text-right">
          {filtered.length} activos · Score = Helper Prime (EMA + ADX + Momentum + MTF + Zona) · Pulse = Helper Pulse (divergencias RSI)
        </p>
      </div>
    </div>
  );
}

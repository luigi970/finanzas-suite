import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

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

function toTvSymbol(ticker) {
  if (ticker.endsWith("-USD")) return ticker.slice(0, -4) + "USDT";
  return ticker;
}

function displayTicker(ticker) {
  return ticker.endsWith("-USD") ? ticker.slice(0, -4) : ticker;
}

const ANIM_DELAY = 280; // ms — wait for slideUp animation to finish before injecting iframes

function TradingViewChart({ ticker }) {
  const containerRef = useRef(null);
  const symbol = toTvSymbol(ticker);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.innerHTML = "";
    const tid = setTimeout(() => {
      const wrap = document.createElement("div");
      wrap.className = "tradingview-widget-container";
      wrap.style.cssText = "width:100%;height:100%";
      const inner = document.createElement("div");
      inner.className = "tradingview-widget-container__widget";
      inner.style.cssText = "width:100%;height:100%";
      const script = document.createElement("script");
      script.src = "https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js";
      script.async = true;
      script.innerHTML = JSON.stringify({
        symbol, width: "100%", height: "100%", locale: "es",
        dateRange: "3M", colorTheme: "light",
        trendLineColor: "rgba(99,102,241,1)",
        underLineColor: "rgba(99,102,241,0.1)",
        isTransparent: true, autosize: true,
      });
      wrap.appendChild(inner);
      wrap.appendChild(script);
      el.appendChild(wrap);
    }, ANIM_DELAY);
    return () => { clearTimeout(tid); el.innerHTML = ""; };
  }, [symbol]);

  return <div ref={containerRef} className="w-full" style={{ height: 200 }} />;
}

function TradingViewEmbed({ ticker, widgetSrc, config }) {
  const containerRef = useRef(null);
  const symbol = toTvSymbol(ticker);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.innerHTML = "";
    const tid = setTimeout(() => {
      const wrap = document.createElement("div");
      wrap.className = "tradingview-widget-container";
      wrap.style.cssText = "width:100%;height:100%";
      const inner = document.createElement("div");
      inner.className = "tradingview-widget-container__widget";
      inner.style.cssText = "width:100%;height:100%";
      const script = document.createElement("script");
      script.src = widgetSrc;
      script.async = true;
      script.innerHTML = JSON.stringify({ symbol, locale: "es", colorTheme: "light", width: "100%", height: "100%", ...config });
      wrap.appendChild(inner);
      wrap.appendChild(script);
      el.appendChild(wrap);
    }, ANIM_DELAY);
    return () => { clearTimeout(tid); el.innerHTML = ""; };
  }, [symbol, widgetSrc]);

  return <div ref={containerRef} className="w-full h-full" />;
}

const TV_BASE = "https://s3.tradingview.com/external-embedding";

function Tooltip({ text, content, children }) {
  const [pos, setPos] = useState(null);
  const ref = useRef(null);

  const show = () => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const x = Math.max(120, Math.min(window.innerWidth - 120, r.left + r.width / 2));
    setPos({ x, y: r.top + window.scrollY });
  };

  const body = content ?? text;

  return (
    <>
      <span ref={ref} onMouseEnter={show} onMouseLeave={() => setPos(null)} className="inline-block">
        {children}
      </span>
      {pos && createPortal(
        <div className="absolute z-[9999] pointer-events-none"
          style={{ left: pos.x, top: pos.y - 10, transform: "translate(-50%, -100%)" }}>
          <div className="bg-gray-900 text-white text-[11px] rounded-xl px-3 py-2.5 leading-relaxed shadow-2xl max-w-[260px] whitespace-normal text-left">
            {body}
          </div>
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-[5px] border-transparent border-t-gray-900" />
        </div>,
        document.body
      )}
    </>
  );
}

function BottomSheet({ onClose, children, className = "" }) {
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end" onClick={onClose}>
      <div
        className={`w-full bg-slate-50 rounded-t-2xl shadow-2xl flex flex-col ${className}`}
        style={{ animation: "slideUp 0.25s ease-out both" }}
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}


function NewsFeed({ ticker }) {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const symbol = ticker.endsWith("-USD") ? ticker.replace("-USD", "-USD") : ticker;

  useEffect(() => {
    setLoading(true);
    setNews([]);
    fetch(`${API_BASE}/api/news?ticker=${symbol}`)
      .then(r => r.json())
      .then(d => { setNews(d.news || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [symbol]);

  if (loading) return <div className="flex items-center justify-center h-full text-gray-400 text-sm">Cargando noticias...</div>;
  if (!news.length) return <div className="flex items-center justify-center h-full text-gray-400 text-sm">Sin noticias disponibles.</div>;

  return (
    <div className="h-full overflow-y-auto space-y-3 pr-1">
      {news.map((n, i) => (
        <a key={i} href={n.link} target="_blank" rel="noreferrer"
          className="flex gap-3 p-3 rounded-xl border border-gray-100 hover:border-amber-200 hover:bg-amber-50 transition group">
          {n.thumbnail && (
            <img src={n.thumbnail} alt="" className="w-20 h-16 object-cover rounded-lg shrink-0" onError={e => e.target.style.display="none"} />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 group-hover:text-amber-700 line-clamp-2 leading-snug">{n.title}</p>
            {n.summary && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{n.summary}</p>}
            <div className="flex items-center gap-2 mt-1.5">
              {n.publisher && <span className="text-xs text-gray-400 font-medium">{n.publisher}</span>}
              {n.time && <span className="text-xs text-gray-300">{new Date(n.time).toLocaleDateString("es-AR", { day:"2-digit", month:"short", year:"numeric" })}</span>}
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}

function HistoryTab({ ticker, listId }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/history?list_id=${listId}&ticker=${ticker}`)
      .then(r => r.json())
      .then(d => { setHistory(d.history || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [ticker, listId]);

  const SIG = {
    compra_fuerte: { label: "C.Fuerte", cls: "bg-emerald-100 text-emerald-800" },
    compra:        { label: "Compra",   cls: "bg-green-100 text-green-700" },
    neutral:       { label: "Neutral",  cls: "bg-gray-100 text-gray-500" },
    venta:         { label: "Venta",    cls: "bg-orange-100 text-orange-700" },
    venta_fuerte:  { label: "V.Fuerte", cls: "bg-red-100 text-red-700" },
  };

  const pctCell = (v) => {
    if (v == null) return <span className="text-gray-300">—</span>;
    const pos = v >= 0;
    return (
      <span className={`font-semibold tabular-nums ${pos ? "text-green-600" : "text-red-600"}`}>
        {pos ? "+" : ""}{v.toFixed(1)}%
      </span>
    );
  };

  if (loading) return <div className="flex items-center justify-center h-full text-gray-400 text-sm">Cargando historial…</div>;
  if (!history.length) return (
    <div className="flex flex-col items-center justify-center h-full text-center gap-2 px-6">
      <div className="text-2xl">📊</div>
      <div className="text-gray-500 text-sm font-medium">Sin historial todavía</div>
      <div className="text-gray-400 text-xs">Los datos se acumulan con cada run del screener. Volvé en unos días para ver el rendimiento de las señales.</div>
    </div>
  );

  // Stats summary per signal
  const stats = {};
  for (const h of history) {
    if (!stats[h.signal]) stats[h.signal] = { n: 0, s5: [], s10: [], s20: [] };
    stats[h.signal].n++;
    if (h.pct_5d  != null) stats[h.signal].s5.push(h.pct_5d);
    if (h.pct_10d != null) stats[h.signal].s10.push(h.pct_10d);
    if (h.pct_20d != null) stats[h.signal].s20.push(h.pct_20d);
  }
  const avg = (arr) => arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1) : null;

  return (
    <div className="h-full overflow-y-auto flex flex-col gap-4">
      {/* Summary */}
      {Object.keys(stats).length > 0 && (
        <div className="shrink-0">
          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-1 mb-1.5">Rendimiento promedio por señal</div>
          <div className="space-y-1">
            {Object.entries(stats).map(([sig, s]) => {
              const cfg = SIG[sig] ?? { label: sig, cls: "bg-gray-100 text-gray-500" };
              return (
                <div key={sig} className="flex items-center gap-2 text-xs">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold w-16 text-center shrink-0 ${cfg.cls}`}>{cfg.label}</span>
                  <span className="text-gray-400 w-8 shrink-0">{s.n}x</span>
                  <div className="flex gap-3">
                    {[["5d", avg(s.s5)], ["10d", avg(s.s10)], ["20d", avg(s.s20)]].map(([label, v]) => (
                      <div key={label} className="flex items-center gap-0.5">
                        <span className="text-gray-300">{label}:</span>
                        {v != null
                          ? <span className={`font-semibold ${Number(v) >= 0 ? "text-green-600" : "text-red-600"}`}>{Number(v) >= 0 ? "+" : ""}{v}%</span>
                          : <span className="text-gray-300">—</span>}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* History table */}
      <div className="flex-1 min-h-0">
        <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-1 mb-1.5">Detalle</div>
        <table className="w-full text-xs">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="px-2 py-2 text-left text-gray-500 font-semibold">Fecha</th>
              <th className="px-2 py-2 text-left text-gray-500 font-semibold">Señal</th>
              <th className="px-2 py-2 text-right text-gray-500 font-semibold">Precio</th>
              <th className="px-2 py-2 text-right text-gray-500 font-semibold">+5d</th>
              <th className="px-2 py-2 text-right text-gray-500 font-semibold">+10d</th>
              <th className="px-2 py-2 text-right text-gray-500 font-semibold">+20d</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {history.map((h, i) => {
              const cfg = SIG[h.signal] ?? { label: h.signal, cls: "bg-gray-100 text-gray-500" };
              return (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-2 py-2 text-gray-500 tabular-nums">{h.recorded_at}</td>
                  <td className="px-2 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${cfg.cls}`}>{cfg.label}</span>
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums text-gray-700">${h.price.toFixed(2)}</td>
                  <td className="px-2 py-2 text-right">{pctCell(h.pct_5d)}</td>
                  <td className="px-2 py-2 text-right">{pctCell(h.pct_10d)}</td>
                  <td className="px-2 py-2 text-right">{pctCell(h.pct_20d)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnalysisModal({ ticker, listId, onClose }) {
  const [tab, setTab] = useState("tecnico");
  const tvSymbol = toTvSymbol(ticker);
  const tabs = [
    { id: "tecnico",   label: "Técnico" },
    { id: "empresa",   label: "Empresa" },
    { id: "noticias",  label: "Noticias" },
    { id: "historial", label: "Historial" },
  ];

  return (
    <BottomSheet onClose={onClose} className="h-[88vh]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <span className="font-semibold text-gray-800 shrink-0">{ticker.endsWith("-USD") ? ticker.replace("-USD","") : ticker}</span>
          <div className="flex gap-1">
            {tabs.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`text-xs px-3 py-1 rounded-full font-medium transition ${tab === t.id ? "bg-amber-500 text-white" : "text-gray-500 hover:bg-gray-100"}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-2">
          <a href={`https://www.tradingview.com/symbols/${tvSymbol}/`} target="_blank" rel="noreferrer" className="text-xs text-amber-500 hover:underline hidden sm:inline">TradingView ↗</a>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
        </div>
      </div>
      <div className="flex-1 overflow-hidden p-3">
        {tab === "tecnico" && (
          <TradingViewEmbed ticker={ticker}
            widgetSrc={`${TV_BASE}/embed-widget-technical-analysis.js`}
            config={{ interval: "1D", showIntervalTabs: true }} />
        )}
        {tab === "empresa" && (
          <TradingViewEmbed ticker={ticker}
            widgetSrc={`${TV_BASE}/embed-widget-financials.js`}
            config={{ displayMode: "compact" }} />
        )}
        {tab === "noticias" && (
          <NewsFeed ticker={ticker} />
        )}
        {tab === "historial" && (
          <HistoryTab ticker={ticker} listId={listId} />
        )}
      </div>
    </BottomSheet>
  );
}

function TradingViewFullChart({ ticker }) {
  const containerRef = useRef(null);
  const symbol = toTvSymbol(ticker);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.innerHTML = "";
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = () => {
      if (window.TradingView) {
        new window.TradingView.widget({
          container_id: el.id,
          symbol,
          interval: "D",
          timezone: "America/Argentina/Buenos_Aires",
          theme: "light",
          style: "1",
          locale: "es",
          width: "100%",
          height: "100%",
          hide_side_toolbar: false,
          allow_symbol_change: true,
          save_image: false,
        });
      }
    };
    el.appendChild(script);
    return () => { el.innerHTML = ""; };
  }, [symbol]);

  return <div id={`tv-full-${ticker}`} ref={containerRef} className="w-full h-full" />;
}

function ChartModal({ ticker, onClose }) {
  return (
    <BottomSheet onClose={onClose} className="h-[85vh]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
        <span className="font-semibold text-gray-800">{ticker.endsWith("-USD") ? ticker.replace("-USD", "") : ticker} — Gráfico</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
      </div>
      <div className="flex-1 overflow-hidden">
        <TradingViewFullChart ticker={ticker} />
      </div>
    </BottomSheet>
  );
}

function AIModal({ stock: s, onClose }) {
  const [rec, setRec]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setRec(null);
    setLoading(true);
    fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s),
    })
      .then(r => r.json())
      .then(d => setRec(d.recommendation ?? d.error ?? "Sin respuesta"))
      .catch(() => setRec("Error al conectar con la IA"))
      .finally(() => setLoading(false));
  }, [s]);

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden"
        style={{ animation: "slideUp 0.2s ease-out both" }}
        onClick={e => e.stopPropagation()}
      >
        <div className="bg-slate-900 px-5 py-4 flex items-center justify-between" style={{ borderTop: "3px solid #f59e0b" }}>
          <div className="flex items-center gap-2.5">
            <span className="text-amber-400 text-lg">✦</span>
            <div>
              <div className="text-white font-bold text-base leading-tight">{s.ticker}</div>
              <div className="text-slate-400 text-xs">Análisis IA</div>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl leading-none">✕</button>
        </div>
        <div className="p-5 min-h-[120px] flex items-start">
          {loading ? (
            <div className="flex items-center gap-2 text-amber-500 text-sm">
              <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
              Generando análisis…
            </div>
          ) : (
            <p className="text-sm text-gray-800 leading-relaxed">{rec}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function TickerModal({ stock: s, listId, onClose }) {
  const [info, setInfo] = useState(null);
  const [showChart, setShowChart] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [pivotType, setPivotType] = useState("classic");

  useEffect(() => {
    if (!s) return;
    setInfo(null);
    fetch(`${API_BASE}/api/info?ticker=${s.ticker}`)
      .then(r => r.json())
      .then(d => { if (Object.keys(d.info || {}).length) setInfo(d.info); })
      .catch(() => {});
  }, [s]);

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

  return (
    <>
      <BottomSheet onClose={onClose} className="max-h-[92vh]">
        <div className="overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="p-4 sm:p-5 bg-slate-900 rounded-t-2xl shrink-0" style={{ borderTop: "3px solid #f59e0b" }}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-xl sm:text-2xl font-bold text-white">{displayTicker(s.ticker)}</h2>
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold text-white ${sigCfg.color}`}>
                  {sigCfg.label}
                </span>
              </div>
              <div className="text-lg sm:text-xl font-semibold text-slate-200">${s.price?.toFixed(2)}</div>
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                <span className={`text-xs font-bold ${s.direction === "LONG" ? "text-green-400" : s.direction === "SHORT" ? "text-red-400" : "text-slate-400"}`}>
                  {s.direction === "LONG" ? "↑ LONG" : s.direction === "SHORT" ? "↓ SHORT" : "● NEUTRAL"}
                </span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${zoneCfg.cls}`}>{zoneCfg.label}</span>
                {s.adx != null && <span className="text-xs text-slate-400">ADX {s.adx}</span>}
                {s.candle_pattern && <CandlePatternBadge pattern={s.candle_pattern} />}
                {info?.earnings_date && (() => {
                  const days = Math.round((new Date(info.earnings_date) - new Date()) / 86400000);
                  const urgent = days >= 0 && days <= 14;
                  const passed = days < 0;
                  return (
                    <Tooltip text={
                      passed ? `Earnings: ${info.earnings_date} (ya reportó)` :
                      urgent ? `⚠️ Earnings en ${days} días (${info.earnings_date}). El precio puede moverse mucho en esa fecha.` :
                      `Próximos earnings: ${info.earnings_date} (en ${days} días)`
                    }>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${urgent ? "bg-orange-100 text-orange-700" : passed ? "bg-gray-100 text-gray-400" : "bg-blue-50 text-blue-700"}`}>
                        📅 {urgent ? `Earnings ${days}d` : info.earnings_date}
                      </span>
                    </Tooltip>
                  );
                })()}
              </div>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-white text-xl leading-none mt-1">✕</button>
          </div>
        </div>

        <div className="px-2 pt-2 shrink-0">
          <div className="relative group">
            <TradingViewChart ticker={s.ticker} />
            <div className="absolute inset-0 z-10 cursor-pointer" onClick={() => setShowChart(true)} />
            <div className="absolute inset-0 z-20 flex items-end justify-end pb-2 pr-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <span className="bg-amber-500 text-white text-xs px-2 py-1 rounded-lg shadow">Ver gráfico ↗</span>
            </div>
          </div>
          <div className="flex gap-2 mt-2">
            <button onClick={() => setShowChart(true)} className="flex-1 text-xs py-1.5 rounded-lg border border-amber-200 text-amber-600 hover:bg-amber-50 transition font-medium">
              Gráfico completo
            </button>
            <button
              onClick={() => setShowAnalysis(true)}
              className="flex-1 text-xs py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition font-medium"
            >
              Análisis técnico
            </button>
            <a
              href={`https://www.tradingview.com/chart/?symbol=${toTvSymbol(s.ticker)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-xs py-1.5 rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50 transition font-medium text-center"
            >
              TradingView ↗
            </a>
          </div>
        </div>

        <div className="p-4 sm:p-5 space-y-4 sm:space-y-5">

          {/* Score */}
          <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <Tooltip text="Puntuación 0-100 que combina 7 componentes técnicos. Long Score mide la fuerza alcista, Short Score la bajista. El Score final es el mayor de los dos. ≥75 = señal fuerte, ≥60 = señal moderada, <60 = esperar.">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider underline decoration-dotted underline-offset-2 cursor-help">Score</span>
              </Tooltip>
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
          <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Métricas</div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: "RSI",          val: s.rsi?.toFixed(1),     cls: s.rsi < 30 ? "text-blue-600" : s.rsi > 70 ? "text-red-600" : "text-gray-700",                                   tip: "RSI: <30 zona de sobreventa (posible rebote). >70 sobrecompra (posible corrección). 30-70 zona neutra. El Score usa RSI-50 como referencia de momentum." },
                { label: "vs MA200",     val: s.pct_vs_ma200 != null ? (s.pct_vs_ma200 >= 0 ? "+" : "") + s.pct_vs_ma200?.toFixed(2) + "%" : "—", cls: s.pct_vs_ma200 >= 0 ? "text-green-600" : "text-red-600", tip: "Distancia al promedio de 200 días. Positivo = precio sobre la MA200 (tendencia alcista principal). El Score suma 15 pts si el precio está por encima." },
                { label: "Vol ×",        val: s.vol_ratio != null ? s.vol_ratio?.toFixed(2) + "x" : "—",                               cls: s.vol_ratio >= 1.5 ? "text-amber-600 font-semibold" : "text-gray-700",                                                                        tip: "Volumen actual vs promedio de 20 días. >1.5x = movimiento confirmado. >2x = fuerte participación. <1x = movimiento sin respaldo — mayor riesgo de fakeout." },
                { label: "% Máx 52s",   val: s.pct_from_high != null ? s.pct_from_high?.toFixed(2) + "%" : "—",                        cls: s.pct_from_high >= 0 ? "text-green-600" : "text-red-600",                                                                                   tip: "Distancia al máximo de las 52 semanas. Cerca de 0% = en zona de máximos, momentum fuerte pero poco recorrido. Muy negativo = amplio potencial si recupera tendencia." },
                { label: "% Mín 52s",   val: s.pct_from_low  != null ? "+" + s.pct_from_low?.toFixed(2) + "%" : "—",                  cls: "text-green-700",                                                                                                                             tip: "Distancia al mínimo de las 52 semanas. Bajo = precio cerca del soporte anual. Alto = fuerte recuperación desde mínimos." },
                { label: "MACD",         val: s.macd_hist != null ? (s.macd_hist > 0 ? "▲" : "▼") + " " + Math.abs(s.macd_hist)?.toFixed(3) : "—", cls: s.macd_hist > 0 ? "text-green-600" : "text-red-600",                                                                           tip: "Histograma MACD. ▲ positivo = momentum alcista activo. ▼ negativo = momentum bajista. Cuanto mayor el valor absoluto, más fuerte el impulso." },
                { label: "Bollinger %B", val: s.pct_b != null ? (s.pct_b * 100).toFixed(0) + "%" : "—",                               cls: s.pct_b < 0.2 ? "text-blue-600" : s.pct_b > 0.8 ? "text-red-600" : "text-gray-700",                                                         tip: "Posición dentro de las Bandas de Bollinger. <20% = cerca de la banda inferior (sobreventa). >80% = cerca de la banda superior (sobrecompra). 50% = centro." },
                { label: "Momentum",     val: s.mom != null ? (s.mom > 0 ? "+" : "") + s.mom : "—",                                    cls: s.mom > 0 ? "text-green-600" : s.mom < 0 ? "text-red-600" : "text-gray-400",                                                                  tip: "Oscilador de momentum (EMA del RSI-50). Positivo = momentum alcista. Negativo = bajista. Usado para detectar divergencias." },
                { label: "ADX",          val: s.adx?.toFixed(1),                                                                        cls: s.adx >= 25 ? "text-amber-700 font-semibold" : "text-gray-700",                                                                               tip: "ADX: mide la fuerza de la tendencia sin importar dirección. <20 = lateral o tendencia débil. 20-25 = tendencia moderada. >25 = tendencia fuerte. >30 = muy fuerte." },
                { label: "POC",          val: s.poc != null ? "$" + s.poc?.toFixed(2) : "—",                                           cls: "text-gray-700",                                                                                                                              tip: "Point of Control: precio con mayor volumen acumulado (últimas 70 velas, 15 buckets). El precio tiende a gravitar hacia el POC. Útil como nivel de soporte/resistencia y objetivo." },
              ].map(({ label, val, cls, tip }) => (
                <Tooltip key={label} text={tip}>
                  <div className="bg-gray-50 rounded-lg p-2 text-center cursor-help">
                    <div className="text-[10px] text-gray-400 mb-0.5">{label}</div>
                    <div className={`text-sm font-semibold tabular-nums ${cls}`}>{val ?? "—"}</div>
                  </div>
                </Tooltip>
              ))}
            </div>
          </div>

          {/* Desktop: 2 columnas | Mobile: una sola columna */}
          <div className="sm:grid sm:grid-cols-2 sm:gap-5 space-y-4 sm:space-y-0">

            {/* Columna izquierda: Niveles de Riesgo + Helper Pulse */}
            <div className="space-y-4">

              {/* Niveles SL / TP */}
              {(s.sl || s.tp1) && (
                <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
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


            </div>{/* fin col izquierda */}

            {/* Columna derecha: Analistas + Medias Móviles + Pivots */}
            <div className="space-y-4">

              {/* Analyst ratings */}
              {info && (info.recommendation_key || info.target_price) && (() => {
                const REC = {
                  strong_buy:   { label: "Compra Fuerte", cls: "bg-emerald-100 text-emerald-800" },
                  buy:          { label: "Compra",        cls: "bg-green-100 text-green-700" },
                  hold:         { label: "Mantener",      cls: "bg-yellow-100 text-yellow-700" },
                  underperform: { label: "Subperformance",cls: "bg-orange-100 text-orange-700" },
                  sell:         { label: "Venta",         cls: "bg-red-100 text-red-700" },
                };
                const rec = REC[info.recommendation_key] ?? { label: info.recommendation_key, cls: "bg-gray-100 text-gray-600" };
                const upside = info.target_price && s.price
                  ? ((info.target_price - s.price) / s.price * 100).toFixed(1)
                  : null;
                return (
                  <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
                    <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Analistas</div>
                    <div className="flex flex-wrap items-center gap-3">
                      {info.recommendation_key && (
                        <Tooltip text={`Consenso de ${info.analyst_count ?? "?"} analistas. Escala: Compra Fuerte → Compra → Mantener → Subperformance → Venta.`}>
                          <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${rec.cls}`}>{rec.label}</span>
                        </Tooltip>
                      )}
                      {info.analyst_count && (
                        <span className="text-xs text-gray-400">{info.analyst_count} analistas</span>
                      )}
                      {info.target_price && (
                        <Tooltip text={`Precio objetivo promedio: $${info.target_price.toFixed(2)}. Rango: $${info.target_low?.toFixed(2) ?? "?"} – $${info.target_high?.toFixed(2) ?? "?"}. Basado en el consenso de analistas.`}>
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs text-gray-500">Target</span>
                            <span className="text-sm font-semibold tabular-nums">${info.target_price.toFixed(2)}</span>
                            {upside && (
                              <span className={`text-xs font-bold ${Number(upside) >= 0 ? "text-green-600" : "text-red-500"}`}>
                                {Number(upside) >= 0 ? "+" : ""}{upside}%
                              </span>
                            )}
                          </div>
                        </Tooltip>
                      )}
                      {info.target_low && info.target_high && (
                        <span className="text-[10px] text-gray-400 tabular-nums">
                          ${info.target_low.toFixed(2)} – ${info.target_high.toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* Medias Móviles */}
              {[s.ma5, s.ma10, s.ma20, s.ma50, s.ma200].some(v => v != null) && (
                <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Medias Móviles</div>
                  <div className="space-y-1.5">
                    {[
                      ["MA 5",   s.ma5,   s.pct_vs_ma5],
                      ["MA 10",  s.ma10,  s.pct_vs_ma10],
                      ["MA 20",  s.ma20,  s.pct_vs_ma20],
                      ["MA 50",  s.ma50,  s.pct_vs_ma50],
                      ["MA 200", s.ma200, s.pct_vs_ma200],
                    ].filter(([, v]) => v != null).map(([label, val, p]) => {
                      const above = p >= 0;
                      return (
                        <Tooltip key={label} text={`Precio ${above ? "por encima" : "por debajo"} de la ${label} un ${Math.abs(p).toFixed(2)}%. Valor actual de la ${label}: $${val?.toFixed(2)}.`}>
                          <div className="flex flex-row gap-2 py-0.5 pr-4">
                            <span className="w-12 text-xs text-gray-500 font-medium shrink-0">{label}</span>
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0 ${above ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                              {above ? "↑ Arriba" : "↓ Abajo"}
                            </span>
                            <div className="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                              <div className={`h-1 rounded-full ${above ? "bg-green-400" : "bg-red-400"}`} style={{ width: `${Math.min(Math.abs(p) * 3, 100)}%` }} />
                            </div>
                            <span className="text-[10px] text-gray-400 tabular-nums shrink-0">${val?.toFixed(2)}</span>
                            <span className={`text-xs font-semibold tabular-nums w-14 text-right shrink-0 ${above ? "text-green-600" : "text-red-600"}`}>
                              {above ? "+" : ""}{p?.toFixed(2)}%
                            </span>
                          </div>
                        </Tooltip>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Pivot Points */}
              {s.pivots && (s.pivots.classic || s.pivots.fibonacci) && (
                <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <Tooltip text="Niveles de precio calculados a partir del máximo, mínimo y cierre del período anterior. Funcionan como zonas de soporte (S) y resistencia (R) donde el precio tiende a reaccionar. P es el pivot central, R1-R3 son resistencias arriba, S1-S3 son soportes abajo.">
                      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider underline decoration-dotted underline-offset-2 cursor-help">Pivots</span>
                    </Tooltip>
                    <div className="flex rounded-lg overflow-hidden border border-gray-200 text-[10px]">
                      {["classic", "fibonacci"].map(t => (
                        <Tooltip key={t} text={
                          t === "classic"
                            ? "Método estándar: P = (Máx + Mín + Cierre) / 3. Los niveles R/S se calculan aritméticamente a partir del rango del período. Es el más usado en acciones."
                            : "Mismo pivot central P, pero los niveles R/S usan los ratios de Fibonacci (23.6%, 38.2%, 61.8%). Más populares en forex y crypto. Tienden a coincidir con zonas de reversión en tendencias fuertes."
                        }>
                          <button onClick={() => setPivotType(t)}
                            className={`px-2.5 py-1 font-medium transition ${pivotType === t ? "bg-amber-500 text-white" : "bg-white text-gray-500 hover:bg-gray-50"}`}>
                            {t === "classic" ? "Clásico" : "Fibonacci"}
                          </button>
                        </Tooltip>
                      ))}
                    </div>
                  </div>
                  {(() => {
                    const pts = s.pivots[pivotType];
                    if (!pts) return null;
                    const levels = [
                      { key: "R3", cls: "text-red-700 font-semibold" },
                      { key: "R2", cls: "text-red-500" },
                      { key: "R1", cls: "text-red-400" },
                      { key: "P",  cls: "text-gray-700 font-bold" },
                      { key: "S1", cls: "text-green-400" },
                      { key: "S2", cls: "text-green-500" },
                      { key: "S3", cls: "text-green-700 font-semibold" },
                    ];
                    return (
                      <div className="space-y-0.5">
                        {levels.map(({ key, cls }) => {
                          const val = pts[key];
                          if (val == null) return null;
                          const diff = ((val - s.price) / s.price * 100).toFixed(2);
                          const isAbove = val > s.price;
                          const isP = key === "P";
                          return (
                            <Tooltip key={key} text={
                              isP ? `Pivot central: $${val.toFixed(2)}. El precio está ${isAbove ? "por debajo" : "por encima"} del pivot.` :
                              key.startsWith("R") ? `Resistencia ${key}: $${val.toFixed(2)}. Zona donde el precio puede frenar su suba (+${diff}% desde precio actual).` :
                              `Soporte ${key}: $${val.toFixed(2)}. Zona donde el precio puede encontrar piso (${diff}% desde precio actual).`
                            }>
                              <div className={`flex items-center gap-2 py-0.5 pr-4 ${isP ? "border-y border-gray-100 my-0.5 py-1" : ""}`}>
                                <span className={`w-8 text-xs shrink-0 ${cls}`}>{key}</span>
                                <div className={`w-2 h-2 rounded-full shrink-0 ${isP ? "bg-gray-400" : isAbove ? "bg-red-300" : "bg-green-300"}`} />
                                <span className={`text-xs tabular-nums font-medium ${cls}`}>${val.toFixed(2)}</span>
                                {!isP && (
                                  <span className={`ml-auto text-[10px] tabular-nums ${isAbove ? "text-red-400" : "text-green-500"}`}>
                                    {isAbove ? "+" : ""}{diff}%
                                  </span>
                                )}
                                {isP && <span className="ml-auto text-[10px] text-gray-400">— actual ${s.price?.toFixed(2)}</span>}
                              </div>
                            </Tooltip>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>
              )}

            </div>{/* fin col derecha */}

          </div>{/* fin grid 2 cols */}

        </div>
        </div>{/* overflow-y-auto */}
      </BottomSheet>
      {showChart && <ChartModal ticker={s.ticker} onClose={() => setShowChart(false)} />}
      {showAnalysis && <AnalysisModal ticker={s.ticker} listId={listId} onClose={() => setShowAnalysis(false)} />}
    </>
  );
}

function HelpModal({ onClose }) {
  return (
    <BottomSheet onClose={onClose} className="max-h-[92vh]">
      <div className="overflow-y-auto">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 sticky top-0 bg-white z-10">
          <h2 className="text-lg font-bold text-gray-900">Cómo usar el Screener</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
        </div>

        <div className="space-y-5 text-sm text-gray-700 p-4 sm:p-5">

          <section>
            <h3 className="font-semibold text-gray-900 mb-1">1. Elegí una lista y analizá</h3>
            <p>Seleccioná qué activos analizar: S&P 500, Nasdaq 100, ETFs, ADRs Argentina o Crypto. Presioná <strong>Analizar</strong> para cargar los resultados. Una vez cargados, podés filtrar dentro de la lista usando el buscador.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-1">2. Hacé clic en un ticker</h3>
            <p className="mb-1">Al tocar cualquier activo de la tabla abrís su panel de detalle, que incluye:</p>
            <ul className="list-disc list-inside space-y-0.5 text-xs text-gray-700">
              <li><strong>Gráfico de precio</strong> (últimos 3 meses via TradingView, click para ver fullscreen)</li>
              <li><strong>Score y señal</strong> con dirección, zona estructural y niveles SL/TP1/TP2</li>
              <li><strong>Divergencia</strong> — última señal de divergencia del oscilador de momentum</li>
              <li><strong>Medias Móviles</strong> — grilla MA5→MA200 con distancia % al precio actual</li>
              <li><strong>Pivot Points</strong> — niveles Classic y Fibonacci (R3→S3) con toggle</li>
              <li><strong>Analistas</strong> — precio objetivo, PE ratio, beta y earnings date (vía Yahoo Finance)</li>
              <li><strong>Recomendación de IA</strong> — análisis en español generado con todos los indicadores</li>
            </ul>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-2">3. Sistema de Score</h3>
            <p className="mb-2">El Score (0-100) combina 7 componentes:</p>
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
            <h3 className="font-semibold text-gray-900 mb-2">4. Divergencias de Momentum</h3>
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
            <h3 className="font-semibold text-gray-900 mb-2">5. Columnas clave</h3>
            <div className="space-y-1.5 text-xs">
              {[
                ["Zona",     "DISCOUNT = precio bajo la regresión lineal (zona de valor). FAIR = zona media. PREMIUM = zona extendida (cara)."],
                ["Dir",      "LONG = setup alcista, SHORT = setup bajista. El Score mide la fuerza de esa dirección."],
                ["SL / TP1", "Stop Loss y Take Profit 1 calculados con ATR × 1.5. TP2 = ATR × 3.0."],
                ["ADX",      "Fuerza de la tendencia. Sobre 20 es condición mínima. Sobre 25 es tendencia fuerte."],
                ["Div. RSI", "Última señal del oscilador de divergencias de momentum."],
                ["RSI",      "Sobreventa (<30) o sobrecompra (>70)."],
                ["vs MA200", "Qué tan lejos está del promedio de 200 días. Positivo = tendencia principal alcista."],
                ["Vol ×",    "Volumen de hoy vs promedio 20 días. 1.5x+ confirma movimiento."],
                ["Medias Móviles", "En el detalle del ticker: MA5, MA10, MA20, MA50, MA200 con % de distancia al precio. Verde = precio arriba, rojo = abajo."],
                ["Pivots",   "Niveles de soporte y resistencia calculados del día anterior. Classic (pivots estándar) o Fibonacci. R1-R3 = resistencias, S1-S3 = soportes, P = pivot central."],
              ].map(([col, desc]) => (
                <div key={col} className="flex gap-2">
                  <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 shrink-0 self-start">{col}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-1">6. Flujo de trabajo recomendado</h3>
            <ol className="list-decimal list-inside space-y-1 text-gray-700">
              <li>Elegí la lista y presioná <strong>Analizar</strong>.</li>
              <li>Filtrá por <strong>Compra Fuerte</strong> en el selector de señal.</li>
              <li>Verificá que <strong>Dir</strong> sea LONG y <strong>Zona</strong> sea DISCOUNT o FAIR.</li>
              <li>Confirmá <strong>ADX &gt; 25</strong> y <strong>vs MA200 positivo</strong>.</li>
              <li>Si <strong>Div. RSI</strong> muestra GIRO UP o SIGUE UP → mayor confluencia.</li>
              <li>Hacé clic en el ticker para ver el gráfico, las medias móviles y la recomendación de IA.</li>
              <li>Revisá los <strong>Pivots</strong> para identificar soporte/resistencia inmediata.</li>
              <li>Dimensioná tu riesgo con <strong>SL/TP1/TP2</strong> antes de entrar.</li>
            </ol>
          </section>

          <section className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            <strong>Importante:</strong> Herramienta de filtrado técnico, no una recomendación financiera. Siempre realizá tu propio análisis antes de operar.
          </section>

        </div>
      </div>{/* overflow-y-auto */}
    </BottomSheet>
  );
}

const SIGNAL_CONFIG = {
  compra_fuerte: { label: "▲▲ Compra Fuerte", color: "bg-emerald-100 text-emerald-800", badge: "bg-emerald-600 text-white",     bar: "bg-emerald-500", border: "border-l-emerald-500", count: "text-emerald-700" },
  compra:        { label: "▲ Compra",         color: "bg-green-100 text-green-700",     badge: "bg-green-500 text-white",       bar: "bg-green-400",   border: "border-l-green-400",   count: "text-green-700" },
  neutral:       { label: "· Esperar",        color: "bg-gray-100 text-gray-600",       badge: "bg-gray-200 text-gray-600",     bar: "bg-gray-300",    border: "border-l-gray-400",    count: "text-gray-600" },
  venta:         { label: "▼ Venta",          color: "bg-orange-100 text-orange-700",   badge: "bg-orange-500 text-white",      bar: "bg-orange-400",  border: "border-l-orange-400",  count: "text-orange-600" },
  venta_fuerte:  { label: "▼▼ Venta Fuerte",  color: "bg-red-100 text-red-700",         badge: "bg-red-600 text-white",         bar: "bg-red-500",     border: "border-l-red-500",     count: "text-red-600" },
};

const FILTER_OPTIONS = [
  { key: "all",          label: "Todas" },
  { key: "compra_fuerte",label: "▲▲ Compra Fuerte" },
  { key: "compra",       label: "▲ Compra" },
  { key: "neutral",      label: "· Esperar" },
  { key: "venta",        label: "▼ Venta" },
  { key: "venta_fuerte", label: "▼▼ Venta Fuerte" },
];

const LIST_CONFIG = [
  { id: "sp500",       label: "S&P 500" },
  { id: "nasdaq100",   label: "Nasdaq 100" },
  { id: "etfs",        label: "ETFs" },
  { id: "adrs_arg",    label: "ADRs Argentina" },
  { id: "crypto",      label: "Crypto" },
  { id: "commodities", label: "Commodities" },
  { id: "dolar",       label: "Dólar" },
];

const PULSE_CONFIG = {
  "GIRO UP":   { color: "bg-cyan-100 text-cyan-800",     title: "Divergencia alcista regular" },
  "SIGUE UP":  { color: "bg-yellow-100 text-yellow-800", title: "Continuación alcista (hidden)" },
  "GIRO DN":   { color: "bg-red-100 text-red-800",       title: "Divergencia bajista regular" },
  "SIGUE DN":  { color: "bg-orange-100 text-orange-800", title: "Continuación bajista (hidden)" },
  "AGOT. SUP": { color: "bg-pink-100 text-pink-800",     title: "Agotamiento superior" },
  "AGOT. INF": { color: "bg-blue-100 text-blue-800",     title: "Agotamiento inferior" },
};

const SIGNAL_TOOLTIPS = {
  compra_fuerte: "Momento de compra fuerte — el algoritmo detectó que la tendencia, el momentum y la zona estructural están todos a favor. La señal más sólida del sistema.",
  compra:        "Momento de compra — la mayoría de los indicadores son positivos. Setup válido, pero con menos confluencia que Compra Fuerte. Operá con tu stop loss definido.",
  neutral:       "Mejor esperar — no hay una ventaja clara ni alcista ni bajista. El mercado está indeciso. Quedarse al margen reduce el riesgo innecesario.",
  venta:         "Señal de precaución — el sesgo es bajista moderado. Si ya tenés posición, es momento de revisar. Si no tenés, no es momento de entrar.",
  venta_fuerte:  "Momento de venta fuerte — todos los indicadores apuntan a la baja. Evitá compras. El sistema detectó la señal bajista más clara.",
};

const CRYPTO_NAMES = {
  BTC: "Bitcoin", ETH: "Ethereum", BNB: "BNB", SOL: "Solana",
  XRP: "XRP", ADA: "Cardano", AVAX: "Avalanche", DOGE: "Dogecoin",
  TRX: "TRON", DOT: "Polkadot", LINK: "Chainlink", MATIC: "Polygon",
  LTC: "Litecoin", BCH: "Bitcoin Cash", NEAR: "NEAR Protocol",
  UNI: "Uniswap", ATOM: "Cosmos", XLM: "Stellar", ALGO: "Algorand",
  FIL: "Filecoin", VET: "VeChain", ICP: "Internet Computer",
  ETC: "Ethereum Classic", HBAR: "Hedera", APT: "Aptos",
  ARB: "Arbitrum", OP: "Optimism", SUI: "Sui", INJ: "Injective",
  RENDER: "Render", FET: "Fetch.ai", GRT: "The Graph",
  SAND: "The Sandbox", MANA: "Decentraland", AXS: "Axie Infinity",
  AAVE: "Aave", MKR: "Maker", CRV: "Curve", COMP: "Compound",
  LDO: "Lido DAO", SHIB: "Shiba Inu", PEPE: "Pepe",
  TON: "Toncoin", TAO: "Bittensor", SEI: "Sei", JUP: "Jupiter",
  WIF: "dogwifhat", BONK: "Bonk", FLOKI: "Floki",
};

function TickerTooltip({ s, children }) {
  const base = displayTicker(s.ticker);
  const cryptoName = CRYPTO_NAMES[base];
  const sigCfg = SIGNAL_CONFIG[s.signal] ?? SIGNAL_CONFIG.neutral;
  const zoneLabel = { discount: "DISCOUNT", fair: "FAIR", premium: "PREMIUM" }[s.zone] ?? (s.zone ?? "—");
  const dir = s.direction === "long" ? "LARGO" : s.direction === "short" ? "CORTO" : null;

  const content = (
    <div className="space-y-1.5">
      <div>
        {cryptoName
          ? <><span className="font-bold text-white">{cryptoName}</span>{" "}<span className="text-gray-400">{base}</span></>
          : <span className="font-bold text-white">{base}</span>
        }
      </div>
      <div className="border-t border-gray-700 pt-1.5 space-y-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-amber-400 font-bold">Score {s.score ?? "—"}/100</span>
          {dir && <span className="text-gray-400">· {dir}</span>}
        </div>
        <div>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${sigCfg.badge}`}>{sigCfg.label}</span>
        </div>
        <div className="text-gray-300 flex flex-wrap gap-x-3">
          <span>Zona <span className="text-white font-semibold">{zoneLabel}</span></span>
          {s.rsi != null && <span>RSI <span className="text-white font-semibold">{s.rsi}</span></span>}
          {s.adx != null && <span>ADX <span className="text-white font-semibold">{s.adx}</span></span>}
        </div>
        {s.pulse_signal && s.pulse_signal !== "—" && (
          <div className="text-gray-300">Div. RSI <span className="text-cyan-400 font-semibold">{s.pulse_signal}</span></div>
        )}
      </div>
    </div>
  );

  return <Tooltip content={content}>{children}</Tooltip>;
}

function SignalBadge({ signal }) {
  const cfg = SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.neutral;
  return (
    <Tooltip text={SIGNAL_TOOLTIPS[signal] ?? ""}>
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${cfg.badge}`}>
        {cfg.label}
      </span>
    </Tooltip>
  );
}

function ScoreBar({ value, direction, signal }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const cfg = signal ? (SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.neutral) : SIGNAL_CONFIG.neutral;
  const dirLabel = direction === "LONG" ? "alcista" : direction === "SHORT" ? "bajista" : "sin dirección";
  const quality = value >= 75 ? "Todos los filtros alineados. Setup de máxima calidad."
    : value >= 60 ? "Mayoría de condiciones cumplidas. Setup válido."
    : value >= 40 ? "Condiciones mixtas. Sin ventaja operativa clara."
    : "Condiciones desfavorables.";
  const tipText = `Score ${value}/100 — Sesgo ${dirLabel}. ${quality} Combina: EMA 200, alineación de medias, ADX, momentum RSI, MTF, volatilidad y zona estructural.`;
  return (
    <Tooltip text={tipText}>
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
    </Tooltip>
  );
}

function RsiBar({ value }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const color = value < 30 ? "bg-blue-500" : value > 70 ? "bg-red-500" : "bg-gray-400";
  const tip = value < 30 ? `RSI ${value}: sobreventa extrema. El precio cayó muy rápido — posible rebote técnico próximo.`
    : value < 40 ? `RSI ${value}: zona de sobreventa. Momentum débil, puede estar acercándose a un piso.`
    : value > 70 ? `RSI ${value}: sobrecompra. El precio subió muy rápido — posible corrección a corto plazo.`
    : value > 60 ? `RSI ${value}: momentum positivo. Tendencia alcista activa, vigilar si supera 70.`
    : `RSI ${value}: zona neutral (30-60). Sin exceso de compradores ni vendedores.`;
  return (
    <Tooltip text={tip}>
      <div className="flex items-center gap-2">
        <div className="w-10 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div className={`h-2 rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
        </div>
        <span className="text-sm tabular-nums">{value}</span>
      </div>
    </Tooltip>
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

const ZONE_TOOLTIPS = {
  discount: "DISCOUNT — Precio por debajo de la regresión lineal de 100 ruedas. Zona de valor estructural: el activo está 'barato' respecto a su tendencia. Mejor relación riesgo/beneficio para compras.",
  fair:     "FAIR — Precio en la zona media de la regresión lineal. Sin ventaja estructural clara. Entrada neutra — ni barato ni caro respecto a la tendencia.",
  premium:  "PREMIUM — Precio extendido por encima de la regresión lineal. El activo está 'caro' respecto a su tendencia. Mayor riesgo de corrección — comprar acá implica pagar más.",
};

function ZoneBadge({ zone }) {
  if (!zone) return <span className="text-gray-400">—</span>;
  const cfg = {
    discount: "bg-teal-100 text-teal-800",
    fair:     "bg-gray-100 text-gray-600",
    premium:  "bg-purple-100 text-purple-800",
  };
  const label = { discount: "DISCOUNT", fair: "FAIR", premium: "PREMIUM" };
  return (
    <Tooltip text={ZONE_TOOLTIPS[zone] ?? ""}>
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${cfg[zone] ?? cfg.fair}`}>
        {label[zone] ?? zone.toUpperCase()}
      </span>
    </Tooltip>
  );
}

const PULSE_TOOLTIPS = {
  "GIRO UP":   "Divergencia alcista regular — El precio marcó un mínimo más bajo pero el momentum RSI no lo acompañó. Señal clásica de reversión al alza. Aparece en zonas de sobreventa.",
  "SIGUE UP":  "Divergencia alcista oculta — El precio hizo un mínimo más alto mientras el momentum confirmó. Señal de que la tendencia alcista va a continuar.",
  "GIRO DN":   "Divergencia bajista regular — El precio marcó un máximo más alto pero el momentum RSI bajó. Señal de agotamiento y posible reversión a la baja.",
  "SIGUE DN":  "Divergencia bajista oculta — El precio hizo un máximo más bajo y el momentum lo confirma. Señal de que la tendencia bajista va a continuar.",
  "AGOT. SUP": "Agotamiento superior — El oscilador llegó a zona de sobrecompra (>15) sin divergencia visible. Precaución con compras — el momentum podría revertir pronto.",
  "AGOT. INF": "Agotamiento inferior — El oscilador llegó a zona de sobreventa (<-15). Posible piso de momentum — vigilar señal de entrada al alza.",
};

function PulseBadge({ signal }) {
  if (!signal) return <span className="text-gray-400 text-xs">—</span>;
  const cfg = PULSE_CONFIG[signal];
  if (!cfg) return <span className="text-gray-500 text-xs">{signal}</span>;
  return (
    <Tooltip text={PULSE_TOOLTIPS[signal] ?? cfg.title}>
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${cfg.color}`}>
        {signal}
      </span>
    </Tooltip>
  );
}

const CANDLE_TOOLTIPS = {
  "Doji":              "Doji — Apertura y cierre casi iguales. El mercado está indeciso: compradores y vendedores se equilibraron. Esperar la próxima vela para confirmar dirección.",
  "Hammer":            "Martillo (alcista) — Sombra inferior larga, cuerpo pequeño arriba. Los vendedores empujaron el precio abajo pero los compradores recuperaron el control al cierre. Posible reversal al alza.",
  "Shooting Star":     "Shooting Star (bajista) — Sombra superior larga, cuerpo pequeño abajo. Los compradores intentaron subir pero los vendedores tomaron el control al cierre. Posible reversal a la baja.",
  "Engulfing Alcista": "Engulfing Alcista — La vela de hoy (verde) envuelve completamente la de ayer (roja). Los compradores superaron a los vendedores con fuerza. Señal de reversión al alza.",
  "Engulfing Bajista": "Engulfing Bajista — La vela de hoy (roja) envuelve completamente la de ayer (verde). Los vendedores superaron a los compradores con fuerza. Señal de reversión a la baja.",
  "Morning Star":      "Morning Star (alcista) — 3 velas: bajista grande, vela pequeña o doji, alcista grande. El mercado agotó la caída y los compradores tomaron el control. Señal de reversión al alza.",
  "Evening Star":      "Evening Star (bajista) — 3 velas: alcista grande, vela pequeña o doji, bajista grande. El mercado agotó la suba y los vendedores tomaron el control. Señal de reversión a la baja.",
};

function CandlePatternBadge({ pattern }) {
  if (!pattern) return <span className="text-gray-400 text-xs">—</span>;
  const colors = {
    bullish: "bg-emerald-50 text-emerald-800",
    bearish: "bg-red-50 text-red-800",
    neutral: "bg-gray-100 text-gray-600",
  };
  return (
    <Tooltip text={CANDLE_TOOLTIPS[pattern.name] ?? pattern.name}>
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${colors[pattern.type] ?? colors.neutral}`}>
        {pattern.name}
      </span>
    </Tooltip>
  );
}

function SlTpCell({ sl, tp1, direction }) {
  if (!sl || !tp1) return <span className="text-gray-400">—</span>;
  return (
    <Tooltip text={`Stop Loss: si el precio llega a $${sl.toFixed(2)} la tesis de la operación se invalida — salir para limitar la pérdida. TP1: primer objetivo de ganancia en $${tp1.toFixed(2)}. Ambos calculados con ATR × 1.5 desde el precio actual.`}>
      <div className="text-[10px] leading-tight tabular-nums">
        <div className="text-red-600 font-medium">SL {sl.toFixed(2)}</div>
        <div className="text-green-600 font-medium">TP {tp1.toFixed(2)}</div>
      </div>
    </Tooltip>
  );
}

function SummaryCard({ signal, count, active, onClick }) {
  const cfg = SIGNAL_CONFIG[signal];
  return (
    <button
      onClick={onClick}
      className={`p-3 rounded-xl border-l-4 border border-gray-100 text-left transition bg-white hover:shadow-md ${cfg.border} ${active ? "ring-2 ring-amber-500 shadow-md" : "hover:border-l-4"}`}
    >
      <div className={`text-2xl font-extrabold ${cfg.count}`}>{count}</div>
      <div className={`text-xs font-semibold mt-0.5 ${cfg.color.split(" ")[1]}`}>{cfg.label}</div>
    </button>
  );
}

function DolarTab() {
  const [dollar, setDollar] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updated, setUpdated] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/dollar`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setDollar(data.dollar || []);
      setUpdated(new Date());
    } catch (e) {
      setError(e.message || "Error al cargar cotizaciones");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const fmt = (v) => v != null ? `$${Number(v).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—";

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-gray-400 text-sm">
      <svg className="animate-spin h-5 w-5 mr-2 text-amber-500" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      Cargando cotizaciones…
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center py-20 gap-2">
      <p className="text-red-500 text-sm">{error}</p>
      <button onClick={load} className="text-xs text-amber-600 underline">Reintentar</button>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-base font-semibold text-gray-700">Cotizaciones del dólar</h2>
        <div className="flex items-center gap-3">
          {updated && (
            <span className="text-xs text-gray-400">
              Actualizado {updated.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
          <button
            onClick={load}
            className="text-xs text-amber-600 hover:text-amber-700 border border-amber-300 hover:border-amber-500 px-2.5 py-1 rounded-lg transition"
          >
            Actualizar
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {dollar.map((d) => {
          const isBlue = d.nombre?.toLowerCase() === "blue";
          const spread = (d.compra != null && d.venta != null)
            ? ((d.venta - d.compra) / d.compra * 100).toFixed(1)
            : null;
          const hora = d.fechaActualizacion
            ? new Date(d.fechaActualizacion).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })
            : null;
          return (
            <div
              key={d.nombre}
              className={`bg-white rounded-xl border shadow-sm p-4 transition hover:shadow-md ${
                isBlue
                  ? "border-amber-400 ring-1 ring-amber-300"
                  : "border-gray-200"
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className={`text-sm font-bold ${isBlue ? "text-amber-600" : "text-gray-800"}`}>
                  {d.nombre}
                  {isBlue && <span className="ml-1.5 text-[10px] font-semibold bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">BLUE</span>}
                </span>
                {hora && <span className="text-[10px] text-gray-400">{hora}</span>}
              </div>
              <div className="flex items-end justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-gray-400 w-12">Compra</span>
                    <span className="text-sm font-semibold tabular-nums text-gray-900">{fmt(d.compra)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-gray-400 w-12">Venta</span>
                    <span className={`text-sm font-bold tabular-nums ${isBlue ? "text-amber-600" : "text-gray-900"}`}>
                      {fmt(d.venta)}
                    </span>
                  </div>
                </div>
                {spread != null && (
                  <div className="text-right">
                    <div className="text-[10px] text-gray-400">Spread</div>
                    <div className="text-sm font-semibold text-gray-500">{spread}%</div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-gray-400 text-right mt-2">Fuente: dolarapi.com</p>
    </div>
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
  const [cryptoLimit, setCryptoLimit] = useState(20);
  const [activeListId, setActiveListId] = useState("sp500");
  const [selectedTicker, setSelectedTicker] = useState(null);
  const [aiModalStock, setAiModalStock] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const [watchlist, setWatchlist] = useState(() => {
    try { return JSON.parse(localStorage.getItem("watchlist") || "[]"); } catch { return []; }
  });
  const [quotes, setQuotes] = useState({});
  const [quotesUpdated, setQuotesUpdated] = useState(null);
  const headerRef = useRef(null);
  const stickyBarRef = useRef(null);
  const [aboveTableH, setAboveTableH] = useState(200);

  useEffect(() => {
    const measure = () => {
      const h1 = headerRef.current?.getBoundingClientRect().height ?? 71;
      const h2 = stickyBarRef.current?.getBoundingClientRect().height ?? 130;
      setAboveTableH(Math.round(h1 + h2) + 10);
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (headerRef.current) ro.observe(headerRef.current);
    if (stickyBarRef.current) ro.observe(stickyBarRef.current);
    return () => ro.disconnect();
  }, []);

  const fetchStocks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stocks?signal=${signalFilter}&list_id=${activeListId}`);
      const data = await res.json();
      let stocks = data.stocks ?? [];

      // Para crypto: precios en tiempo real desde Binance (proxeado por el Worker)
      if (activeListId === "crypto" && stocks.length > 0) {
        try {
          // s.ticker viene en formato Yahoo (BTC-USD) → extraer base (BTC)
          const baseSymbols = stocks.map(s => s.ticker.replace(/-USD$/, ""));
          const r = await fetch(
            `${API_BASE}/api/crypto-quotes?symbols=${baseSymbols.join(",")}`,
            { cache: "no-store" }
          );
          if (r.ok) {
            const d = await r.json();
            const quotes = d.quotes || {};
            stocks = stocks.map(s => {
              const base = s.ticker.replace(/-USD$/, "");
              return quotes[base] != null ? { ...s, price: quotes[base] } : s;
            });
          }
        } catch (_) {}
      }

      setStocks(stocks);
      if (data.status) setStatus(data.status);
    } catch { }
  }, [signalFilter, activeListId]);

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status?list_id=${activeListId}`);
      const data = await res.json();
      setProcessed(data.processed ?? 0);
      setTotalTickers(data.total_tickers ?? 0);
      // "idle" means the GH Actions job hasn't created the DB record yet —
      // don't cancel the loading state while waiting for it to start
      if (data.status !== "idle") setStatus(data.status);
      if (data.last_updated) setLastUpdated(data.last_updated);
      if (data.status === "ready") fetchStocks();
    } catch { }
  }, [fetchStocks, activeListId]);

  useEffect(() => { checkStatus(); }, [checkStatus]);

  useEffect(() => {
    if (status !== "loading") return;
    const interval = setInterval(() => {
      checkStatus();
      if (status === "loading") fetchStocks();
    }, 3000);
    return () => clearInterval(interval);
  }, [status, checkStatus, fetchStocks]);

  useEffect(() => {
    if (status === "ready") fetchStocks();
  }, [signalFilter, status, fetchStocks]);

  // Deep link: ?ticker=NVDA abre el modal directamente (viene de alertas ntfy)
  useEffect(() => {
    if (stocks.length === 0) return;
    const param = new URLSearchParams(window.location.search).get("ticker");
    if (!param || selectedTicker) return;
    const found = stocks.find(s => s.ticker === param.toUpperCase());
    if (found) setSelectedTicker(found);
  }, [stocks]);

  const handleRefresh = async () => {
    setLoading(true);
    await fetch(`${API_BASE}/api/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ list_id: selectedList, crypto_limit: cryptoLimit }),
    });
    setActiveListId(selectedList);
    setStocks([]);
    setStatus("loading");
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

  const dataAgeHours = lastUpdated ? (Date.now() / 1000 - lastUpdated) / 3600 : null;
  const isFresh = dataAgeHours !== null && dataAgeHours < 8;

  function fmtAge(hours) {
    if (hours < 1) return `hace ${Math.round(hours * 60)} min`;
    if (hours < 24) return `hace ${Math.round(hours)} h`;
    return `hace ${Math.round(hours / 24)} d`;
  }

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>;
  };

  const th = (label, col, tip = "", hide = "") => (
    <th
      className={`px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap bg-gray-50 ${hide}`}
      onClick={() => handleSort(col)}
    >
      {tip
        ? <Tooltip text={tip}><span className="underline decoration-dotted underline-offset-2 cursor-help">{label}</span></Tooltip>
        : label
      }
      <SortIcon col={col} />
    </th>
  );

  const thStatic = (label, tip = "", hide = "") => (
    <th className={`px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap bg-gray-50 ${hide}`}>
      {tip
        ? <Tooltip text={tip}><span className="underline decoration-dotted underline-offset-2 cursor-help">{label}</span></Tooltip>
        : label
      }
    </th>
  );

  const activeListLabel = LIST_CONFIG.find(l => l.id === activeListId)?.label ?? "";

  // Persist watchlist
  useEffect(() => {
    localStorage.setItem("watchlist", JSON.stringify(watchlist));
  }, [watchlist]);

  // Poll Alpaca quotes every 30s for watchlist stocks (skip crypto -USD)
  useEffect(() => {
    const stockWatchlist = watchlist.filter(t => !t.endsWith("-USD"));
    if (stockWatchlist.length === 0) return;
    const fetchQuotes = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/quotes?tickers=${stockWatchlist.join(",")}`);
        const data = await res.json();
        if (data.quotes) { setQuotes(data.quotes); setQuotesUpdated(new Date()); }
      } catch {}
    };
    fetchQuotes();
    const id = setInterval(fetchQuotes, 30000);
    return () => clearInterval(id);
  }, [watchlist]);

  const toggleWatch = (ticker, e) => {
    e.stopPropagation();
    setWatchlist(prev => prev.includes(ticker) ? prev.filter(t => t !== ticker) : [...prev, ticker]);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}
      {aiModalStock && <AIModal stock={aiModalStock} onClose={() => setAiModalStock(null)} />}
      {selectedTicker && <TickerModal stock={selectedTicker} listId={activeListId} onClose={() => setSelectedTicker(null)} />}

      {/* ── Header oscuro ── */}
      <header ref={headerRef} className="bg-slate-900 shadow-lg sticky top-0 z-30" style={{ borderTop: "3px solid #f59e0b" }}>
        <div className="max-w-screen-2xl mx-auto px-3 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 bg-amber-500 rounded-lg flex items-center justify-center shrink-0 shadow-md">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">máximos</h1>
              </div>
              <p className="text-[11px] text-slate-400 truncate mt-0.5">
                IA integrada
              </p>
            </div>
          </div>
          {/* Status + ayuda */}
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {status === "ready" && stocks.length > 0 && (
              <div className="hidden sm:flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-sm" />
                <span className="text-xs text-slate-400">{stocks.length} activos</span>
              </div>
            )}
            {isBusy && (
              <div className="hidden sm:flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                <span className="text-xs text-slate-400">Analizando…</span>
              </div>
            )}
            <button
              onClick={() => setShowHelp(true)}
              className="text-xs sm:text-sm text-slate-300 hover:text-white border border-slate-700 hover:border-slate-500 px-2.5 sm:px-3 py-1.5 rounded-lg transition"
            >
              ? Ayuda
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-screen-2xl mx-auto p-3 sm:p-6">

        {/* Selector de lista + botón */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-3 sm:p-4 mb-4 sm:mb-5">
          <div className="flex flex-wrap items-center gap-2">
            {LIST_CONFIG.map((l) => (
              <button
                key={l.id}
                onClick={() => { setSelectedList(l.id); setActiveListId(l.id); setStocks([]); setStatus("idle"); setLastUpdated(null); }}
                className={`px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-sm font-medium transition ${
                  selectedList === l.id
                    ? "bg-amber-500 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {l.label}
              </button>
            ))}
            {selectedList !== "dolar" && (
              <div className="w-full sm:w-auto sm:ml-auto mt-1 sm:mt-0 flex flex-col sm:items-end gap-1">
                <button
                  onClick={handleRefresh}
                  disabled={loading || isBusy}
                  className={`w-full sm:w-auto px-5 py-2 text-sm font-medium rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed ${
                    isBusy
                      ? "bg-amber-500 text-white cursor-not-allowed"
                      : isFresh
                        ? "bg-amber-50 text-amber-700 border border-amber-300 hover:bg-amber-100 hover:border-amber-500"
                        : "bg-amber-500 text-white hover:bg-amber-600"
                  }`}
                >
                  {isBusy
                    ? "Analizando…"
                    : isFresh
                      ? `Actualizar ${LIST_CONFIG.find(l => l.id === selectedList)?.label ?? ""}`
                      : `Analizar ${LIST_CONFIG.find(l => l.id === selectedList)?.label ?? ""}`}
                </button>
                {isFresh && !isBusy && (
                  <span className="text-[11px] text-gray-400 text-right">
                    Datos {fmtAge(dataAgeHours)} · {new Date(lastUpdated * 1000).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
            )}
          </div>
          {selectedList === "crypto" && (
            <div className="mt-3 flex items-center gap-4">
              <span className="text-sm text-gray-600 shrink-0">Top</span>
              <input
                type="range"
                min={10} max={100} step={10}
                value={cryptoLimit}
                onChange={(e) => setCryptoLimit(Number(e.target.value))}
                className="flex-1 accent-amber-500"
              />
              <span className="text-sm font-semibold text-amber-700 w-12 text-right">
                {cryptoLimit} cripto{cryptoLimit > 1 ? "s" : ""}
              </span>
            </div>
          )}
        </div>

        {/* Dólar tab */}
        {selectedList === "dolar" && <DolarTab />}

        {/* Loading banner */}
        {selectedList !== "dolar" && isBusy && (
          <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
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
            <div className="w-full bg-amber-100 rounded-full h-2 overflow-hidden">
              {status === "downloading" ? (
                <div className="h-2 bg-amber-400 rounded-full animate-pulse w-full" />
              ) : (
                <div
                  className="bg-amber-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${totalTickers > 0 ? Math.round((processed / totalTickers) * 100) : 0}%` }}
                />
              )}
            </div>
            <p className="text-xs text-amber-600 mt-1 text-right">
              {status === "downloading" ? "Conectando…" : `${totalTickers > 0 ? Math.round((processed / totalTickers) * 100) : 0}%`}
            </p>
          </div>
        )}

        {/* Watchlist */}
        {selectedList !== "dolar" && watchlist.length > 0 && (
          <div className="mb-6 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 bg-gray-50">
              <span className="text-sm font-semibold text-gray-700">Watchlist</span>
              <span className="text-xs text-gray-400">
                {quotesUpdated ? `Actualizado ${quotesUpdated.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}` : "Cargando..."}
              </span>
            </div>
            <div className="flex flex-wrap gap-3 p-4">
              {watchlist.map(ticker => {
                const q = quotes[ticker.replace("-USD", "").replace("-", "")];
                const stockKey = ticker.endsWith("-USD") ? null : ticker;
                const qd = stockKey ? quotes[stockKey] : null;
                const isCrypto = ticker.endsWith("-USD");
                const cached = stocks.find(s => s.ticker === ticker);
                const displayPrice = qd?.price ?? cached?.price;
                const change = qd?.change;
                const changePct = qd?.change_pct;
                return (
                  <div
                    key={ticker}
                    className="flex items-center gap-3 bg-gray-50 hover:bg-amber-50 rounded-lg px-3 py-2 border border-gray-200 min-w-[160px] cursor-pointer transition"
                    onClick={() => cached && setSelectedTicker(cached)}
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {cached
                          ? <TickerTooltip s={cached}><span className="font-semibold text-sm text-gray-900 underline decoration-dotted underline-offset-2">{displayTicker(ticker)}</span></TickerTooltip>
                          : <span className="font-semibold text-sm text-gray-900">{displayTicker(ticker)}</span>
                        }
                        {isCrypto && <span className="text-xs text-gray-400">Binance</span>}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-sm tabular-nums font-mono">
                          {displayPrice != null ? `$${displayPrice.toFixed(2)}` : "—"}
                        </span>
                        {changePct != null && (
                          <span className={`text-xs font-semibold ${changePct >= 0 ? "text-green-600" : "text-red-500"}`}>
                            {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
                          </span>
                        )}
                      </div>
                    </div>
                    <button onClick={(e) => toggleWatch(ticker, e)} className="text-gray-300 hover:text-red-400 text-lg leading-none">✕</button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Resumen por señal + Filtros — sticky bajo el header */}
        {selectedList !== "dolar" && <><div ref={stickyBarRef} className="sticky top-[67px] sm:top-[75px] z-20 bg-gray-50 -mx-3 sm:-mx-6 px-3 sm:px-6 pt-1 pb-3 shadow-[0_4px_8px_-2px_rgba(0,0,0,0.06)]">
          {stocks.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 sm:gap-3 mb-3">
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
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <input
            type="text"
            placeholder="Buscar ticker…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 w-full sm:w-48"
          />
          <div className="flex flex-wrap gap-1">
            {FILTER_OPTIONS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setSignalFilter(key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  signalFilter === key
                    ? "bg-amber-500 text-white"
                    : "bg-white border border-gray-300 text-gray-600 hover:bg-gray-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {search && (
            <button
              onClick={() => setSearch("")}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              ✕ limpiar
            </button>
          )}
          </div>{/* fin filtros */}
        </div>{/* fin sticky */}

        {/* Tabla */}
        <div
          className="mt-2.5 bg-white rounded-xl shadow-sm border border-gray-200 overflow-auto sticky"
          style={{ top: `${aboveTableH}px`, height: `calc(100vh - ${aboveTableH + 16}px)` }}
        >
          {filtered.length === 0 && !isBusy ? (
            stocks.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
                <div className="w-14 h-14 rounded-2xl bg-amber-50 flex items-center justify-center mb-4">
                  <svg className="w-7 h-7 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                </div>
                <p className="text-gray-800 font-semibold text-base mb-1">
                  Presioná <span className="text-amber-600">Analizar</span> para ver los activos
                </p>
                <p className="text-gray-400 text-sm max-w-xs">
                  Vas a ver el ranking completo con Score, señal de compra/venta y análisis de IA para cada uno
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center px-8">
                <div className="text-3xl mb-2">🔍</div>
                <p className="text-gray-500 text-sm">Sin activos para este filtro.</p>
                <button onClick={() => setSignalFilter("all")} className="mt-2 text-xs text-amber-600 hover:underline">Ver todas las señales</button>
              </div>
            )
          ) : (
            <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
                  <tr>
                    {th("Ticker",   "ticker",  "Símbolo del activo. Hacé clic para ver el gráfico, medias móviles, pivots y análisis IA.")}
                    {th("Precio",   "price",   "Precio de cierre del último día de mercado. Para crypto, precio en tiempo real desde Binance.")}
                    {th("Score",    "score",   "Puntuación 0-100 que combina 7 indicadores técnicos: tendencia EMA, ADX, momentum RSI, zona estructural, volumen y multi-timeframe. Cuanto más alto, más señales alineadas a favor.")}
                    {thStatic("Zona",    "Posición del precio en la regresión lineal de 100 períodos. DISCOUNT = precio bajo respecto a su historial reciente, mejor punto de entrada. FAIR = zona media. PREMIUM = precio extendido, mayor riesgo de comprar caro.")}
                    {thStatic("Div. RSI","Divergencias entre el precio y el oscilador de momentum (EMA del RSI-50). GIRO = posible reversión de tendencia. SIGUE = continuación. AGOT. = agotamiento del movimiento actual.")}
                    {thStatic("Señal",   "Recomendación del algoritmo según el Score. Compra Fuerte (≥75), Compra (≥60), Esperar (<60 en ambas direcciones), Venta (≥60 bajista), Venta Fuerte (≥75 bajista).")}
                    {thStatic("IA",      "Análisis generado por inteligencia artificial con todos los indicadores del activo: señal, zona, momentum, volumen, medias móviles y patrones de velas.")}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((s) => (
                    <tr
                      key={s.ticker}
                      className="hover:bg-amber-50 transition cursor-pointer"
                      onClick={() => setSelectedTicker(s)}
                    >
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={(e) => toggleWatch(s.ticker, e)}
                            className={`text-base leading-none transition-colors ${watchlist.includes(s.ticker) ? "text-amber-400" : "text-gray-400 hover:text-amber-400"}`}
                          >{watchlist.includes(s.ticker) ? "★" : "☆"}</button>
                          <TickerTooltip s={s}>
                            <span className="font-semibold text-gray-900 underline decoration-dotted underline-offset-2">{displayTicker(s.ticker)}</span>
                          </TickerTooltip>
                        </div>
                      </td>
                      <td className="px-3 py-3 tabular-nums">${s.price.toFixed(2)}</td>
                      <td className="px-3 py-3">
                        <ScoreBar value={s.score} direction={s.direction} signal={s.signal} />
                      </td>
                      <td className="px-3 py-3"><ZoneBadge zone={s.zone} /></td>
                      <td className="px-3 py-3"><PulseBadge signal={s.pulse_signal} /></td>
                      <td className="px-3 py-3"><SignalBadge signal={s.signal} /></td>
                      <td className="px-3 py-3">
                        <button
                          onClick={e => { e.stopPropagation(); setAiModalStock(s); }}
                          className="text-amber-400 hover:text-amber-600 text-base leading-none transition-colors"
                          title="Análisis IA"
                        >✦</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-3 text-right">
          {filtered.length} activos · Score: EMA + ADX + Momentum + MTF + Zona · Div. RSI: divergencias de momentum
        </p>
        </>}

      </div>
    </div>
  );
}

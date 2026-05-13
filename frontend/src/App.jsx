import { useState, useEffect, useCallback } from "react";

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
            <p>Seleccioná qué acciones querés analizar: S&P 500, Nasdaq 100, ETFs, ADRs Argentina, o escribí tus propios tickers. Luego presioná <strong>Analizar</strong>.</p>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-2">2. Leé el Score (0-100)</h3>
            <p className="mb-2">Es el número más importante. Combina 5 indicadores automáticamente:</p>
            <div className="space-y-1">
              {[
                ["bg-emerald-500", "75-100 → Compra Fuerte", "Múltiples señales alcistas alineadas. La acción tiene momentum, volumen y tendencia a favor."],
                ["bg-green-400",   "60-74 → Compra",         "Señales positivas pero no todas confirmadas. Buena oportunidad con menor convicción."],
                ["bg-gray-300",    "40-59 → Neutral",         "Sin señal clara. Mejor esperar a que se defina la dirección."],
                ["bg-orange-400",  "20-39 → Venta",           "Señales bajistas. Evitar comprar, considerar salir si tenés posición."],
                ["bg-red-500",     "0-19 → Venta Fuerte",     "Confluencia bajista fuerte. Alta probabilidad de continuación a la baja."],
              ].map(([color, label, desc]) => (
                <div key={label} className="flex gap-2 items-start">
                  <div className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${color}`} />
                  <div><span className="font-medium">{label}:</span> {desc}</div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-2">3. Entendé las columnas</h3>
            <div className="space-y-1.5">
              {[
                ["RSI",       "Mide si la acción está sobrevendida (<30, posible rebote) o sobrecomprada (>70, posible baja)."],
                ["vs MA50",   "Qué tan lejos está el precio de la media de 50 días. Positivo = por encima (bueno a corto plazo)."],
                ["vs MA200",  "Lo mismo pero con la media de 200 días. Es el indicador de tendencia más importante. Por encima = alcista."],
                ["Vol ×",     "Cuántas veces el volumen de hoy supera al promedio. Más de 1.5x confirma el movimiento."],
                ["MACD ▲▼",  "▲ verde = momentum alcista. ▼ rojo = momentum bajista."],
                ["% Máx 52s", "Qué tan lejos está del máximo del año. Cerca de 0% = está en máximos."],
                ["% Mín 52s", "Qué tan lejos está del mínimo del año. Cerca de 0% = está en mínimos (posible oportunidad)."],
              ].map(([col, desc]) => (
                <div key={col} className="flex gap-2">
                  <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 shrink-0 self-start">{col}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-semibold text-gray-900 mb-1">4. Flujo de trabajo recomendado</h3>
            <ol className="list-decimal list-inside space-y-1 text-gray-700">
              <li>Filtrá por <strong>Compra Fuerte</strong> o <strong>Compra</strong>.</li>
              <li>Ordená por <strong>Score</strong> de mayor a menor.</li>
              <li>Verificá que el <strong>vs MA200 sea positivo</strong> (tendencia alcista).</li>
              <li>Confirmá que el <strong>Vol ×</strong> sea mayor a 1.2x.</li>
              <li>Las que pasen estos 4 filtros son las candidatas más fuertes.</li>
            </ol>
          </section>

          <section className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            <strong>Importante:</strong> Este screener es una herramienta de filtrado, no una recomendación financiera. Siempre complementá con tu propio análisis antes de tomar decisiones de compra o venta.
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
  { id: "custom",    label: "Personalizada" },
];

function SignalBadge({ signal }) {
  const cfg = SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.neutral;
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function ScoreBar({ value }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const signal = value >= 75 ? "compra_fuerte"
    : value >= 60 ? "compra"
    : value >= 40 ? "neutral"
    : value >= 20 ? "venta"
    : "venta_fuerte";
  const cfg = SIGNAL_CONFIG[signal];
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-2 rounded-full ${cfg.bar}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-sm tabular-nums font-medium">{value}</span>
    </div>
  );
}

function RsiBar({ value }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const color = value < 30 ? "bg-blue-500" : value > 70 ? "bg-red-500" : "bg-gray-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-12 h-2 bg-gray-200 rounded-full overflow-hidden">
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
  const [activeListId, setActiveListId] = useState("sp500");
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
      body: JSON.stringify({ list_id: selectedList, custom }),
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

  const activeListLabel = LIST_CONFIG.find(l => l.id === activeListId)?.label ?? "";

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-screen-xl mx-auto">

        {showHelp && <HelpModal onClose={() => setShowHelp(false)} />}

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
                    {th("RSI",       "rsi")}
                    {th("vs MA50",   "pct_vs_ma50")}
                    {th("vs MA200",  "pct_vs_ma200")}
                    {th("Vol ×",     "vol_ratio")}
                    {th("% Máx 52s", "pct_from_high")}
                    {th("% Mín 52s", "pct_from_low")}
                    {th("MACD",      "macd_hist")}
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Señal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((s) => (
                    <tr key={s.ticker} className="hover:bg-gray-50 transition">
                      <td className="px-3 py-3 font-semibold text-gray-900">{s.ticker}</td>
                      <td className="px-3 py-3 tabular-nums">${s.price.toFixed(2)}</td>
                      <td className="px-3 py-3"><ScoreBar value={s.score} /></td>
                      <td className="px-3 py-3"><RsiBar value={s.rsi} /></td>
                      <td className="px-3 py-3"><PctCell value={s.pct_vs_ma50} /></td>
                      <td className="px-3 py-3"><PctCell value={s.pct_vs_ma200} /></td>
                      <td className="px-3 py-3 tabular-nums">
                        {s.vol_ratio != null
                          ? <span className={s.vol_ratio >= 1.5 ? "font-semibold text-indigo-600" : "text-gray-700"}>
                              {s.vol_ratio.toFixed(2)}x
                            </span>
                          : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-3 py-3"><PctCell value={s.pct_from_high} invertColors={false} /></td>
                      <td className="px-3 py-3"><PctCell value={s.pct_from_low} /></td>
                      <td className="px-3 py-3 tabular-nums">
                        {s.macd_hist != null
                          ? <span className={s.macd_hist > 0 ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
                              {s.macd_hist > 0 ? "▲" : "▼"} {Math.abs(s.macd_hist).toFixed(3)}
                            </span>
                          : <span className="text-gray-400">—</span>}
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
          {filtered.length} activos · Score = Tendencia (MA) + RSI + MACD + Volumen + Bollinger
        </p>
      </div>
    </div>
  );
}

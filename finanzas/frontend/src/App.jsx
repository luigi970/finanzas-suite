import { useState, useEffect, useRef, useCallback } from 'react'

const API = ''

async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error(await r.text())
  if (r.status === 204) return null
  return r.json()
}

const ACCOUNT_TYPES = [
  { value: 'bank',   label: 'Banco',    icon: '🏦' },
  { value: 'crypto', label: 'Crypto',   icon: '₿'  },
  { value: 'broker', label: 'Broker',   icon: '📈' },
  { value: 'cash',   label: 'Efectivo', icon: '💵' },
  { value: 'other',  label: 'Otro',     icon: '📁' },
]

const ASSET_TYPES = [
  { value: 'fiat',       label: 'Fiat (ARS/USD)' },
  { value: 'stablecoin', label: 'Stablecoin (USDT/USDC)' },
  { value: 'crypto',     label: 'Crypto (BTC/ETH)' },
  { value: 'stock',      label: 'Acción' },
  { value: 'cedear',     label: 'CEDEAR' },
  { value: 'fixed_term', label: 'Plazo fijo' },
  { value: 'fund',       label: 'Fondo de inversión' },
]

const CATEGORIES = [
  'sueldo','freelance','inversión','alquiler_cobrado',
  'comida','transporte','servicios','alquiler_pagado',
  'entretenimiento','salud','educación','ropa',
  'transferencia','retiro','otro',
]

const ACCOUNT_COLORS = [
  '#f59e0b','#64748b','#10b981','#ef4444',
  '#3b82f6','#8b5cf6','#ec4899','#14b8a6',
]

function fmtAmount(amount) {
  if (amount === null || amount === undefined) return '—'
  // detecta cuántos decimales significativos tiene
  const str = amount.toString()
  const decimals = str.includes('.') ? str.split('.')[1].replace(/0+$/, '').length : 0
  if (decimals > 4) return amount.toFixed(Math.min(decimals, 8))
  if (decimals > 2) return amount.toFixed(decimals)
  return amount.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function typeIcon(type) {
  return ACCOUNT_TYPES.find(t => t.value === type)?.icon ?? '📁'
}

function assetTypeLabel(type) {
  return ASSET_TYPES.find(t => t.value === type)?.label ?? type
}

// ── HelpModal ─────────────────────────────────────────────────────────────────
function HelpModal({ onClose }) {
  const steps = [
    {
      num: '1',
      title: 'Configurá tus cuentas',
      tab: 'Cuentas',
      icon: '🏦',
      desc: 'Andá al tab "Cuentas" y agregá cada lugar donde tenés plata: bancos, exchanges de crypto, broker, efectivo. Cada cuenta tiene un tipo y un color para identificarla fácil.',
      examples: ['BBVA → Banco', 'Binance → Crypto', 'Invertir Online → Broker', 'Billetera → Efectivo'],
    },
    {
      num: '2',
      title: 'Cargá tus posiciones',
      tab: 'Portfolio',
      icon: '📊',
      desc: 'En el tab "Portfolio" agregá lo que tenés en cada cuenta ahora mismo. Para cada posición indicás el activo, la cantidad y el tipo. Los plazos fijos y fondos también tienen fecha de vencimiento y tasa.',
      examples: ['BBVA: 500.000 ARS (fiat)', 'Binance: 0.05 BTC (crypto)', 'Nexo: 1.000 USDT plazo fijo al 8% hasta 03/06'],
    },
    {
      num: '3',
      title: 'Importá tus movimientos',
      tab: 'Movimientos',
      icon: '📎',
      desc: 'Hacé click en "+ Cargar movimientos". Podés subir un PDF, CSV, imagen, o simplemente pegar texto copiado del homebanking. La IA extrae todas las transacciones automáticamente y te muestra una preview para confirmar antes de guardar.',
      examples: ['PDF del resumen de tarjeta', 'CSV exportado del banco', 'Screenshot del extracto', 'Texto pegado de la app'],
    },
    {
      num: '4',
      title: 'Consultá al agente',
      tab: 'Agente',
      icon: '🤖',
      desc: 'En el tab "Agente" podés preguntarle cualquier cosa sobre tus finanzas en lenguaje natural. Tiene acceso a todas tus cuentas, posiciones y movimientos. También puede cruzar con señales del mercado.',
      examples: ['¿Cuánto gasté este mes?', '¿En qué moneda tengo más exposición?', '¿Cuándo vence mi plazo fijo?', '¿Tengo plata disponible para invertir?'],
    },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-lg max-h-[92vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <span className="font-semibold text-gray-800">Cómo usar la app</span>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="overflow-y-auto flex-1 p-5 space-y-5">
          {steps.map(s => (
            <div key={s.num} className="flex gap-4">
              <div className="flex flex-col items-center shrink-0">
                <div className="w-8 h-8 rounded-full bg-amber-500 text-white text-sm font-bold flex items-center justify-center">
                  {s.num}
                </div>
                {s.num !== '4' && <div className="w-px flex-1 bg-gray-200 mt-2" />}
              </div>
              <div className="pb-4 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-base">{s.icon}</span>
                  <span className="font-semibold text-gray-800 text-sm">{s.title}</span>
                  <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5 font-medium">{s.tab}</span>
                </div>
                <p className="text-sm text-gray-600 leading-relaxed mb-2">{s.desc}</p>
                <div className="flex flex-wrap gap-1.5">
                  {s.examples.map(e => (
                    <span key={e} className="text-[11px] bg-gray-100 text-gray-500 rounded-lg px-2 py-1">{e}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
          <div className="bg-amber-50 rounded-xl p-4 text-sm text-amber-700 leading-relaxed">
            <strong>Consejo:</strong> empezá por las cuentas, después las posiciones, y recién entonces importá movimientos. Así el agente tiene toda la foto completa para ayudarte mejor.
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Modal ────────────────────────────────────────────────────────────────────
function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <span className="font-semibold text-gray-800">{title}</span>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="overflow-y-auto p-5 flex-1">{children}</div>
      </div>
    </div>
  )
}

// ── AccountForm ───────────────────────────────────────────────────────────────
function AccountForm({ initial, onSave, onClose }) {
  const [form, setForm] = useState({
    name: initial?.name ?? '',
    type: initial?.type ?? 'bank',
    color: initial?.color ?? '#f59e0b',
  })
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    await onSave(form)
    onClose()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Nombre</label>
        <input value={form.name} onChange={set('name')} required
          className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tipo</label>
        <select value={form.type} onChange={set('type')}
          className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400">
          {ACCOUNT_TYPES.map(t => <option key={t.value} value={t.value}>{t.icon} {t.label}</option>)}
        </select>
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Color</label>
        <div className="flex gap-2 mt-1">
          {ACCOUNT_COLORS.map(c => (
            <button type="button" key={c} onClick={() => setForm(f => ({ ...f, color: c }))}
              className={`w-7 h-7 rounded-full border-2 transition-transform ${form.color === c ? 'border-gray-800 scale-110' : 'border-transparent'}`}
              style={{ backgroundColor: c }} />
          ))}
        </div>
      </div>
      <div className="flex gap-2 pt-2">
        <button type="button" onClick={onClose}
          className="flex-1 border border-gray-200 rounded-lg py-2 text-sm text-gray-600 hover:bg-gray-50">Cancelar</button>
        <button type="submit"
          className="flex-1 bg-amber-500 text-white rounded-lg py-2 text-sm font-medium hover:bg-amber-600">Guardar</button>
      </div>
    </form>
  )
}

// ── PositionForm ──────────────────────────────────────────────────────────────
function PositionForm({ accounts, initial, onSave, onClose }) {
  const [form, setForm] = useState({
    account_id: initial?.account_id ?? accounts[0]?.id ?? '',
    asset: initial?.asset ?? '',
    asset_type: initial?.asset_type ?? 'fiat',
    quantity: initial?.quantity ?? '',
    start_date: initial?.start_date ?? '',
    end_date: initial?.end_date ?? '',
    rate: initial?.rate ?? '',
    auto_renew: initial?.auto_renew ?? 0,
    notes: initial?.notes ?? '',
  })
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))
  const hasTerm = ['fixed_term', 'fund'].includes(form.asset_type)

  async function submit(e) {
    e.preventDefault()
    await onSave({
      ...form,
      account_id: Number(form.account_id),
      quantity: Number(form.quantity),
      rate: form.rate ? Number(form.rate) : null,
    })
    onClose()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Cuenta</label>
        <select value={form.account_id} onChange={set('account_id')}
          className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400">
          {accounts.map(a => <option key={a.id} value={a.id}>{typeIcon(a.type)} {a.name}</option>)}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Activo</label>
          <input value={form.asset} onChange={set('asset')} required placeholder="ARS, BTC, YPF..."
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Cantidad</label>
          <input value={form.quantity} onChange={set('quantity')} required type="number" step="any"
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tipo de activo</label>
        <select value={form.asset_type} onChange={set('asset_type')}
          className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400">
          {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>
      {hasTerm && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Inicio</label>
            <input type="date" value={form.start_date} onChange={set('start_date')}
              className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Vencimiento</label>
            <input type="date" value={form.end_date} onChange={set('end_date')}
              className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tasa anual %</label>
            <input type="number" step="0.01" value={form.rate} onChange={set('rate')}
              className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" checked={!!form.auto_renew}
                onChange={e => setForm(f => ({ ...f, auto_renew: e.target.checked ? 1 : 0 }))} />
              Auto-renovar
            </label>
          </div>
        </div>
      )}
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Notas</label>
        <input value={form.notes} onChange={set('notes')} placeholder="opcional"
          className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
      </div>
      <div className="flex gap-2 pt-2">
        <button type="button" onClick={onClose}
          className="flex-1 border border-gray-200 rounded-lg py-2 text-sm text-gray-600 hover:bg-gray-50">Cancelar</button>
        <button type="submit"
          className="flex-1 bg-amber-500 text-white rounded-lg py-2 text-sm font-medium hover:bg-amber-600">Guardar</button>
      </div>
    </form>
  )
}

// ── IngestPanel ───────────────────────────────────────────────────────────────
function IngestPanel({ accounts, onDone }) {
  const [accountId, setAccountId] = useState('')
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const fileRef = useRef()

  async function processFile(file) {
    setLoading(true)
    setPreview(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (accountId) fd.append('account_id', accountId)
      const r = await fetch('/api/ingest/file', { method: 'POST', body: fd })
      if (!r.ok) throw new Error(await r.text())
      const data = await r.json()
      setPreview(data.transactions ?? [])
    } catch (e) {
      alert('Error procesando archivo: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  async function processText() {
    if (!text.trim()) return
    setLoading(true)
    setPreview(null)
    try {
      const data = await api('/api/ingest/text', {
        method: 'POST',
        body: JSON.stringify({ text, account_id: accountId ? Number(accountId) : null }),
      })
      setPreview(data.transactions ?? [])
    } catch (e) {
      alert('Error procesando texto: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  async function confirm() {
    if (!accountId) return alert('Seleccioná una cuenta')
    setSaving(true)
    try {
      await api('/api/transactions/batch', {
        method: 'POST',
        body: JSON.stringify({ account_id: Number(accountId), transactions: preview }),
      })
      await api(`/api/positions/sync/${accountId}`, { method: 'POST' })
      setPreview(null)
      setText('')
      onDone()
    } catch (e) {
      alert('Error guardando: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) processFile(file)
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Cuenta destino</label>
        <select value={accountId} onChange={e => setAccountId(e.target.value)}
          className={`mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 ${!accountId ? 'border-amber-400 bg-amber-50' : 'border-gray-200'}`}>
          <option value="">— Elegí una cuenta —</option>
          {accounts.map(a => <option key={a.id} value={a.id}>{typeIcon(a.type)} {a.name}</option>)}
        </select>
      </div>

      {/* Drop zone */}
      <div
        onDrop={onDrop} onDragOver={e => e.preventDefault()}
        onClick={() => fileRef.current?.click()}
        className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-amber-400 hover:bg-amber-50 transition-colors">
        <input ref={fileRef} type="file" className="hidden"
          accept=".pdf,.csv,.txt,.jpg,.jpeg,.png,.webp"
          onChange={e => e.target.files[0] && processFile(e.target.files[0])} />
        <div className="text-3xl mb-2">📎</div>
        <div className="text-sm text-gray-500">Arrastrá o hacé click para subir</div>
        <div className="text-xs text-gray-400 mt-1">PDF · CSV · TXT · JPG · PNG</div>
      </div>

      <div className="text-xs text-gray-400 text-center">— o pegá texto directamente —</div>

      <textarea value={text} onChange={e => setText(e.target.value)} rows={4}
        placeholder="Pegá el contenido de un resumen, extracto, o lista de movimientos..."
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 resize-none" />

      {text && (
        <button onClick={processText} disabled={loading}
          className="w-full bg-amber-500 text-white rounded-lg py-2 text-sm font-medium hover:bg-amber-600 disabled:opacity-50">
          {loading ? 'Procesando...' : 'Analizar texto'}
        </button>
      )}

      {loading && (
        <div className="text-center text-sm text-gray-500 py-4">
          <span className="animate-pulse">Extrayendo transacciones...</span>
        </div>
      )}

      {preview && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">{preview.length} transacciones encontradas</span>
            <button onClick={() => setPreview(null)} className="text-xs text-gray-400 hover:text-gray-600">Descartar</button>
          </div>
          <div className="max-h-64 overflow-y-auto space-y-1.5">
            {preview.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-xs bg-gray-50 rounded-lg px-3 py-2">
                <span className={`font-bold ${t.type === 'income' ? 'text-green-600' : 'text-red-600'}`}>
                  {t.type === 'income' ? '+' : '-'}
                </span>
                <span className="text-gray-400 shrink-0">{t.date}</span>
                <span className="flex-1 text-gray-600 truncate">{t.description}</span>
                <span className="font-semibold tabular-nums shrink-0">{fmtAmount(t.amount)} {t.currency}</span>
                <span className="text-gray-400 shrink-0">{t.category}</span>
              </div>
            ))}
          </div>
          <button onClick={confirm} disabled={saving}
            className="w-full bg-green-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-green-700 disabled:opacity-50">
            {saving ? 'Guardando...' : `Confirmar y guardar ${preview.length} transacciones`}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Chat ──────────────────────────────────────────────────────────────────────
// ── PatrimonioTab ────────────────────────────────────────────────────────────
const MAXIMOS_API = 'http://localhost:8000'
const STABLECOINS = new Set(['USDT','USDC','DAI','BUSD','FDUSD','TUSD','PYUSD'])
const FIAT_USD    = new Set(['USD'])
const FIAT_ARS    = new Set(['ARS'])

function toYahooTicker(asset, assetType) {
  if (assetType === 'crypto' || (!STABLECOINS.has(asset) && !FIAT_USD.has(asset) && !FIAT_ARS.has(asset) && assetType !== 'stock' && assetType !== 'cedear' && assetType !== 'fixed_term' && assetType !== 'fund')) {
    return `${asset}-USD`
  }
  return asset
}

const TYPE_LABELS = {
  fiat: 'Fiat', stablecoin: 'Stablecoins', crypto: 'Crypto',
  stock: 'Acciones', cedear: 'CEDEARs', fixed_term: 'Plazos fijos', fund: 'Fondos',
}
const TYPE_ORDER = ['fiat','stablecoin','crypto','stock','cedear','fixed_term','fund']
const TYPE_COLORS = {
  fiat: 'bg-blue-100 text-blue-700', stablecoin: 'bg-green-100 text-green-700',
  crypto: 'bg-orange-100 text-orange-700', stock: 'bg-purple-100 text-purple-700',
  cedear: 'bg-pink-100 text-pink-700', fixed_term: 'bg-amber-100 text-amber-700',
  fund: 'bg-teal-100 text-teal-700',
}

function PatrimonioTab({ positions, transactions = [] }) {
  const [prices,   setPrices]   = useState({})
  const [blueRate, setBlueRate] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  // Resumen de movimientos del mes actual
  const thisMonth = new Date().toISOString().slice(0, 7)
  const monthTx = transactions.filter(t => t.date?.startsWith(thisMonth))
  const monthIncome  = monthTx.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0)
  const monthExpense = monthTx.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0)
  const currencies = [...new Set(monthTx.map(t => t.currency))].slice(0, 2).join(' / ') || '—'

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // 1. Tipo de cambio blue desde maximos
      const dollarRes = await fetch(`${MAXIMOS_API}/api/dollar`)
      if (dollarRes.ok) {
        const dollarData = await dollarRes.json()
        const blue = (dollarData.dollar || []).find(d => d.nombre?.toLowerCase().includes('blue'))
        if (blue) setBlueRate(blue.venta)
      }

      // 2. Precios de activos desde maximos
      const needsPrice = positions.filter(p =>
        !FIAT_ARS.has(p.asset) && !FIAT_USD.has(p.asset) && !STABLECOINS.has(p.asset) &&
        p.asset_type !== 'fixed_term' && p.asset_type !== 'fund'
      )
      if (needsPrice.length > 0) {
        const tickers = [...new Set(needsPrice.map(p => toYahooTicker(p.asset, p.asset_type)))].join(',')
        const quotesRes = await fetch(`${MAXIMOS_API}/api/quotes?tickers=${tickers}`)
        if (quotesRes.ok) {
          const quotesData = await quotesRes.json()
          setPrices(quotesData.quotes || {})
        }
      }
    } catch (e) {
      setError('No se pudo conectar con maximos. Asegurate de que esté corriendo en localhost:8000.')
    } finally {
      setLoading(false)
    }
  }, [positions])

  useEffect(() => { if (positions.length) load() }, [load, positions])

  function getPriceUSD(pos) {
    if (FIAT_USD.has(pos.asset) || STABLECOINS.has(pos.asset)) return 1
    if (FIAT_ARS.has(pos.asset)) return blueRate ? 1 / blueRate : null
    if (pos.asset_type === 'fixed_term' || pos.asset_type === 'fund') return null
    const ticker = toYahooTicker(pos.asset, pos.asset_type)
    return prices[ticker]?.price ?? null
  }

  // Calcular valores
  const enriched = positions.map(p => {
    const priceUSD = getPriceUSD(p)
    const valueUSD = priceUSD != null ? p.quantity * priceUSD : null
    return { ...p, priceUSD, valueUSD }
  })

  const totalUSD = enriched.reduce((s, p) => s + (p.valueUSD ?? 0), 0)
  const totalARS = blueRate ? totalUSD * blueRate : null

  // Agrupar por tipo
  const byType = {}
  for (const p of enriched) {
    if (!byType[p.asset_type]) byType[p.asset_type] = []
    byType[p.asset_type].push(p)
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-gray-400 text-sm">
      <span className="animate-pulse">Cargando precios desde maximos...</span>
    </div>
  )

  if (positions.length === 0) return (
    <div className="text-center py-16 text-gray-400 text-sm">
      <div className="text-4xl mb-3">💰</div>
      <div>Cargá posiciones en Portfolio para ver tu patrimonio</div>
    </div>
  )

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-700 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={load} className="text-amber-600 font-medium hover:underline">Reintentar</button>
        </div>
      )}

      {/* Mini resumen del mes */}
      {monthTx.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm text-center">
            <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">Ingresos este mes</div>
            <div className="text-sm font-bold text-green-600 tabular-nums">
              {monthIncome.toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </div>
            <div className="text-[10px] text-gray-400">{currencies}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm text-center">
            <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">Gastos este mes</div>
            <div className="text-sm font-bold text-red-500 tabular-nums">
              {monthExpense.toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </div>
            <div className="text-[10px] text-gray-400">{currencies}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm text-center">
            <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">Balance del mes</div>
            <div className={`text-sm font-bold tabular-nums ${monthIncome - monthExpense >= 0 ? 'text-green-600' : 'text-red-500'}`}>
              {(monthIncome - monthExpense >= 0 ? '+' : '')}{(monthIncome - monthExpense).toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </div>
            <div className="text-[10px] text-gray-400">{currencies}</div>
          </div>
        </div>
      )}

      {/* Total patrimonio */}
      <div className="bg-slate-900 rounded-2xl p-6 text-white" style={{ borderTop: '3px solid #f59e0b' }}>
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">Patrimonio total estimado</div>
        <div className="text-4xl font-bold tabular-nums">
          {totalUSD > 0 ? `USD ${totalUSD.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
        </div>
        {totalARS && (
          <div className="text-amber-400 text-lg mt-1 tabular-nums">
            ≈ ARS {totalARS.toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
          </div>
        )}
        {blueRate && (
          <div className="text-xs text-gray-500 mt-2">Dólar blue: ${blueRate} · Precios vía maximos</div>
        )}
      </div>

      {/* Desglose por tipo */}
      {TYPE_ORDER.filter(t => byType[t]).map(type => {
        const group = byType[type]
        const groupTotal = group.reduce((s, p) => s + (p.valueUSD ?? 0), 0)
        const pct = totalUSD > 0 ? (groupTotal / totalUSD) * 100 : 0
        return (
          <div key={type} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${TYPE_COLORS[type]}`}>
                  {TYPE_LABELS[type]}
                </span>
                <div className="h-1.5 w-24 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-1.5 bg-amber-400 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <span className="text-xs text-gray-400">{pct.toFixed(1)}%</span>
              </div>
              <span className="font-semibold text-sm text-gray-700 tabular-nums">
                {groupTotal > 0 ? `USD ${groupTotal.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
              </span>
            </div>
            <div className="divide-y divide-gray-50">
              {group.map(p => (
                <div key={p.id} className="flex items-center gap-3 px-4 py-2.5">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-gray-800">{p.asset}</span>
                      {p.end_date && <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">vence {p.end_date}</span>}
                    </div>
                    <div className="text-xs text-gray-400">{p.account_name} · {fmtAmount(p.quantity)} {p.asset}</div>
                  </div>
                  <div className="text-right shrink-0">
                    {p.priceUSD != null ? (
                      <>
                        <div className="font-semibold text-sm text-gray-800 tabular-nums">
                          USD {(p.valueUSD).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                        <div className="text-xs text-gray-400 tabular-nums">@ USD {fmtAmount(p.priceUSD)}</div>
                      </>
                    ) : (
                      <span className="text-xs text-gray-400">sin precio</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })}

      <button onClick={load} className="text-xs text-amber-600 hover:underline w-full text-center py-2">
        Actualizar precios
      </button>
    </div>
  )
}

// ── TransactionForm ───────────────────────────────────────────────────────────
function TransactionForm({ initial, accounts, onSave, onClose }) {
  const [form, setForm] = useState({
    account_id: initial?.account_id ?? (accounts[0]?.id ?? ''),
    date:        initial?.date ?? new Date().toISOString().slice(0, 10),
    description: initial?.description ?? '',
    amount:      initial?.amount ?? '',
    currency:    initial?.currency ?? 'ARS',
    type:        initial?.type ?? 'expense',
    category:    initial?.category ?? '',
  })
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    await onSave({ ...form, amount: parseFloat(form.amount), account_id: parseInt(form.account_id) })
    onClose()
  }

  const inputCls = "mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Fecha</label>
          <input type="date" value={form.date} onChange={set('date')} required className={inputCls} />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tipo</label>
          <select value={form.type} onChange={set('type')} className={inputCls}>
            <option value="income">Ingreso</option>
            <option value="expense">Gasto</option>
            <option value="transfer">Transferencia</option>
          </select>
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Cuenta</label>
        <select value={form.account_id} onChange={set('account_id')} required className={inputCls}>
          {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Descripción</label>
        <input value={form.description} onChange={set('description')}
          className={inputCls} placeholder="Ej: Supermercado, Netflix..." />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Monto</label>
          <input type="number" step="any" min="0" value={form.amount} onChange={set('amount')} required className={inputCls} />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Moneda</label>
          <input value={form.currency} onChange={set('currency')} required
            className={inputCls} placeholder="ARS, USD, BTC..." />
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Categoría</label>
        <select value={form.category} onChange={set('category')} className={inputCls}>
          <option value="">Sin categoría</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="flex gap-2 pt-1">
        <button type="button" onClick={onClose}
          className="flex-1 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50">
          Cancelar
        </button>
        <button type="submit"
          className="flex-1 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium">
          Guardar
        </button>
      </div>
    </form>
  )
}

// ── AccountCard ───────────────────────────────────────────────────────────────
function AccountCard({ acc, positions, onEdit, onDelete }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col"
      style={{ borderTop: `3px solid ${acc.color}` }}>
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-4 py-3 hover:bg-gray-50 transition-colors text-left w-full">
        <span className="text-base">{typeIcon(acc.type)}</span>
        <span className="font-semibold text-gray-800 text-sm flex-1">{acc.name}</span>
        <span className="text-xs text-gray-400">{positions.length} pos.</span>
        <span className={`text-gray-400 text-[10px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
      </button>
      {open && (
        <div className="divide-y divide-gray-50 overflow-y-auto border-t border-gray-100" style={{ maxHeight: '205px' }}>
          {positions.map(p => (
            <div key={p.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="font-semibold text-sm text-gray-800">{p.asset}</span>
                  <span className="text-[10px] bg-gray-100 text-gray-500 rounded px-1.5 py-0.5">{assetTypeLabel(p.asset_type)}</span>
                  {p.end_date && (
                    <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">vence {p.end_date}</span>
                  )}
                </div>
                {p.notes && <div className="text-xs text-gray-400 mt-0.5 truncate">{p.notes}</div>}
              </div>
              <div className="text-right shrink-0">
                <div className="font-semibold text-sm text-gray-800 tabular-nums">{fmtAmount(p.quantity)}</div>
                {p.rate && <div className="text-[10px] text-green-600">{p.rate}% anual</div>}
              </div>
              <div className="flex gap-1 shrink-0">
                <button onClick={() => onEdit(p)} className="text-xs text-gray-300 hover:text-amber-500 px-1">✏️</button>
                <button onClick={() => onDelete(p.id)} className="text-xs text-gray-300 hover:text-red-500 px-1">🗑</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── PortfolioTab ──────────────────────────────────────────────────────────────
function PortfolioTab({ accounts, positions, onAddPosition, onEditPosition, onDeletePosition }) {
  const activeAccounts = accounts.filter(a => a.active)
  const hasPositions = positions.length > 0

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Posiciones</h2>
        <button onClick={onAddPosition} className="text-xs text-amber-600 hover:underline">+ Agregar</button>
      </div>

      {!hasPositions ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          <div className="text-4xl mb-3">📊</div>
          <div>No tenés posiciones cargadas</div>
          <button onClick={onAddPosition} className="mt-3 text-amber-600 text-xs hover:underline">Agregar posición</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 items-start">
          {activeAccounts.map(acc => {
            const acPos = positions.filter(p => p.account_id === acc.id)
            if (!acPos.length) return null
            return (
              <AccountCard
                key={acc.id}
                acc={acc}
                positions={acPos}
                onEdit={onEditPosition}
                onDelete={onDeletePosition}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}

function Chat() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: '¡Hola! Soy tu asesor financiero. Puedo analizar tus cuentas, posiciones y movimientos. ¿En qué te ayudo?' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    if (!input.trim() || loading) return
    const userMsg = { role: 'user', content: input }
    setMessages(m => [...m, userMsg])
    setInput('')
    setLoading(true)
    try {
      const data = await api('/api/agent/chat', {
        method: 'POST',
        body: JSON.stringify({ messages: [...messages, userMsg].filter(m => m.role !== 'assistant' || messages.indexOf(m) > 0) }),
      })
      setMessages(m => [...m, { role: 'assistant', content: data.reply }])
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: 'Error al conectar con el agente.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-3 p-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === 'user'
                ? 'bg-amber-500 text-white rounded-br-sm'
                : 'bg-gray-100 text-gray-800 rounded-bl-sm'
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-500 animate-pulse">
              Pensando...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 p-4 border-t border-gray-100">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Preguntame sobre tus finanzas..."
          className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
        <button onClick={send} disabled={loading || !input.trim()}
          className="bg-amber-500 text-white rounded-xl px-4 py-2.5 text-sm font-medium hover:bg-amber-600 disabled:opacity-40">
          Enviar
        </button>
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState('patrimonio')
  const [accounts, setAccounts] = useState([])
  const [positions, setPositions] = useState([])
  const [transactions, setTransactions] = useState([])
  const [modal, setModal] = useState(null) // null | 'add-account' | 'add-position' | 'ingest' | 'help'
  const [editTarget, setEditTarget] = useState(null)

  const load = useCallback(async () => {
    const [ac, po, tx] = await Promise.all([
      api('/api/accounts'),
      api('/api/positions'),
      api('/api/transactions?limit=100'),
    ])
    setAccounts(ac)
    setPositions(po)
    setTransactions(tx)
  }, [])

  useEffect(() => { load() }, [load])

  async function saveAccount(data) {
    if (editTarget) {
      await api(`/api/accounts/${editTarget.id}`, { method: 'PATCH', body: JSON.stringify(data) })
    } else {
      await api('/api/accounts', { method: 'POST', body: JSON.stringify(data) })
    }
    await load()
    setEditTarget(null)
  }

  async function deleteAccount(id) {
    if (!confirm('¿Eliminar esta cuenta y todas sus posiciones y transacciones?')) return
    await api(`/api/accounts/${id}`, { method: 'DELETE' })
    await load()
  }

  async function toggleAccount(acc) {
    await api(`/api/accounts/${acc.id}`, { method: 'PATCH', body: JSON.stringify({ active: acc.active ? 0 : 1 }) })
    await load()
  }

  async function savePosition(data) {
    if (editTarget) {
      await api(`/api/positions/${editTarget.id}`, { method: 'PATCH', body: JSON.stringify(data) })
    } else {
      await api('/api/positions', { method: 'POST', body: JSON.stringify(data) })
    }
    await load()
    setEditTarget(null)
  }

  async function deletePosition(id) {
    await api(`/api/positions/${id}`, { method: 'DELETE' })
    await load()
  }

  async function deleteTransaction(id) {
    await api(`/api/transactions/${id}`, { method: 'DELETE' })
    await load()
  }

  async function saveTransaction(data) {
    if (editTarget?.type === 'transaction') {
      await api(`/api/transactions/${editTarget.id}`, { method: 'PATCH', body: JSON.stringify(data) })
    }
    await load()
    setEditTarget(null)
  }

  const TABS = [
    { id: 'patrimonio', label: 'Patrimonio' },
    { id: 'portfolio',  label: 'Portfolio' },
    { id: 'movimientos',label: 'Movimientos' },
    { id: 'agente',     label: 'Agente' },
    { id: 'cuentas',    label: 'Cuentas' },
  ]

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-slate-900 text-white px-4 sm:px-6 py-4 flex items-center justify-between"
        style={{ borderTop: '3px solid #f59e0b' }}>
        <div>
          <span className="text-lg font-bold tracking-tight">finanzas</span>
          <span className="text-xs text-gray-400 ml-2">personal</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setModal('help')}
            className="text-gray-400 hover:text-white text-xs font-medium px-2.5 py-1.5 rounded-lg border border-gray-700 hover:border-gray-500 transition-colors">
            ? Ayuda
          </button>
          <button onClick={() => { setModal('ingest'); setEditTarget(null) }}
            className="bg-amber-500 hover:bg-amber-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg">
            + Cargar movimientos
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-4 sm:px-6">
        <div className="flex gap-0">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? 'border-amber-500 text-amber-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 px-4 sm:px-6 py-6">

        {/* PATRIMONIO */}
        {tab === 'patrimonio' && (
          <PatrimonioTab positions={positions} transactions={transactions} />
        )}

        {/* PORTFOLIO */}
        {tab === 'portfolio' && (
          <PortfolioTab
            accounts={accounts}
            positions={positions}
            onAddPosition={() => { setModal('add-position'); setEditTarget(null) }}
            onEditPosition={p => { setEditTarget(p); setModal('add-position') }}
            onDeletePosition={deletePosition}
          />
        )}

        {/* MOVIMIENTOS */}
        {tab === 'movimientos' && (
          <div className="max-w-3xl mx-auto space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Movimientos recientes</h2>
              <button onClick={() => { setModal('ingest'); setEditTarget(null) }}
                className="text-xs text-amber-600 hover:underline">+ Cargar</button>
            </div>
            {transactions.length === 0 ? (
              <div className="text-center py-16 text-gray-400 text-sm">
                <div className="text-4xl mb-3">📋</div>
                <div>No hay movimientos cargados</div>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="divide-y divide-gray-50">
                  {transactions.map(t => (
                    <div key={t.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 group">
                      <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.type === 'income' ? 'bg-green-500' : 'bg-red-400'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-700 truncate">{t.description || '—'}</div>
                        <div className="text-xs text-gray-400">{t.account_name} · {t.date} {t.category && `· ${t.category}`}</div>
                      </div>
                      <div className={`font-semibold text-sm tabular-nums shrink-0 ${t.type === 'income' ? 'text-green-600' : 'text-red-600'}`}>
                        {t.type === 'income' ? '+' : '-'}{fmtAmount(t.amount)} {t.currency}
                      </div>
                      <button onClick={() => { setEditTarget({ ...t, type: 'transaction' }); setModal('edit-transaction') }}
                        className="text-gray-300 hover:text-amber-500 px-1 text-xs shrink-0">
                        ✏️
                      </button>
                      <button onClick={() => deleteTransaction(t.id)}
                        className="text-gray-300 hover:text-red-500 px-1 text-xs shrink-0">
                        🗑
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* AGENTE */}
        {tab === 'agente' && (
          <div className="max-w-2xl mx-auto h-[calc(100vh-200px)] bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col overflow-hidden">
            <Chat />
          </div>
        )}

        {/* CUENTAS */}
        {tab === 'cuentas' && (
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Cuentas y wallets</h2>
              <button onClick={() => { setModal('add-account'); setEditTarget(null) }}
                className="text-xs text-amber-600 hover:underline">+ Agregar</button>
            </div>
            {accounts.length === 0 ? (
              <div className="text-center py-16 text-gray-400 text-sm">
                <div className="text-4xl mb-3">🏦</div>
                <div>No hay cuentas configuradas</div>
                <button onClick={() => { setModal('add-account'); setEditTarget(null) }}
                  className="mt-3 text-amber-600 text-xs hover:underline">Agregar cuenta</button>
              </div>
            ) : (
              <div className="space-y-2">
                {accounts.map(acc => (
                  <div key={acc.id} className={`bg-white rounded-xl border border-gray-200 shadow-sm flex items-center gap-3 px-4 py-3 ${!acc.active ? 'opacity-50' : ''}`}
                    style={{ borderLeft: `4px solid ${acc.color}` }}>
                    <span className="text-xl">{typeIcon(acc.type)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm text-gray-800">{acc.name}</div>
                      <div className="text-xs text-gray-400">{ACCOUNT_TYPES.find(t => t.value === acc.type)?.label}</div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => toggleAccount(acc)}
                        className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1 rounded hover:bg-gray-100">
                        {acc.active ? 'Ocultar' : 'Mostrar'}
                      </button>
                      <button onClick={() => { setEditTarget(acc); setModal('add-account') }}
                        className="text-xs text-gray-400 hover:text-amber-600 px-2 py-1 rounded hover:bg-gray-100">✏️</button>
                      <button onClick={() => deleteAccount(acc.id)}
                        className="text-xs text-gray-400 hover:text-red-500 px-2 py-1 rounded hover:bg-gray-100">🗑</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      {modal === 'add-account' && (
        <Modal title={editTarget ? 'Editar cuenta' : 'Nueva cuenta'} onClose={() => { setModal(null); setEditTarget(null) }}>
          <AccountForm initial={editTarget} onSave={saveAccount} onClose={() => { setModal(null); setEditTarget(null) }} />
        </Modal>
      )}

      {modal === 'add-position' && (
        <Modal title={editTarget ? 'Editar posición' : 'Nueva posición'} onClose={() => { setModal(null); setEditTarget(null) }}>
          <PositionForm accounts={accounts.filter(a => a.active)} initial={editTarget} onSave={savePosition} onClose={() => { setModal(null); setEditTarget(null) }} />
        </Modal>
      )}

      {modal === 'ingest' && (
        <Modal title="Cargar movimientos" onClose={() => setModal(null)}>
          <IngestPanel accounts={accounts.filter(a => a.active)} onDone={() => { setModal(null); load() }} />
        </Modal>
      )}

      {modal === 'edit-transaction' && editTarget && (
        <Modal title="Editar movimiento" onClose={() => { setModal(null); setEditTarget(null) }}>
          <TransactionForm
            initial={editTarget}
            accounts={accounts}
            onSave={saveTransaction}
            onClose={() => { setModal(null); setEditTarget(null) }}
          />
        </Modal>
      )}

      {modal === 'help' && <HelpModal onClose={() => setModal(null)} />}
    </div>
  )
}

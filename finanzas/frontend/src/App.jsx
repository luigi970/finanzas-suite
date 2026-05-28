import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

function calcAccruedInterest(pos) {
  if (!pos.rate || !pos.start_date) return null
  const start = new Date(pos.start_date)
  if (isNaN(start)) return null
  const today = new Date()
  const end = pos.end_date ? new Date(pos.end_date) : null
  const effectiveEnd = (end && !isNaN(end) && end < today) ? end : today
  const days = (effectiveEnd - start) / (1000 * 60 * 60 * 24)
  if (days <= 0) return null
  return pos.quantity * (pos.rate / 100) * (days / 365)
}

function downloadCSV(rows, filename) {
  const csv = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

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
  { value: 'bank',          label: 'Banco',         icon: '🏦' },
  { value: 'exchange',      label: 'Exchange',       icon: '₿'  },
  { value: 'wallet_crypto', label: 'Wallet Crypto',  icon: '🔐' },
  { value: 'wallet',        label: 'Wallet Fiat',    icon: '👛' },
  { value: 'broker',        label: 'Broker',         icon: '📈' },
  { value: 'cash',          label: 'Efectivo',       icon: '💵' },
  { value: 'other',         label: 'Otro',           icon: '📁' },
]

const ASSET_TYPES = [
  { value: 'fiat',       label: 'Fiat (ARS/USD)' },
  { value: 'stablecoin', label: 'Stablecoin (USDT/USDC)' },
  { value: 'crypto',     label: 'Crypto (BTC/ETH)' },
  { value: 'stock',      label: 'Acción' },
  { value: 'cedear',     label: 'CEDEAR' },
  { value: 'fixed_term', label: 'Plazo fijo' },
  { value: 'fund',       label: 'Fondo de inversión' },
  { value: 'flexible',   label: 'Rendimiento flexible' },
]

const CATEGORIES = [
  'sueldo','freelance','inversión','alquiler_cobrado',
  'comida','transporte','servicios','alquiler_pagado',
  'entretenimiento','salud','educación','ropa',
  'transferencia','retiro','comisión','otro',
]

const ACCOUNT_COLORS = [
  '#f59e0b','#eab308','#64748b','#10b981',
  '#ef4444','#3b82f6','#8b5cf6','#ec4899','#14b8a6',
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
      desc: 'Agregá cada lugar donde tenés plata: banco, exchange de crypto, broker, efectivo. Cada cuenta tiene un tipo y un color.',
      examples: ['BBVA → Banco', 'Binance → Crypto', 'Invertir Online → Broker', 'Efectivo → Efectivo'],
    },
    {
      num: '2',
      title: 'Cargá tus posiciones',
      tab: 'Portfolio',
      icon: '📊',
      desc: 'Agregá lo que tenés en cada cuenta ahora mismo: cripto, acciones, plazos fijos, fiat. Para plazos fijos y staking indicá la tasa y fecha de vencimiento — el interés devengado se calcula solo.',
      examples: ['BBVA: 500.000 ARS', 'Binance: 0.05 BTC (precio promedio 60.000 USD)', 'Nexo: 1.000 USDT al 8% hasta 03/06'],
    },
    {
      num: '3',
      title: 'Importá o cargá movimientos',
      tab: 'Movimientos',
      icon: '📎',
      desc: 'Subí un PDF, imagen o CSV, o pegá texto del homebanking. La IA extrae las transacciones con monto, fecha, tipo y categoría. Podés editar o eliminar filas de la preview antes de confirmar. También podés cargar operaciones manualmente una por una.',
      examples: ['PDF del resumen de tarjeta', 'Screenshot de Binance', 'Texto pegado del homebanking', 'Carga manual de una venta de ETH'],
    },
    {
      num: '4',
      title: 'Registrá compras y ventas de activos',
      tab: 'Movimientos',
      icon: '💹',
      desc: 'Al cargar una compra o venta de cripto/acción, completá el campo "Precio por unidad". Esto actualiza el precio promedio de tu posición y calcula el P&L realizado automáticamente al vender.',
      examples: ['Compra 0.01 BTC a USD 95.000 → actualiza avg_price', 'Venta 0.005 BTC a USD 102.000 → muestra P&L realizado'],
    },
    {
      num: '5',
      title: 'Consultá al agente',
      tab: 'Agente',
      icon: '🤖',
      desc: 'Preguntale cualquier cosa sobre tus finanzas en lenguaje natural. Tiene acceso a tus cuentas, posiciones, movimientos y P&L. También puede sugerirte consultar el screener de mercado.',
      examples: ['¿Cuánto gasté este mes?', '¿En qué moneda tengo más exposición?', '¿Cuándo vence mi plazo fijo?', '¿Cuál fue mi P&L realizado en ETH?'],
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
                {s.num !== '5' && <div className="w-px flex-1 bg-gray-200 mt-2" />}
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
    avg_price: initial?.avg_price ?? '',
    start_date: initial?.start_date ?? '',
    end_date: initial?.end_date ?? '',
    rate: initial?.rate ?? '',
    auto_renew: initial?.auto_renew ?? 0,
    notes: initial?.notes ?? '',
  })
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))
  const hasTerm     = ['fixed_term', 'fund', 'flexible'].includes(form.asset_type)
  const isFlexible  = form.asset_type === 'flexible'

  async function submit(e) {
    e.preventDefault()
    await onSave({
      ...form,
      account_id: Number(form.account_id),
      quantity: Number(form.quantity),
      avg_price: form.avg_price ? Number(form.avg_price) : null,
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
      {!['fiat', 'fixed_term'].includes(form.asset_type) && (
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Precio promedio de compra <span className="text-gray-400 font-normal normal-case">(USD, opcional)</span>
          </label>
          <input type="number" step="any" min="0" value={form.avg_price} onChange={set('avg_price')}
            placeholder="ej: 95000 para BTC comprado a USD 95k"
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
          <p className="mt-1 text-[11px] text-gray-400 leading-snug">
            Cargalo una sola vez. Las compras futuras que registres con precio lo actualizarán automáticamente.
          </p>
        </div>
      )}
      {hasTerm && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Inicio</label>
            <input type="date" value={form.start_date} onChange={set('start_date')}
              className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
          </div>
          {!isFlexible && (
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Vencimiento</label>
              <input type="date" value={form.end_date} onChange={set('end_date')}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
            </div>
          )}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tasa anual %</label>
            <input type="number" step="0.01" value={form.rate} onChange={set('rate')}
              className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
          </div>
          {!isFlexible && (
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input type="checkbox" checked={!!form.auto_renew}
                  onChange={e => setForm(f => ({ ...f, auto_renew: e.target.checked ? 1 : 0 }))} />
                Auto-renovar
              </label>
            </div>
          )}
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
  const [editingIdx, setEditingIdx] = useState(null)
  const fileRef = useRef()

  function updatePreviewRow(idx, field, val) {
    setPreview(p => p.map((t, i) => i === idx ? { ...t, [field]: val } : t))
  }
  function removePreviewRow(idx) {
    setPreview(p => p.filter((_, i) => i !== idx))
  }

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
            <span className="text-sm font-medium text-gray-700">{preview.length} transacciones encontradas · <span className="text-gray-400 font-normal">Hacé click para editar</span></span>
            <button onClick={() => { setPreview(null); setEditingIdx(null) }} className="text-xs text-gray-400 hover:text-gray-600">Descartar</button>
          </div>
          <div className="max-h-80 overflow-y-auto space-y-1.5">
            {preview.map((t, i) => (
              <div key={i} className="text-xs bg-gray-50 rounded-lg overflow-hidden">
                {editingIdx === i ? (
                  <div className="p-2 space-y-2 bg-amber-50 border border-amber-200 rounded-lg">
                    <div className="flex gap-1.5 flex-wrap">
                      <input type="date" value={t.date || ''} onChange={e => updatePreviewRow(i,'date',e.target.value)}
                        className="border border-gray-200 rounded px-2 py-1 text-xs bg-white w-32" />
                      <select value={t.type} onChange={e => updatePreviewRow(i,'type',e.target.value)}
                        className="border border-gray-200 rounded px-2 py-1 text-xs bg-white">
                        <option value="income">Ingreso</option>
                        <option value="expense">Egreso</option>
                        <option value="transfer">Transferencia</option>
                      </select>
                      <input type="number" step="any" value={t.amount} onChange={e => updatePreviewRow(i,'amount',parseFloat(e.target.value)||0)}
                        className="border border-gray-200 rounded px-2 py-1 text-xs bg-white w-24" placeholder="Monto" />
                      <input type="text" value={t.currency} onChange={e => updatePreviewRow(i,'currency',e.target.value.toUpperCase())}
                        className="border border-gray-200 rounded px-2 py-1 text-xs bg-white w-16" placeholder="USD" />
                    </div>
                    <input type="text" value={t.description||''} onChange={e => updatePreviewRow(i,'description',e.target.value)}
                      className="w-full border border-gray-200 rounded px-2 py-1 text-xs bg-white" placeholder="Descripción" />
                    <div className="flex gap-1.5 flex-wrap">
                      <input type="number" step="any" value={t.unit_price||''} onChange={e => updatePreviewRow(i,'unit_price',e.target.value?parseFloat(e.target.value):null)}
                        className="border border-gray-200 rounded px-2 py-1 text-xs bg-white w-28" placeholder="Precio unit. USD" />
                      <input type="number" step="any" value={t.fee||''} onChange={e => updatePreviewRow(i,'fee',e.target.value?parseFloat(e.target.value):null)}
                        className="border border-gray-200 rounded px-2 py-1 text-xs bg-white w-20" placeholder="Comisión" />
                      <input type="text" value={t.fee_currency||''} onChange={e => updatePreviewRow(i,'fee_currency',e.target.value.toUpperCase())}
                        className="border border-gray-200 rounded px-2 py-1 text-xs bg-white w-16" placeholder="BNB" />
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => setEditingIdx(null)} className="flex-1 bg-amber-500 text-white rounded py-1 text-xs font-medium">Listo</button>
                      <button onClick={() => { removePreviewRow(i); setEditingIdx(null) }} className="text-red-400 hover:text-red-600 text-xs px-2">Eliminar</button>
                    </div>
                  </div>
                ) : (
                  <button onClick={() => setEditingIdx(i)} className="w-full text-left px-3 py-2 hover:bg-amber-50 transition-colors">
                    <div className="flex items-center gap-2">
                      <span className={`font-bold shrink-0 ${t.type === 'income' ? 'text-green-600' : t.type === 'transfer' ? 'text-blue-500' : 'text-red-600'}`}>
                        {t.type === 'income' ? '+' : t.type === 'transfer' ? '↔' : '-'}
                      </span>
                      <span className="text-gray-400 shrink-0">{t.date}</span>
                      <span className="flex-1 text-gray-600 truncate">{t.description}</span>
                      <span className="font-semibold tabular-nums shrink-0">{fmtAmount(t.amount)} {t.currency}</span>
                      {t.category && <span className="text-gray-400 shrink-0">{t.category}</span>}
                    </div>
                    {(t.unit_price || t.fee) && (
                      <div className="flex gap-3 pl-4 text-gray-400 mt-0.5">
                        {t.unit_price && <span>@ USD {fmtAmount(t.unit_price)}</span>}
                        {t.fee && <span className="text-orange-400">comisión {t.fee} {t.fee_currency}</span>}
                      </div>
                    )}
                  </button>
                )}
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
const MAXIMOS_LOCAL  = 'http://localhost:8000'
const MAXIMOS_ONLINE = import.meta.env.VITE_MAXIMOS_URL || 'https://maximos-worker.luchotour.workers.dev'
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
  stock: 'Acciones', cedear: 'CEDEARs', fixed_term: 'Plazos fijos', fund: 'Fondos', flexible: 'Rend. flexible',
}
const TYPE_ORDER = ['fiat','stablecoin','crypto','stock','cedear','fixed_term','fund','flexible']
const TYPE_COLORS = {
  fiat: 'bg-blue-100 text-blue-700', stablecoin: 'bg-green-100 text-green-700',
  crypto: 'bg-orange-100 text-orange-700', stock: 'bg-purple-100 text-purple-700',
  cedear: 'bg-pink-100 text-pink-700', fixed_term: 'bg-amber-100 text-amber-700',
  fund: 'bg-teal-100 text-teal-700', flexible: 'bg-lime-100 text-lime-700',
}

function LayoutToggle({ value, onChange }) {
  return (
    <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
      <button
        onClick={() => onChange('grid')}
        title="Grid"
        className={`p-1.5 rounded-md transition-colors ${value === 'grid' ? 'bg-white shadow-sm text-gray-700' : 'text-gray-400 hover:text-gray-600'}`}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="0" y="0" width="6" height="6" rx="1" fill="currentColor"/>
          <rect x="8" y="0" width="6" height="6" rx="1" fill="currentColor"/>
          <rect x="0" y="8" width="6" height="6" rx="1" fill="currentColor"/>
          <rect x="8" y="8" width="6" height="6" rx="1" fill="currentColor"/>
        </svg>
      </button>
      <button
        onClick={() => onChange('masonry')}
        title="Masonry"
        className={`p-1.5 rounded-md transition-colors ${value === 'masonry' ? 'bg-white shadow-sm text-gray-700' : 'text-gray-400 hover:text-gray-600'}`}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="0" y="0" width="6" height="8" rx="1" fill="currentColor"/>
          <rect x="8" y="0" width="6" height="5" rx="1" fill="currentColor"/>
          <rect x="0" y="10" width="6" height="4" rx="1" fill="currentColor"/>
          <rect x="8" y="7" width="6" height="7" rx="1" fill="currentColor"/>
        </svg>
      </button>
    </div>
  )
}

function PatrimonioTypeCard({ type, group, pct }) {
  const [open, setOpen] = useState(true)
  const groupTotal = group.reduce((s, p) => s + (p.valueUSD ?? 0), 0)
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center justify-between w-full px-4 py-3 hover:bg-gray-50 transition-colors text-left">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${TYPE_COLORS[type]}`}>
            {TYPE_LABELS[type]}
          </span>
          <div className="h-1.5 w-16 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-1.5 bg-amber-400 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
          </div>
          <span className="text-xs text-gray-400">{pct.toFixed(1)}%</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-semibold text-sm text-gray-700 tabular-nums">
            {groupTotal > 0 ? `USD ${groupTotal.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
          </span>
          <span className={`text-gray-400 text-[10px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▼</span>
        </div>
      </button>
      {open && (
        <div className="divide-y divide-gray-50 border-t border-gray-100">
          {group.map(p => (
            <div key={p.id} className="flex items-center gap-3 px-4 py-2.5">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm text-gray-800">{p.asset}</span>
                  {p.end_date && <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">vence {p.end_date}</span>}
                  {p.rate && <span className="text-[10px] bg-green-100 text-green-700 rounded px-1.5 py-0.5">{p.rate}% anual</span>}
                </div>
                <div className="text-xs text-gray-400">{p.account_name} · {fmtAmount(p.quantity)} {p.asset}</div>
                {p.accrued != null && (
                  <div className="text-xs text-green-600 tabular-nums">
                    +{fmtAmount(p.accrued)} {p.asset} interés devengado
                  </div>
                )}
              </div>
              <div className="text-right shrink-0">
                {p.priceUSD != null ? (
                  <>
                    <div className="font-semibold text-sm text-gray-800 tabular-nums">
                      USD {(p.valueUSD).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    {!['fixed_term','fund','flexible'].includes(p.asset_type) && (
                      <div className="text-xs text-gray-400 tabular-nums">@ USD {fmtAmount(p.priceUSD)}</div>
                    )}
                    {p.pnlUSD != null && !['fixed_term','fund','flexible'].includes(p.asset_type) && (
                      <div className={`text-xs font-semibold tabular-nums ${p.pnlUSD >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                        {p.pnlUSD >= 0 ? '+' : ''}USD {p.pnlUSD.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        {' '}({p.pnlPct >= 0 ? '+' : ''}{p.pnlPct.toFixed(2)}%)
                      </div>
                    )}
                  </>
                ) : (
                  <span className="text-xs text-gray-400">sin precio</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PatrimonioTab({ positions, transactions = [], maximosUrl = MAXIMOS_ONLINE }) {
  const [prices,   setPrices]   = useState({})
  const [blueRate, setBlueRate] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)
  const [layout,   setLayout]   = useState(() => localStorage.getItem('patrimonio_layout') || 'grid')
  const onLayout = v => { setLayout(v); localStorage.setItem('patrimonio_layout', v) }
  const MAXIMOS_API = maximosUrl

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
      setError(`No se pudo conectar con maximos (${MAXIMOS_API}). Verificá tu conexión o que el servidor esté corriendo.`)
    } finally {
      setLoading(false)
    }
  }, [positions, maximosUrl])

  useEffect(() => { if (positions.length) load() }, [load, positions])

  function getPriceUSD(pos) {
    if (FIAT_USD.has(pos.asset) || STABLECOINS.has(pos.asset)) return 1
    if (FIAT_ARS.has(pos.asset)) return blueRate ? 1 / blueRate : null
    if (pos.asset_type === 'fixed_term' || pos.asset_type === 'fund') return null
    const ticker = toYahooTicker(pos.asset, pos.asset_type)
    return prices[ticker]?.price ?? null
  }

  // Calcular valores (incluyendo interés devengado para plazos fijos / staking)
  const enriched = positions.map(p => {
    const accrued  = calcAccruedInterest(p)  // en moneda nativa
    let priceUSD   = getPriceUSD(p)
    let valueUSD   = null

    if (priceUSD != null) {
      // Activo normal: principal + interés convertido a USD
      const total = accrued != null ? p.quantity + accrued : p.quantity
      valueUSD = total * priceUSD
    } else if (p.asset_type === 'fixed_term' || p.asset_type === 'fund' || p.asset_type === 'flexible') {
      // Plazo fijo / staking sin precio de mercado → valuamos por moneda
      const total = accrued != null ? p.quantity + accrued : p.quantity
      if (FIAT_USD.has(p.asset) || STABLECOINS.has(p.asset)) { valueUSD = total; priceUSD = 1 }
      else if (FIAT_ARS.has(p.asset) && blueRate)            { valueUSD = total / blueRate; priceUSD = 1 / blueRate }
    }

    const costUSD = p.avg_price != null ? p.avg_price * p.quantity : null
    const pnlUSD  = (valueUSD != null && costUSD != null) ? valueUSD - costUSD : null
    const pnlPct  = (priceUSD != null && p.avg_price != null) ? (priceUSD - p.avg_price) / p.avg_price * 100 : null
    return { ...p, priceUSD, valueUSD, costUSD, pnlUSD, pnlPct, accrued }
  })

  const totalUSD      = enriched.reduce((s, p) => s + (p.valueUSD ?? 0), 0)
  const totalARS      = blueRate ? totalUSD * blueRate : null
  const totalPnl      = enriched.reduce((s, p) => s + (p.pnlUSD ?? 0), 0)
  const hasPnl        = enriched.some(p => p.pnlUSD != null)
  const totalRealized = transactions.reduce((s, t) => s + (t.realized_pnl ?? 0), 0)
  const hasRealized   = transactions.some(t => t.realized_pnl != null)

  const feeToUSD = (amount, cur) => {
    if (!amount || !cur) return 0
    const c = cur.toUpperCase()
    if (c === 'USD' || c === 'USDT' || c === 'USDC') return amount
    if (c === 'ARS' && blueRate) return amount / blueRate
    const price = prices[`${c}-USD`]?.price
    return price ? amount * price : 0
  }
  const totalFeesUSD = transactions.reduce((s, t) => {
    // Campo fee en cualquier transacción
    if (t.fee && t.fee_currency) s += feeToUSD(t.fee, t.fee_currency)
    // Egreso categorizado como "comisión"
    if (t.type === 'expense' && t.category === 'comisión') s += feeToUSD(t.amount, t.currency)
    return s
  }, 0)
  const hasFees = transactions.some(t =>
    (t.fee != null && t.fee > 0) || (t.type === 'expense' && t.category === 'comisión')
  )

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
    <div className="max-w-6xl mx-auto space-y-6">
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
      <div className="bg-slate-900 rounded-2xl p-6 text-white flex flex-col sm:flex-row sm:items-center gap-5" style={{ borderTop: '3px solid #f59e0b' }}>

        {/* Izquierda: total principal */}
        <div className="flex-1 min-w-0">
          <div className="text-[11px] text-gray-500 uppercase tracking-widest mb-2">Patrimonio total estimado</div>
          <div className="text-4xl sm:text-5xl font-bold tabular-nums tracking-tight">
            {totalUSD > 0 ? `USD ${totalUSD.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
          </div>
          {totalARS && (
            <div className="text-amber-400 text-base mt-1.5 tabular-nums font-medium">
              ≈ ARS {totalARS.toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </div>
          )}
          {blueRate && (
            <div className="text-xs text-gray-600 mt-3">Dólar blue: ${blueRate} · Precios vía maximos</div>
          )}
        </div>

        {/* Derecha: stats cards */}
        {(hasPnl || hasRealized || hasFees) && (
          <div className="flex flex-wrap gap-3">
            {hasPnl && (
              <div className="bg-white/[0.06] rounded-xl px-4 py-3 min-w-[130px]">
                <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1.5">No realizado</div>
                <div className={`text-xl font-bold tabular-nums ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {totalPnl >= 0 ? '+' : ''}USD {totalPnl.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
            )}
            {hasRealized && (
              <div className="bg-white/[0.06] rounded-xl px-4 py-3 min-w-[130px]">
                <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1.5">Realizado</div>
                <div className={`text-xl font-bold tabular-nums ${totalRealized >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {totalRealized >= 0 ? '+' : ''}USD {totalRealized.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
            )}
            {hasFees && (
              <div className="bg-white/[0.06] rounded-xl px-4 py-3 min-w-[130px]">
                <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1.5">Comisiones</div>
                <div className="text-xl font-bold tabular-nums text-orange-400">
                  -USD {totalFeesUSD.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Desglose por tipo */}
      <div>
        <div className="flex items-center justify-end mb-3">
          <LayoutToggle value={layout} onChange={onLayout} />
        </div>
        <div className={layout === 'masonry'
          ? 'columns-1 sm:columns-2 lg:columns-3 gap-4'
          : 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 items-start'}>
          {TYPE_ORDER.filter(t => byType[t]).map(type => (
            <div key={type} className={layout === 'masonry' ? 'break-inside-avoid mb-4' : ''}>
              <PatrimonioTypeCard type={type} group={byType[type]} pct={totalUSD > 0 ? (byType[type].reduce((s, p) => s + (p.valueUSD ?? 0), 0) / totalUSD) * 100 : 0} />
            </div>
          ))}
        </div>
      </div>

      <button onClick={load} className="text-xs text-amber-600 hover:underline w-full text-center py-2">
        Actualizar precios
      </button>
    </div>
  )
}

// ── TransactionForm ───────────────────────────────────────────────────────────
const FIAT_CURRENCIES = new Set(['ARS','USD','EUR','BRL','UYU'])

function TransactionForm({ initial, accounts, onSave, onClose }) {
  const [form, setForm] = useState({
    account_id:    initial?.account_id ?? (accounts[0]?.id ?? ''),
    to_account_id: '',
    date:          initial?.date ?? new Date().toISOString().slice(0, 10),
    description:   initial?.description ?? '',
    amount:        initial?.amount ?? '',
    currency:      initial?.currency ?? 'ARS',
    type:          initial?.type ?? 'expense',
    category:      initial?.category ?? '',
    unit_price:    initial?.unit_price ?? '',
    fee:           initial?.fee ?? '',
    fee_currency:  initial?.fee_currency ?? '',
  })
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  const isTransfer  = form.type === 'transfer'
  const showUnitPrice = ['income','expense'].includes(form.type) && !FIAT_CURRENCIES.has(form.currency.toUpperCase())

  async function submit(e) {
    e.preventDefault()
    const base = { ...form, amount: parseFloat(form.amount), account_id: parseInt(form.account_id) }
    if (form.unit_price !== '' && showUnitPrice) base.unit_price = parseFloat(form.unit_price)
    else delete base.unit_price
    if (form.fee !== '' && form.fee_currency) { base.fee = parseFloat(form.fee); base.fee_currency = form.fee_currency.toUpperCase() }
    else { delete base.fee; delete base.fee_currency }

    if (isTransfer && form.to_account_id) {
      // Crear egreso en cuenta origen e ingreso en cuenta destino
      await onSave({ ...base, type: 'expense', description: base.description || 'Transferencia' })
      await onSave({ ...base, type: 'income',  account_id: parseInt(form.to_account_id), description: base.description || 'Transferencia' })
    } else {
      await onSave(base)
    }
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
            <option value="income">Ingreso / Compra</option>
            <option value="expense">Egreso / Venta / Gasto</option>
            <option value="transfer">Transferencia</option>
          </select>
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          {isTransfer ? 'Cuenta origen' : 'Cuenta'}
        </label>
        <select value={form.account_id} onChange={set('account_id')} required className={inputCls}>
          {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      {isTransfer && (
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Cuenta destino</label>
          <select value={form.to_account_id} onChange={set('to_account_id')} required={isTransfer} className={inputCls}>
            <option value="">— Elegí una cuenta —</option>
            {accounts.filter(a => a.id !== parseInt(form.account_id)).map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <p className="mt-1 text-[11px] text-gray-400">Se registra un egreso en origen y un ingreso en destino automáticamente.</p>
        </div>
      )}
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
      {!isTransfer && (
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">Categoría</label>
          <select value={form.category} onChange={set('category')} className={inputCls}>
            <option value="">Sin categoría</option>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      )}
      {showUnitPrice && !isTransfer && (
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Precio por unidad (USD) <span className="text-gray-400 normal-case font-normal">(opcional)</span>
          </label>
          <input type="number" step="any" min="0" value={form.unit_price} onChange={set('unit_price')}
            className={inputCls} placeholder="ej: 97500 para ETH a USD 97.500" />
          <p className="mt-1 text-[11px] text-gray-400 leading-snug">
            {form.type === 'income'
              ? 'Si lo completás, el costo promedio de tu posición se actualiza automáticamente.'
              : 'Si lo completás, se calcula y guarda la ganancia o pérdida realizada de esta venta.'}
          </p>
        </div>
      )}
      {!isTransfer && (
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Comisión <span className="text-gray-400 normal-case font-normal">(opcional)</span>
          </label>
          <div className="flex gap-2 mt-1">
            <input type="number" step="any" min="0" value={form.fee} onChange={set('fee')}
              className={`${inputCls} flex-1`} placeholder="0.001" />
            <input type="text" value={form.fee_currency} onChange={set('fee_currency')}
              className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 shrink-0" placeholder="BNB" maxLength={10} />
          </div>
        </div>
      )}
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
  const [layout, setLayout] = useState(() => localStorage.getItem('portfolio_layout') || 'grid')
  const onLayout = v => { setLayout(v); localStorage.setItem('portfolio_layout', v) }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Posiciones</h2>
        <div className="flex items-center gap-3">
          <LayoutToggle value={layout} onChange={onLayout} />
          <button onClick={onAddPosition} className="text-xs text-amber-600 hover:underline">+ Agregar</button>
        </div>
      </div>

      {!hasPositions ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          <div className="text-4xl mb-3">📊</div>
          <div>No tenés posiciones cargadas</div>
          <button onClick={onAddPosition} className="mt-3 text-amber-600 text-xs hover:underline">Agregar posición</button>
        </div>
      ) : (
        <div className={layout === 'masonry'
          ? 'columns-1 sm:columns-2 lg:columns-3 gap-3'
          : 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 items-start'}>
          {activeAccounts.map(acc => {
            const acPos = positions.filter(p => p.account_id === acc.id)
            if (!acPos.length) return null
            return (
              <div key={acc.id} className={layout === 'masonry' ? 'break-inside-avoid mb-3' : ''}>
                <AccountCard
                  acc={acc}
                  positions={acPos}
                  onEdit={onEditPosition}
                  onDelete={onDeletePosition}
                />
              </div>
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
      let msg = 'Error al conectar con el agente.'
      try { const d = JSON.parse(e.message); if (d.detail) msg = d.detail } catch {}
      setMessages(m => [...m, { role: 'assistant', content: msg }])
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

// ── MovimientosTab ────────────────────────────────────────────────────────────
function MovimientosTab({ transactions, accounts, onEdit, onDelete, onNewManual, onImport }) {
  const [search, setSearch]               = useState('')
  const [filterMonth, setFilterMonth]     = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [filterAccount, setFilterAccount] = useState('')
  const [displayLimit, setDisplayLimit]   = useState(50)

  const months     = useMemo(() => [...new Set(transactions.map(t => t.date?.slice(0, 7)).filter(Boolean))].sort().reverse(), [transactions])
  const categories = useMemo(() => [...new Set(transactions.map(t => t.category).filter(Boolean))].sort(), [transactions])

  const filtered = useMemo(() => transactions.filter(t => {
    if (filterMonth    && !t.date?.startsWith(filterMonth))                                            return false
    if (filterCategory && t.category !== filterCategory)                                               return false
    if (filterAccount  && String(t.account_id) !== filterAccount)                                      return false
    if (search) {
      const q = search.toLowerCase()
      if (![t.description, t.currency, t.category, t.account_name].some(v => v?.toLowerCase().includes(q))) return false
    }
    return true
  }), [transactions, search, filterMonth, filterCategory, filterAccount])

  const visible = filtered.slice(0, displayLimit)

  function resetFilters() { setSearch(''); setFilterMonth(''); setFilterCategory(''); setFilterAccount(''); setDisplayLimit(50) }

  function exportCSV() {
    const headers = ['fecha','cuenta','descripcion','monto','moneda','tipo','categoria','precio_unit','pnl_realizado','comision','moneda_comision']
    const rows = filtered.map(t => [t.date, t.account_name, t.description || '', t.amount, t.currency, t.type, t.category || '', t.unit_price || '', t.realized_pnl || '', t.fee || '', t.fee_currency || ''])
    downloadCSV([headers, ...rows], `movimientos_${new Date().toISOString().slice(0,10)}.csv`)
  }

  const inputCls = 'border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 text-gray-600 bg-white'

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Movimientos</h2>
        <div className="flex items-center gap-3">
          <button onClick={exportCSV} className="text-xs text-gray-400 hover:text-gray-600 transition-colors">↓ CSV</button>
          <button onClick={onNewManual} className="text-xs text-gray-500 hover:text-amber-600">+ Manual</button>
          <button onClick={onImport} className="text-xs text-amber-600 hover:underline">+ Importar</button>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap gap-2">
        <input value={search} onChange={e => { setSearch(e.target.value); setDisplayLimit(50) }}
          placeholder="Buscar..." className={`${inputCls} flex-1 min-w-[150px]`} />
        <select value={filterMonth} onChange={e => { setFilterMonth(e.target.value); setDisplayLimit(50) }} className={inputCls}>
          <option value="">Todos los meses</option>
          {months.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={filterCategory} onChange={e => { setFilterCategory(e.target.value); setDisplayLimit(50) }} className={inputCls}>
          <option value="">Todas las categorías</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filterAccount} onChange={e => { setFilterAccount(e.target.value); setDisplayLimit(50) }} className={inputCls}>
          <option value="">Todas las cuentas</option>
          {accounts.map(a => <option key={a.id} value={String(a.id)}>{a.name}</option>)}
        </select>
        {(search || filterMonth || filterCategory || filterAccount) && (
          <button onClick={resetFilters} className="text-xs text-gray-400 hover:text-gray-600 px-2">✕ Limpiar</button>
        )}
      </div>

      {transactions.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          <div className="text-4xl mb-3">📋</div>
          <div>No hay movimientos cargados</div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-10 text-gray-400 text-sm">
          <div>No hay resultados para ese filtro</div>
          <button onClick={resetFilters} className="mt-2 text-amber-500 hover:underline text-xs">Limpiar filtros</button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          {(filtered.length < transactions.length) && (
            <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-700">
              Mostrando {Math.min(visible.length, filtered.length)} de {filtered.length} movimientos filtrados (total: {transactions.length})
            </div>
          )}
          <div className="divide-y divide-gray-50">
            {visible.map(t => (
              <div key={t.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 group">
                <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.type === 'income' ? 'bg-green-500' : t.type === 'transfer' ? 'bg-blue-400' : 'bg-red-400'}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-700 truncate">{t.description || '—'}</div>
                  <div className="text-xs text-gray-400">{t.account_name} · {t.date}{t.category && ` · ${t.category}`}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`font-semibold text-sm tabular-nums ${t.type === 'income' ? 'text-green-600' : t.type === 'transfer' ? 'text-blue-500' : 'text-red-600'}`}>
                    {t.type === 'income' ? '+' : t.type === 'transfer' ? '↔' : '-'}{fmtAmount(t.amount)} {t.currency}
                  </div>
                  {t.realized_pnl != null && (
                    <div className={`text-xs font-semibold tabular-nums ${t.realized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {t.realized_pnl >= 0 ? '+' : ''}USD {t.realized_pnl.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} realizado
                    </div>
                  )}
                  {t.fee != null && t.fee > 0 && (
                    <div className="text-xs text-orange-400 tabular-nums">comisión {t.fee} {t.fee_currency}</div>
                  )}
                </div>
                <button onClick={() => onEdit(t)} className="text-gray-300 hover:text-amber-500 px-1 text-xs shrink-0">✏️</button>
                <button onClick={() => onDelete(t.id)} className="text-gray-300 hover:text-red-500 px-1 text-xs shrink-0">🗑</button>
              </div>
            ))}
          </div>
          {filtered.length > displayLimit && (
            <button onClick={() => setDisplayLimit(l => l + 50)}
              className="w-full py-3 text-sm text-gray-400 hover:text-amber-600 hover:bg-gray-50 transition-colors border-t border-gray-100">
              Cargar más · {filtered.length - displayLimit} restantes
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ── SettingsModal ─────────────────────────────────────────────────────────────
function SettingsModal({ maximosMode, onMode, onClose }) {
  const [localStatus, setLocalStatus] = useState(null) // null | true | false
  const [starting, setStarting]       = useState(false)

  useEffect(() => {
    if (maximosMode === 'local') checkLocal()
  }, [maximosMode])

  async function checkLocal() {
    setLocalStatus(null)
    try {
      const r = await fetch('/api/maximos/status')
      const d = await r.json()
      setLocalStatus(d.running)
    } catch { setLocalStatus(false) }
  }

  async function startLocal() {
    setStarting(true)
    try {
      await fetch('/api/maximos/start', { method: 'POST' })
      // Polling hasta que arranque (max 15s)
      for (let i = 0; i < 15; i++) {
        await new Promise(r => setTimeout(r, 1000))
        const r = await fetch('/api/maximos/status')
        const d = await r.json()
        if (d.running) { setLocalStatus(true); break }
      }
    } catch {}
    setStarting(false)
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">Configuración</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <p className="text-xs text-gray-500 mb-3">Fuente de precios de mercado</p>
        <div className="flex flex-col gap-2">
          {[
            { id: 'online', label: 'Online', sub: 'maximos en Cloudflare', icon: '☁️' },
            { id: 'local',  label: 'Local',  sub: 'maximos en localhost:8000', icon: '💻' },
          ].map(opt => (
            <button key={opt.id} onClick={() => { onMode(opt.id); if (opt.id === 'local') setLocalStatus(null) }}
              className={`flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-colors ${
                maximosMode === opt.id ? 'border-amber-500 bg-amber-50' : 'border-gray-200 hover:border-gray-300'
              }`}>
              <span className="text-xl">{opt.icon}</span>
              <div>
                <div className="text-sm font-medium text-gray-900">{opt.label}</div>
                <div className="text-xs text-gray-500">{opt.sub}</div>
              </div>
              {maximosMode === opt.id && <span className="ml-auto text-amber-500 text-sm">✓</span>}
            </button>
          ))}
        </div>

        {maximosMode === 'local' && (
          <div className="mt-4 p-3 rounded-xl bg-gray-50 border border-gray-200">
            <div className="flex items-center gap-2 mb-2">
              {localStatus === null && <span className="text-xs text-gray-400">Verificando...</span>}
              {localStatus === true  && <><span className="w-2 h-2 rounded-full bg-green-500 shrink-0" /><span className="text-xs text-green-700 font-medium">maximos corriendo</span></>}
              {localStatus === false && <><span className="w-2 h-2 rounded-full bg-red-500 shrink-0" /><span className="text-xs text-red-600 font-medium">maximos no está corriendo</span></>}
              <button onClick={checkLocal} className="ml-auto text-xs text-gray-400 hover:text-gray-600">↻</button>
            </div>
            {localStatus === false && (
              <button onClick={startLocal} disabled={starting}
                className="w-full py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-medium disabled:opacity-50 transition-colors">
                {starting ? 'Arrancando...' : 'Arrancar maximos'}
              </button>
            )}
          </div>
        )}

        <p className="text-xs text-gray-400 mt-4">
          Usá <strong>Online</strong> si no tenés maximos local.
          Usá <strong>Local</strong> para precios de acciones más actualizados.
        </p>
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
  const [modal, setModal] = useState(null) // null | 'add-account' | 'add-position' | 'ingest' | 'help' | 'settings'
  const [editTarget, setEditTarget] = useState(null)
  const [maximosMode, setMaximosMode] = useState(() => localStorage.getItem('maximos_mode') || 'online')
  const maximosUrl = maximosMode === 'local' ? MAXIMOS_LOCAL : MAXIMOS_ONLINE
  const saveMaximosMode = m => { setMaximosMode(m); localStorage.setItem('maximos_mode', m) }

  const load = useCallback(async () => {
    const [ac, po, tx] = await Promise.all([
      api('/api/accounts'),
      api('/api/positions'),
      api('/api/transactions?limit=500'),
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
    if (editTarget?.id) {
      await api(`/api/transactions/${editTarget.id}`, { method: 'PATCH', body: JSON.stringify(data) })
    } else {
      await api('/api/transactions', { method: 'POST', body: JSON.stringify(data) })
      if (data.account_id) {
        await api(`/api/positions/create-missing/${data.account_id}`, { method: 'POST' })
      }
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
          <button onClick={() => setModal('settings')}
            title="Configuración"
            className="text-gray-400 hover:text-white text-base px-2 py-1.5 rounded-lg border border-gray-700 hover:border-gray-500 transition-colors">
            ⚙️
          </button>
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
      <div className="bg-white border-b border-gray-200 px-4 sm:px-6 sticky top-0 z-10">
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
          <PatrimonioTab positions={positions} transactions={transactions} maximosUrl={maximosUrl} />
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
          <MovimientosTab
            transactions={transactions}
            accounts={accounts}
            onEdit={t => { setEditTarget(t); setModal('edit-transaction') }}
            onDelete={deleteTransaction}
            onNewManual={() => { setModal('new-transaction'); setEditTarget(null) }}
            onImport={() => { setModal('ingest'); setEditTarget(null) }}
          />
        )}

        {/* AGENTE */}
        {tab === 'agente' && (
          <div className="max-w-2xl mx-auto h-[calc(100vh-200px)] bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col overflow-hidden">
            <Chat />
          </div>
        )}

        {/* CUENTAS */}
        {tab === 'cuentas' && (
          <div className="max-w-4xl mx-auto space-y-4">
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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {accounts.map(acc => (
                  <div key={acc.id} className={`bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col gap-3 p-4 ${!acc.active ? 'opacity-50' : ''}`}
                    style={{ borderTop: `3px solid ${acc.color}` }}>
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{typeIcon(acc.type)}</span>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-sm text-gray-800 truncate">{acc.name}</div>
                        <div className="text-xs text-gray-400">{ACCOUNT_TYPES.find(t => t.value === acc.type)?.label}</div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between border-t border-gray-100 pt-2">
                      <button onClick={() => toggleAccount(acc)}
                        className="text-xs text-gray-400 hover:text-gray-600">
                        {acc.active ? 'Ocultar' : 'Mostrar'}
                      </button>
                      <div className="flex gap-1">
                        <button onClick={() => { setEditTarget(acc); setModal('add-account') }}
                          className="text-gray-300 hover:text-amber-500 px-1.5 py-1 rounded hover:bg-gray-100 text-xs">✏️</button>
                        <button onClick={() => deleteAccount(acc.id)}
                          className="text-gray-300 hover:text-red-500 px-1.5 py-1 rounded hover:bg-gray-100 text-xs">🗑</button>
                      </div>
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

      {modal === 'new-transaction' && (
        <Modal title="Nueva transacción" onClose={() => setModal(null)}>
          <TransactionForm
            initial={null}
            accounts={accounts}
            onSave={saveTransaction}
            onClose={() => { setModal(null); load() }}
          />
        </Modal>
      )}

      {modal === 'edit-transaction' && editTarget && (
        <Modal title="Editar movimiento" onClose={() => { setModal(null); setEditTarget(null); load() }}>
          <TransactionForm
            initial={editTarget}
            accounts={accounts}
            onSave={saveTransaction}
            onClose={() => { setModal(null); setEditTarget(null); load() }}
          />
        </Modal>
      )}

      {modal === 'help' && <HelpModal onClose={() => setModal(null)} />}

      {modal === 'settings' && (
        <SettingsModal
          maximosMode={maximosMode}
          onMode={saveMaximosMode}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}

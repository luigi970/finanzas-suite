import { useState, useEffect, useRef } from 'react'

const TEAL = '#14b8a6'

const TABS = [
  { id: 'dashboard',   label: 'Dashboard' },
  { id: 'perfil',      label: 'Perfil' },
  { id: 'arca',        label: 'ARCA' },
  { id: 'documentos',  label: 'Documentos' },
  { id: 'agente',      label: 'Agente' },
  { id: 'vencimientos',label: 'Vencimientos' },
]

const CONDICIONES = [
  { value: 'monotributo',          label: 'Monotributista' },
  { value: 'responsable_inscripto',label: 'Responsable Inscripto' },
  { value: 'relacion_dependencia', label: 'Relación de dependencia' },
  { value: 'otro',                 label: 'Otro' },
]

const AUTOMATIONS = [
  { id: 'nuestra-parte',              label: 'Nuestra Parte',              desc: 'Datos completos del contribuyente, patrimonio, inversiones' },
  { id: 'monotributo-info',           label: 'Monotributo',                desc: 'Categoría actual, monto facturado, próximo vencimiento' },
  { id: 'mis-retenciones',            label: 'Retenciones',                desc: 'Retenciones y percepciones de Ganancias y BP' },
  { id: 'domicilio-fiscal-electronico',label: 'Domicilio Fiscal',          desc: 'Notificaciones e intimaciones de ARCA' },
  { id: 'ccma',                       label: 'Cuenta Corriente',           desc: 'Deuda, movimientos y obligaciones mensuales' },
  { id: 'mis-comprobantes',           label: 'Comprobantes',               desc: 'Comprobantes emitidos y recibidos' },
  { id: 'mis-facilidades',            label: 'Facilidades de Pago',        desc: 'Planes de pago activos' },
]

// ── SettingsModal ──────────────────────────────────────────────────────────────
function SettingsModal({ onClose }) {
  const [groq, setGroq]     = useState('')
  const [google, setGoogle] = useState('')
  const [sdk, setSdk]       = useState('')
  const [saved, setSaved]   = useState(false)

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(d => {
      setGroq(d.groq || '')
      setGoogle(d.google || '')
      setSdk(d.afipsdk || '')
    })
  }, [])

  const save = async () => {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groq_key: groq, google_key: google, afipsdk_key: sdk }),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
        <h2 className="text-base font-semibold text-gray-800 mb-4">Configuración</h2>
        <div className="space-y-3">
          {[
            { label: 'Groq API Key', val: groq, set: setGroq, ph: 'gsk_...' },
            { label: 'Google API Key', val: google, set: setGoogle, ph: 'AIza...' },
            { label: 'AFIP SDK Token', val: sdk, set: setSdk, ph: 'Tu access_token de afipsdk.com' },
          ].map(({ label, val, set, ph }) => (
            <div key={label}>
              <label className="text-xs text-gray-500 font-medium">{label}</label>
              <input type="password" value={val} onChange={e => set(e.target.value)}
                placeholder={ph}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
            </div>
          ))}
        </div>
        <button onClick={save}
          className="mt-4 w-full py-2.5 rounded-xl text-sm font-semibold text-white transition-colors"
          style={{ background: TEAL }}>
          {saved ? '¡Guardado!' : 'Guardar'}
        </button>
      </div>
    </div>
  )
}

// ── DashboardTab ───────────────────────────────────────────────────────────────
function DashboardTab({ profile, cacheList }) {
  if (!profile?.cuit) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <div className="text-4xl mb-3">📋</div>
          <h3 className="font-semibold text-gray-700 mb-1">Completá tu perfil fiscal</h3>
          <p className="text-sm text-gray-400">Ingresá tu CUIT y condición impositiva para empezar.</p>
        </div>
      </div>
    )
  }

  const syncedAutomations = cacheList.map(c => c.automation)

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-400 uppercase tracking-wide font-medium mb-1">CUIT</div>
          <div className="text-lg font-bold text-gray-800">{profile.cuit}</div>
          <div className="text-sm text-gray-500">{CONDICIONES.find(c => c.value === profile.condicion)?.label || '—'}</div>
        </div>
        {profile.condicion === 'monotributo' && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 uppercase tracking-wide font-medium mb-1">Categoría</div>
            <div className="text-3xl font-bold" style={{ color: TEAL }}>{profile.categoria_monotributo || '?'}</div>
          </div>
        )}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-400 uppercase tracking-wide font-medium mb-2">Datos ARCA</div>
          <div className="space-y-1">
            {AUTOMATIONS.slice(0, 3).map(a => (
              <div key={a.id} className="flex items-center gap-2 text-xs">
                <span className={syncedAutomations.includes(a.id) ? 'text-teal-500' : 'text-gray-300'}>
                  {syncedAutomations.includes(a.id) ? '✓' : '○'}
                </span>
                <span className="text-gray-600">{a.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Bienes declarables</h3>
        <div className="flex flex-wrap gap-2">
          {[
            { key: 'tiene_inmuebles',      label: 'Inmuebles' },
            { key: 'tiene_vehiculos',      label: 'Vehículos' },
            { key: 'opera_cripto',         label: 'Cripto' },
            { key: 'opera_cedears',        label: 'CEDEARs' },
            { key: 'usa_broker',           label: 'Broker' },
            { key: 'tiene_caja_ahorro_usd',label: 'CA USD' },
          ].map(({ key, label }) => (
            <span key={key} className={`text-xs px-2.5 py-1 rounded-full font-medium ${
              profile[key] ? 'bg-teal-100 text-teal-700' : 'bg-gray-100 text-gray-400'
            }`}>{label}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── PerfilTab ──────────────────────────────────────────────────────────────────
function PerfilTab({ profile, onSave }) {
  const [form, setForm] = useState({
    cuit: '', razon_social: '', condicion: 'monotributo', categoria_monotributo: '',
    tiene_inmuebles: 0, tiene_vehiculos: 0, tiene_inversiones: 0,
    opera_cripto: 0, opera_cedears: 0, usa_broker: 0, tiene_caja_ahorro_usd: 0,
    periodo_fiscal: new Date().getFullYear().toString(), notas: '',
    ...profile,
  })
  const [saved, setSaved] = useState(false)

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setSaved(true)
    onSave()
    setTimeout(() => setSaved(false), 2000)
  }

  const inp = 'border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 w-full'
  const chk = (key, label) => (
    <label key={key} className="flex items-center gap-2 cursor-pointer">
      <input type="checkbox" checked={!!form[key]} onChange={e => upd(key, e.target.checked ? 1 : 0)}
        className="w-4 h-4 rounded accent-teal-500" />
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  )

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Perfil Fiscal</h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-500 font-medium">CUIT</label>
            <input className={`mt-1 ${inp}`} value={form.cuit} onChange={e => upd('cuit', e.target.value)} placeholder="20-12345678-9" />
          </div>
          <div>
            <label className="text-xs text-gray-500 font-medium">Razón social</label>
            <input className={`mt-1 ${inp}`} value={form.razon_social} onChange={e => upd('razon_social', e.target.value)} placeholder="Tu nombre completo" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-500 font-medium">Condición fiscal</label>
            <select className={`mt-1 ${inp}`} value={form.condicion} onChange={e => upd('condicion', e.target.value)}>
              {CONDICIONES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          {form.condicion === 'monotributo' && (
            <div>
              <label className="text-xs text-gray-500 font-medium">Categoría monotributo</label>
              <select className={`mt-1 ${inp}`} value={form.categoria_monotributo} onChange={e => upd('categoria_monotributo', e.target.value)}>
                <option value="">Sin especificar</option>
                {'ABCDEFGHIJK'.split('').map(c => <option key={c} value={c}>Categoría {c}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="text-xs text-gray-500 font-medium">Período fiscal</label>
            <input className={`mt-1 ${inp}`} value={form.periodo_fiscal} onChange={e => upd('periodo_fiscal', e.target.value)} placeholder="2025" />
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-500 font-medium mb-2 block">Bienes y actividades declarables</label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {chk('tiene_inmuebles', 'Inmuebles')}
            {chk('tiene_vehiculos', 'Vehículos')}
            {chk('tiene_inversiones', 'Inversiones financieras')}
            {chk('opera_cripto', 'Criptomonedas')}
            {chk('opera_cedears', 'CEDEARs')}
            {chk('usa_broker', 'Broker / acciones')}
            {chk('tiene_caja_ahorro_usd', 'Caja de ahorro USD')}
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-500 font-medium">Notas adicionales</label>
          <textarea className={`mt-1 ${inp} resize-none`} rows={3} value={form.notas}
            onChange={e => upd('notas', e.target.value)}
            placeholder="Ej: Tengo un inmueble alquilado, soy profesional liberal..." />
        </div>

        <button onClick={save}
          className="w-full py-2.5 rounded-xl text-sm font-semibold text-white transition-colors"
          style={{ background: TEAL }}>
          {saved ? '¡Guardado!' : 'Guardar perfil'}
        </button>
      </div>
    </div>
  )
}

// ── ARCATab ────────────────────────────────────────────────────────────────────
function ARCATab({ profile, cacheList, onSync }) {
  const [showSyncModal, setShowSyncModal] = useState(false)
  const [selectedAuto, setSelectedAuto]   = useState(null)
  const [password, setPassword]           = useState('')
  const [periodo, setPeriodo]             = useState(new Date().getFullYear().toString())
  const [syncing, setSyncing]             = useState(false)
  const [syncResult, setSyncResult]       = useState(null)
  const [expandedData, setExpandedData]   = useState(null)

  const cacheMap = Object.fromEntries(cacheList.map(c => [c.automation, c]))

  const openSync = (auto) => {
    setSelectedAuto(auto)
    setPassword('')
    setSyncResult(null)
    setShowSyncModal(true)
  }

  const runSync = async () => {
    setSyncing(true)
    setSyncResult(null)
    try {
      const r = await fetch('/api/arca/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          automation: selectedAuto.id,
          cuit: profile.cuit.replace(/[-]/g, ''),
          password,
          periodo,
        }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'Error')
      setSyncResult({ ok: true, source: data.source })
      onSync()
    } catch (e) {
      setSyncResult({ ok: false, error: e.message })
    } finally {
      setSyncing(false)
      setPassword('')
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {!profile?.cuit && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700">
          Completá tu perfil fiscal antes de sincronizar con ARCA.
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Automatizaciones disponibles</h2>
          <p className="text-xs text-gray-400 mt-0.5">La Clave Fiscal no se guarda. Se usa solo durante la sincronización.</p>
        </div>
        <div className="divide-y divide-gray-50">
          {AUTOMATIONS.map(auto => {
            const cached = cacheMap[auto.id]
            return (
              <div key={auto.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-700">{auto.label}</div>
                  <div className="text-xs text-gray-400">{auto.desc}</div>
                  {cached && (
                    <div className="text-xs text-teal-600 mt-0.5">
                      Actualizado {cached.fetched_at?.slice(0, 10)} · expira {cached.expires_at?.slice(0, 10)}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  {cached && (
                    <button onClick={() => setExpandedData({ label: auto.label, id: auto.id })}
                      className="text-xs text-gray-400 hover:text-teal-600 px-2 py-1 rounded-lg hover:bg-gray-50">
                      Ver datos
                    </button>
                  )}
                  <button onClick={() => openSync(auto)} disabled={!profile?.cuit}
                    className="text-xs font-medium px-3 py-1.5 rounded-lg text-white disabled:opacity-40 transition-colors"
                    style={{ background: TEAL }}>
                    {cached ? 'Actualizar' : 'Sincronizar'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {showSyncModal && selectedAuto && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setShowSyncModal(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-gray-800 mb-1">Sincronizar — {selectedAuto.label}</h3>
            <p className="text-xs text-gray-400 mb-4">CUIT: {profile.cuit}</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 font-medium">Clave Fiscal</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="Tu Clave Fiscal de ARCA"
                  className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
              </div>
              <div>
                <label className="text-xs text-gray-500 font-medium">Período (año)</label>
                <input value={periodo} onChange={e => setPeriodo(e.target.value)}
                  className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
              </div>
            </div>
            {syncResult && (
              <div className={`mt-3 text-sm px-3 py-2 rounded-lg ${syncResult.ok ? 'bg-teal-50 text-teal-700' : 'bg-red-50 text-red-600'}`}>
                {syncResult.ok ? `Datos obtenidos desde ${syncResult.source}` : syncResult.error}
              </div>
            )}
            <div className="flex gap-2 mt-4">
              <button onClick={() => setShowSyncModal(false)}
                className="flex-1 py-2.5 rounded-xl text-sm text-gray-500 hover:bg-gray-50 border border-gray-200">
                Cancelar
              </button>
              <button onClick={runSync} disabled={!password || syncing}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                style={{ background: TEAL }}>
                {syncing ? 'Sincronizando...' : 'Sincronizar'}
              </button>
            </div>
            {syncing && <p className="text-xs text-gray-400 text-center mt-2">Puede tardar hasta 2 minutos...</p>}
          </div>
        </div>
      )}

      {expandedData && <CacheDataModal automation={expandedData} onClose={() => setExpandedData(null)} />}
    </div>
  )
}

function CacheDataModal({ automation, onClose }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    fetch(`/api/arca/cache/${automation.id}`).then(r => r.json()).then(d => setData(d.data))
  }, [automation.id])

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">{automation.label}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="overflow-y-auto flex-1 p-4">
          <pre className="text-xs text-gray-600 whitespace-pre-wrap break-words">
            {data ? JSON.stringify(data, null, 2) : 'Cargando...'}
          </pre>
        </div>
      </div>
    </div>
  )
}

// ── DocumentosTab ──────────────────────────────────────────────────────────────
function DocumentosTab() {
  const [docs, setDocs]       = useState([])
  const [uploading, setUploading] = useState(false)
  const fileRef               = useRef()

  const load = () => fetch('/api/documents').then(r => r.json()).then(setDocs)
  useEffect(() => { load() }, [])

  const upload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('type', 'ddjj')
    await fetch('/api/documents/upload', { method: 'POST', body: fd })
    setUploading(false)
    load()
    fileRef.current.value = ''
  }

  const del = async (id) => {
    await fetch(`/api/documents/${id}`, { method: 'DELETE' })
    load()
  }

  const TYPE_LABELS = { ddjj: 'DDJJ', recibo: 'Recibo', constancia: 'Constancia', otro: 'Otro' }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Subir documento</h2>
        <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-teal-300 transition-colors cursor-pointer"
          onClick={() => fileRef.current?.click()}>
          <div className="text-2xl mb-2">📄</div>
          <p className="text-sm text-gray-500">{uploading ? 'Procesando...' : 'PDF, JPG o PNG — hacé click para subir'}</p>
          <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden" onChange={upload} />
        </div>
      </div>

      {docs.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="divide-y divide-gray-50">
            {docs.map(d => (
              <div key={d.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 group">
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-700 truncate">{d.name}</div>
                  <div className="text-xs text-gray-400">{TYPE_LABELS[d.type] || d.type}{d.period && ` · ${d.period}`} · {d.created_at?.slice(0, 10)}</div>
                </div>
                <button onClick={() => del(d.id)}
                  className="text-gray-300 hover:text-red-500 text-xs opacity-0 group-hover:opacity-100 transition-opacity px-1">🗑</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── AgenteTab ──────────────────────────────────────────────────────────────────
function AgenteTab({ messages, setMessages }) {
  const [input, setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const endRef              = useRef()

  useEffect(() => {
    fetch('/api/agent/chat').then(r => r.json()).then(hist => {
      if (hist.length > 0) setMessages(hist.map(h => ({ role: h.role, content: h.content })))
    })
  }, [])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg = { role: 'user', content: input }
    setMessages(m => [...m, userMsg])
    setInput('')
    setLoading(true)
    const r = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: input }),
    })
    const data = await r.json()
    setMessages(m => [...m, { role: 'assistant', content: data.reply }])
    setLoading(false)
  }

  const clear = async () => {
    await fetch('/api/agent/chat', { method: 'DELETE' })
    setMessages([])
  }

  const INITIAL = [
    '¿Cómo estoy fiscalmente?',
    '¿Tengo que presentar Bienes Personales?',
    '¿Cuándo vence el monotributo?',
    '¿Qué pasa si no declaro el cripto?',
  ]

  return (
    <div className="max-w-3xl mx-auto h-[calc(100vh-200px)] bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div>
          <span className="text-sm font-semibold text-gray-700">Asesor Fiscal IA</span>
          <span className="ml-2 text-xs text-gray-400">Conoce tu situación completa</span>
        </div>
        {messages.length > 0 && (
          <button onClick={clear} className="text-xs text-gray-400 hover:text-gray-600">Limpiar</button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-400 text-center py-4">Preguntame sobre tu situación fiscal</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {INITIAL.map(q => (
                <button key={q} onClick={() => { setInput(q); setTimeout(send, 50) }}
                  className="text-left text-sm text-gray-600 bg-gray-50 hover:bg-teal-50 hover:text-teal-700 rounded-xl px-4 py-3 border border-gray-100 transition-colors">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
              m.role === 'user' ? 'text-white' : 'bg-gray-100 text-gray-800'
            }`} style={m.role === 'user' ? { background: TEAL } : {}}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-2.5 text-sm text-gray-400">Analizando...</div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-gray-100 p-3 flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), send())}
          placeholder="Preguntá sobre tu situación fiscal..."
          className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
        <button onClick={send} disabled={!input.trim() || loading}
          className="px-4 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-40"
          style={{ background: TEAL }}>
          Enviar
        </button>
      </div>
    </div>
  )
}

// ── VencimientosTab ────────────────────────────────────────────────────────────
function VencimientosTab({ profile }) {
  const condicion = profile?.condicion

  const all = [
    { name: 'Recategorización Monotributo', date: '2026-01-20', type: 'presentacion', applies: ['monotributo'], notes: 'Revisar si los parámetros del semestre anterior superan los límites de categoría' },
    { name: 'Recategorización Monotributo', date: '2026-07-20', type: 'presentacion', applies: ['monotributo'], notes: 'Segunda recategorización del año' },
    { name: 'Bienes Personales DDJJ', date: '2026-06-22', type: 'presentacion', applies: ['monotributo', 'responsable_inscripto', 'relacion_dependencia'], notes: 'Fecha aproximada — varía según último dígito del CUIT' },
    { name: 'Bienes Personales — pago', date: '2026-06-22', type: 'pago', applies: ['monotributo', 'responsable_inscripto', 'relacion_dependencia'], notes: 'Misma fecha que presentación' },
    { name: 'Ganancias 4ta categoría DDJJ', date: '2026-06-29', type: 'presentacion', applies: ['relacion_dependencia'], notes: 'Solo si el empleador no hizo retención definitiva' },
    { name: 'IVA mensual', date: '2026-07-18', type: 'pago', applies: ['responsable_inscripto'], notes: 'Vencimiento del período Junio 2026' },
  ]

  const applicable = condicion ? all.filter(o => o.applies.includes(condicion)) : all
  const sorted = [...applicable].sort((a, b) => a.date.localeCompare(b.date))
  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {!condicion && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700">
          Completá tu condición fiscal en el perfil para ver solo los vencimientos que te aplican.
        </div>
      )}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="divide-y divide-gray-50">
          {sorted.map((o, i) => {
            const overdue = o.date < today
            const soon    = !overdue && o.date <= new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10)
            return (
              <div key={i} className="flex items-start gap-3 px-4 py-3">
                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${overdue ? 'bg-red-400' : soon ? 'bg-amber-400' : 'bg-gray-200'}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-700">{o.name}</div>
                  <div className="text-xs text-gray-400 mt-0.5">{o.notes}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-xs font-semibold tabular-nums ${overdue ? 'text-red-500' : soon ? 'text-amber-500' : 'text-gray-500'}`}>
                    {o.date}
                  </div>
                  <div className={`text-[10px] mt-0.5 ${o.type === 'presentacion' ? 'text-blue-500' : 'text-orange-500'}`}>
                    {o.type === 'presentacion' ? 'Presentación' : 'Pago'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── App ────────────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab]         = useState('dashboard')
  const [showSettings, setShowSettings] = useState(false)
  const [profile, setProfile] = useState({})
  const [cacheList, setCacheList] = useState([])
  const [chatMessages, setChatMessages] = useState([])

  const loadProfile  = () => fetch('/api/profile').then(r => r.json()).then(setProfile)
  const loadCache    = () => fetch('/api/arca/cache').then(r => r.json()).then(setCacheList)

  useEffect(() => { loadProfile(); loadCache() }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-40 bg-slate-900 text-white shadow-lg"
        style={{ borderTop: `3px solid ${TEAL}` }}>
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-center justify-between h-12">
            <span className="font-bold tracking-wide text-base">fiscal</span>
            <button onClick={() => setShowSettings(true)} className="text-slate-400 hover:text-white text-lg">⚙️</button>
          </div>
          <div className="flex gap-1 overflow-x-auto pb-0 -mb-px scrollbar-none">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`px-4 py-2 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors ${
                  tab === t.id ? 'border-teal-400 text-teal-400' : 'border-transparent text-slate-400 hover:text-white'
                }`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {tab === 'dashboard'    && <DashboardTab profile={profile} cacheList={cacheList} />}
        {tab === 'perfil'       && <PerfilTab profile={profile} onSave={loadProfile} />}
        {tab === 'arca'         && <ARCATab profile={profile} cacheList={cacheList} onSync={loadCache} />}
        {tab === 'documentos'   && <DocumentosTab />}
        {tab === 'agente'       && <AgenteTab messages={chatMessages} setMessages={setChatMessages} />}
        {tab === 'vencimientos' && <VencimientosTab profile={profile} />}
      </main>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  )
}

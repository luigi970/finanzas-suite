import { useState, useEffect, useCallback } from 'react'

const APPS = [
  {
    id: 'maximos',
    name: 'máximos',
    desc: 'Screener de acciones, ETFs y cripto con scoring técnico',
    port: 5173,
    accent: '#f59e0b',
    accentLight: 'rgba(245,158,11,0.12)',
    border: 'rgba(245,158,11,0.35)',
  },
  {
    id: 'finanzas',
    name: 'finanzas',
    desc: 'Seguimiento de patrimonio, posiciones y movimientos',
    port: 5174,
    accent: '#f59e0b',
    accentLight: 'rgba(245,158,11,0.12)',
    border: 'rgba(245,158,11,0.35)',
  },
  {
    id: 'fiscal',
    name: 'fiscal',
    desc: 'Asistente fiscal inteligente — ARCA, AFIP y obligaciones',
    port: 5175,
    accent: '#14b8a6',
    accentLight: 'rgba(20,184,166,0.12)',
    border: 'rgba(20,184,166,0.35)',
  },
]

function StatusDot({ ok, label }) {
  return (
    <span className="flex items-center gap-1 text-xs" style={{ color: ok ? '#4ade80' : '#f87171' }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: ok ? '#4ade80' : '#475569',
        boxShadow: ok ? '0 0 6px #4ade80' : 'none',
        display: 'inline-block', flexShrink: 0,
      }} />
      {label}
    </span>
  )
}

function AppCard({ app, status, onOpen, onStart, starting }) {
  const s = status[app.id] || { backend: false, frontend: false }
  const bothUp = s.backend && s.frontend

  return (
    <div style={{
      background: '#1e293b',
      border: `1px solid ${s.backend || s.frontend ? app.border : 'rgba(255,255,255,0.07)'}`,
      borderTop: `3px solid ${app.accent}`,
      borderRadius: 12,
      padding: '24px 28px',
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      transition: 'border-color 0.3s',
    }}>
      <div>
        <h2 style={{ color: '#f8fafc', fontSize: 22, fontWeight: 700, letterSpacing: '-0.5px', marginBottom: 6 }}>
          {app.name}
        </h2>
        <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.5 }}>{app.desc}</p>
      </div>

      <div style={{ display: 'flex', gap: 14 }}>
        <StatusDot ok={s.backend} label="backend" />
        <StatusDot ok={s.frontend} label="frontend" />
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
        <button
          onClick={() => onOpen(app.port)}
          disabled={!bothUp}
          style={{
            flex: 1,
            padding: '9px 0',
            borderRadius: 8,
            border: 'none',
            background: bothUp ? app.accent : '#334155',
            color: bothUp ? '#0f172a' : '#64748b',
            fontWeight: 600,
            fontSize: 14,
            cursor: bothUp ? 'pointer' : 'default',
            transition: 'all 0.2s',
          }}
        >
          Abrir
        </button>
        <button
          onClick={() => onStart(app.id)}
          disabled={bothUp || starting === app.id}
          style={{
            flex: 1,
            padding: '9px 0',
            borderRadius: 8,
            border: `1px solid ${bothUp ? 'rgba(255,255,255,0.08)' : app.border}`,
            background: 'transparent',
            color: bothUp ? '#475569' : app.accent,
            fontWeight: 600,
            fontSize: 14,
            cursor: bothUp || starting === app.id ? 'default' : 'pointer',
            transition: 'all 0.2s',
          }}
        >
          {starting === app.id ? 'Iniciando…' : bothUp ? 'Corriendo' : 'Iniciar'}
        </button>
      </div>
    </div>
  )
}

function ConfigModal({ onClose }) {
  const [form, setForm] = useState({ groq: '', google: '', coingecko: '', afipsdk: '', maximosMode: 'online' })
  const [show, setShow] = useState({ groq: false, google: false, coingecko: false, afipsdk: false })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const [saveError, setSaveError] = useState(false)

  useEffect(() => {
    fetch('/api/config', { cache: 'no-store' })
      .then(r => r.json())
      .then(d => setForm({
        groq: d.groq || '',
        google: d.google || '',
        coingecko: d.coingecko || '',
        afipsdk: d.afipsdk || '',
        maximosMode: d.maximos_mode || 'online',
      }))
      .catch(() => {})
  }, [])

  const save = async () => {
    setSaving(true)
    setSaveError(false)
    try {
      const r = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, maximos_mode: form.maximosMode }),
      })
      if (r.ok) {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      } else {
        setSaveError(true)
      }
    } catch {
      setSaveError(true)
    }
    setSaving(false)
  }

  const Field = ({ id, label, placeholder }) => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 5, fontWeight: 500 }}>
        {label}
      </label>
      <div style={{ position: 'relative' }}>
        <input
          type={show[id] ? 'text' : 'password'}
          value={form[id]}
          onChange={e => setForm(f => ({ ...f, [id]: e.target.value }))}
          placeholder={placeholder}
          style={{
            width: '100%', boxSizing: 'border-box',
            background: '#0f172a', border: '1px solid #334155',
            borderRadius: 8, padding: '9px 42px 9px 12px',
            color: '#f8fafc', fontSize: 13, outline: 'none',
            fontFamily: 'monospace',
          }}
        />
        <button
          onClick={() => setShow(s => ({ ...s, [id]: !s[id] }))}
          style={{
            position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 13,
          }}
        >
          {show[id] ? '🙈' : '👁'}
        </button>
      </div>
    </div>
  )

  const Section = ({ title, color }) => (
    <div style={{ color: color || '#94a3b8', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12, marginTop: 4 }}>
      {title}
    </div>
  )

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        padding: '24px 16px',
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: '#1e293b', border: '1px solid #334155',
        borderRadius: 14, width: '100%', maxWidth: 460,
        boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
        display: 'flex', flexDirection: 'column',
        maxHeight: 'calc(100vh - 48px)',
        overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '24px 28px 20px', borderBottom: '1px solid #334155', flexShrink: 0 }}>
          <h3 style={{ color: '#f8fafc', fontSize: 18, fontWeight: 700, margin: 0 }}>Configuración</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>×</button>
        </div>

        <div className="modal-scroll" style={{ overflowY: 'auto', padding: '20px 28px', flex: 1 }}>
          <Section title="Inteligencia Artificial" color="#f59e0b" />
          <Field id="groq" label="Groq API Key" placeholder="gsk_..." />
          <Field id="google" label="Google (Gemini) API Key" placeholder="AIza..." />

          <div style={{ borderTop: '1px solid #334155', margin: '20px 0' }} />
          <Section title="Mercado" color="#60a5fa" />

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', color: '#94a3b8', fontSize: 12, marginBottom: 8, fontWeight: 500 }}>
              Fuente de precios (finanzas)
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              {[
                { id: 'online', label: 'Online', sub: 'Cloudflare Worker' },
                { id: 'local',  label: 'Local',  sub: 'localhost:8000' },
              ].map(opt => (
                <button
                  key={opt.id}
                  onClick={() => setForm(f => ({ ...f, maximosMode: opt.id }))}
                  style={{
                    flex: 1, padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
                    border: `1px solid ${form.maximosMode === opt.id ? '#60a5fa' : '#334155'}`,
                    background: form.maximosMode === opt.id ? 'rgba(96,165,250,0.12)' : 'transparent',
                    textAlign: 'left', transition: 'all 0.15s',
                  }}
                >
                  <div style={{ color: form.maximosMode === opt.id ? '#93c5fd' : '#f8fafc', fontSize: 13, fontWeight: 600 }}>{opt.label}</div>
                  <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{opt.sub}</div>
                </button>
              ))}
            </div>
          </div>

          <Field id="coingecko" label="CoinGecko API Key (demo)" placeholder="CG-..." />

          <div style={{ borderTop: '1px solid #334155', margin: '20px 0' }} />
          <Section title="Fiscal" color="#14b8a6" />
          <Field id="afipsdk" label="AFIP SDK Access Token" placeholder="sdk_..." />
        </div>

        <div style={{ padding: '16px 28px', borderTop: '1px solid #334155', display: 'flex', gap: 10, justifyContent: 'flex-end', alignItems: 'center', flexShrink: 0 }}>
          {saveError && <span style={{ color: '#f87171', fontSize: 12, marginRight: 'auto' }}>Error al guardar — verificá que el backend esté corriendo</span>}
          <button onClick={onClose} style={{ padding: '9px 20px', borderRadius: 8, border: '1px solid #334155', background: 'transparent', color: '#94a3b8', cursor: 'pointer', fontSize: 14 }}>
            Cancelar
          </button>
          <button
            onClick={save}
            disabled={saving}
            style={{ padding: '9px 24px', borderRadius: 8, border: 'none', background: '#f59e0b', color: '#0f172a', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}
          >
            {saved ? '✓ Guardado' : saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [status, setStatus] = useState({})
  const [showConfig, setShowConfig] = useState(false)
  const [starting, setStarting] = useState(null)

  const fetchStatus = useCallback(() => {
    fetch('/api/apps/status')
      .then(r => r.json())
      .then(d => setStatus(d))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchStatus()
    const id = setInterval(fetchStatus, 3000)
    return () => clearInterval(id)
  }, [fetchStatus])

  const handleOpen = port => window.open(`http://localhost:${port}`, '_blank')

  const handleStart = async appId => {
    setStarting(appId)
    try {
      await fetch(`/api/apps/${appId}/start`, { method: 'POST' })
      setTimeout(fetchStatus, 2500)
    } catch {}
    setTimeout(() => setStarting(null), 4000)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        background: '#1e293b',
        borderBottom: '1px solid #334155',
        padding: '0 32px',
        height: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#f8fafc', fontSize: 18, fontWeight: 700, letterSpacing: '-0.5px' }}>
            finanzas suite
          </span>
          <span style={{ color: '#475569', fontSize: 13 }}>— panel de control</span>
        </div>
        <button
          onClick={() => setShowConfig(true)}
          style={{
            background: '#334155', border: '1px solid #475569',
            borderRadius: 8, padding: '6px 14px',
            color: '#94a3b8', cursor: 'pointer', fontSize: 13, fontWeight: 500,
          }}
        >
          ⚙️ Configuración
        </button>
      </header>

      {/* Main */}
      <main style={{ flex: 1, padding: '48px 32px', maxWidth: 860, margin: '0 auto', width: '100%' }}>
        <p style={{ color: '#64748b', fontSize: 14, marginBottom: 36, marginTop: 0 }}>
          Seleccioná una aplicación para abrirla o iniciala si no está corriendo.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 20 }}>
          {APPS.map(app => (
            <AppCard
              key={app.id}
              app={app}
              status={status}
              onOpen={handleOpen}
              onStart={handleStart}
              starting={starting}
            />
          ))}
        </div>

        <div style={{ marginTop: 52, borderTop: '1px solid #1e293b', paddingTop: 28 }}>
          <p style={{ color: '#334155', fontSize: 12, textAlign: 'center' }}>
            maximos :8000/:5173 · finanzas :8001/:5174 · fiscal :8002/:5175 · launcher :8099/:5172
          </p>
        </div>
      </main>

      {showConfig && <ConfigModal onClose={() => setShowConfig(false)} />}
    </div>
  )
}

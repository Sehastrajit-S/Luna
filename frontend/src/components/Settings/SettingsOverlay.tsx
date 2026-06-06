import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, LayoutDashboard, Puzzle, CheckCircle, AlertCircle, RefreshCw, Save, ChevronDown, Eye, Download, Volume2, Keyboard, Mic, Camera, Sun, Moon } from 'lucide-react'
import { siAnthropic, siMistralai, siNvidia, siOllama } from 'simple-icons'
import { useStore } from '../../store'
import { api, streamMoondreamInstall, streamVoskInstall } from '../../api/client'
import { IntegrationStore, INTEGRATIONS } from './IntegrationStore'
import { getSelectedCameraDeviceId, setCameraDevice } from '../../services/cameraStream'

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = 'general' | 'controls' | 'integrations' | 'models' | 'providers'

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'general',      label: 'General',      icon: <LayoutDashboard size={14} /> },
  { id: 'controls',     label: 'Controls',     icon: <Keyboard size={14} /> },
  { id: 'integrations', label: 'Integrations', icon: <Puzzle size={14} /> },
  { id: 'models',       label: 'Models',       icon: <span className="text-[13px]">⚡</span> },
  { id: 'providers',    label: 'Providers',    icon: <CheckCircle size={14} /> },
]

// ── Model settings types ──────────────────────────────────────────────────────

const PROVIDERS_LIST = [
  { value: 'ollama',            label: 'Ollama (local)' },
  { value: 'anthropic',         label: 'Anthropic Claude' },
  { value: 'groq',              label: 'Groq' },
  { value: 'google',            label: 'Google Gemini' },
  { value: 'openai-compatible', label: 'OpenAI / Compatible' },
  { value: 'mistral',           label: 'Mistral AI' },
  { value: 'cohere',            label: 'Cohere' },
  { value: 'nvidia-nim',        label: 'NVIDIA NIM' },
]
const CODING_PROVIDERS = [{ value: '', label: 'Same as chat' }, ...PROVIDERS_LIST]

interface ProviderInfo { label: string; configured: boolean }
interface CodingSettings {
  llm_provider: string; coding_provider: string; effective_coding_provider: string
  coding_model: string; coding_max_iterations: number; coding_shell_timeout: number
  ollama_model: string; anthropic_model: string; groq_model: string; google_model: string
  openai_model: string; mistral_model: string; cohere_model: string; nvidia_nim_model: string
  providers: Record<string, ProviderInfo>
}

function modelKey(provider: string) {
  const m: Record<string, string> = {
    ollama: 'ollama_model', anthropic: 'anthropic_model', groq: 'groq_model',
    google: 'google_model', 'openai-compatible': 'openai_model',
    mistral: 'mistral_model', cohere: 'cohere_model', 'nvidia-nim': 'nvidia_nim_model',
  }
  return m[provider] ?? 'ollama_model'
}

// ── Small UI atoms ────────────────────────────────────────────────────────────

function SelectField({ value, onChange, options }: {
  value: string; onChange: (v: string) => void; options: { value: string; label: string }[]
}) {
  const [open, setOpen] = useState(false)
  const selected = options.find(o => o.value === value) ?? options[0]
  const SelectedIcon = selected?.value ? PROVIDER_ICONS[selected.value] : undefined

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none hover:border-luna-primary/40 transition-colors"
      >
        <span className="flex items-center gap-2.5">
          {SelectedIcon && <span className="shrink-0 scale-75 -ml-1"><SelectedIcon /></span>}
          <span>{selected?.label ?? value}</span>
        </span>
        <ChevronDown size={13} className={`text-luna-dim transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.1 }}
            className="absolute z-50 mt-1 w-full bg-luna-surface border border-luna-border rounded-xl shadow-xl overflow-hidden"
          >
            {options.map(o => {
              const Icon = PROVIDER_ICONS[o.value]
              return (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => { onChange(o.value); setOpen(false) }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-left transition-colors hover:bg-luna-card ${o.value === value ? 'text-luna-accent bg-luna-primary/10' : 'text-luna-text'}`}
                >
                  {Icon
                    ? <span className="shrink-0 scale-75 -ml-1"><Icon /></span>
                    : <div className="w-5 h-5 shrink-0" />
                  }
                  {o.label}
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function OllamaModelPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [models, setModels] = useState<string[]>([])
  const [ollamaRunning, setOllamaRunning] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)

  const load = () => {
    setLoading(true)
    const base = window.electronAPI?.apiBase ?? ''
    fetch(`${base}/api/coding/status`)
      .then(r => r.json())
      .then(data => {
        setOllamaRunning(data.ollama_running ?? false)
        setModels(data.available_models ?? [])
      })
      .catch(() => { setOllamaRunning(null); setModels([]) })
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const refreshBtn = (
    <button onClick={load} disabled={loading}
      className="p-2 rounded-lg border border-luna-border bg-luna-card hover:bg-luna-surface text-luna-dim transition-colors shrink-0">
      <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
    </button>
  )

  if (!loading && ollamaRunning === false) {
    return (
      <div className="space-y-2">
        <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs">
          <AlertCircle size={13} className="shrink-0 mt-0.5" />
          <span>Ollama isn't running. Start it, then click refresh.</span>
          {refreshBtn}
        </div>
        <input className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
          value={value} onChange={e => onChange(e.target.value)} placeholder="e.g. qwen2.5:7b" />
      </div>
    )
  }

  if (!loading && ollamaRunning === true && models.length === 0) {
    return (
      <div className="space-y-2">
        <div className="flex items-start gap-2 p-3 rounded-lg bg-luna-primary/10 border border-luna-primary/30 text-luna-accent text-xs">
          <AlertCircle size={13} className="shrink-0 mt-0.5" />
          <span>No models installed. Run in a terminal: <code className="font-mono bg-luna-surface px-1 rounded">ollama pull qwen2.5:7b</code>, then refresh.</span>
          {refreshBtn}
        </div>
        <input className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
          value={value} onChange={e => onChange(e.target.value)} placeholder="e.g. qwen2.5:7b" />
      </div>
    )
  }

  if (models.length > 0) {
    return (
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <select value={value} onChange={e => onChange(e.target.value)}
            className="w-full appearance-none bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text pr-8 focus:outline-none focus:border-luna-primary/60">
            {!models.includes(value) && <option value={value}>{value}</option>}
            {models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-luna-dim pointer-events-none" />
        </div>
        {refreshBtn}
      </div>
    )
  }

  return (
    <input className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
      value={value} onChange={e => onChange(e.target.value)} placeholder="e.g. qwen2.5:7b" />
  )
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`relative w-10 h-5 rounded-full overflow-hidden transition-colors shrink-0 ${on ? 'bg-luna-primary/70' : 'bg-luna-border'}`}>
      <span className={`absolute top-[2px] w-4 h-4 rounded-full bg-white shadow transition-all duration-200 ${on ? 'left-[22px]' : 'left-[2px]'}`} />
    </button>
  )
}

// ── Tab contents ──────────────────────────────────────────────────────────────

function GeneralTab() {
  const { layoutModeEnabled, setLayoutModeEnabled, devModeEnabled, setDevModeEnabled, theme, setTheme } = useStore()
  return (
    <div className="max-w-xl space-y-3">
      <div className="flex items-center justify-between py-3 px-4 rounded-xl bg-luna-card border border-luna-border">
        <div className="flex items-center gap-3">
          {theme === 'light' ? <Sun size={14} className="text-luna-dim" /> : <Moon size={14} className="text-luna-dim" />}
          <div>
            <p className="text-sm text-luna-text">Light mode</p>
            <p className="text-[11px] text-luna-dim">Switch to a lighter colour scheme</p>
          </div>
        </div>
        <Toggle on={theme === 'light'} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} />
      </div>

      <div className="flex items-center justify-between py-3 px-4 rounded-xl bg-luna-card border border-luna-border">
        <div>
          <p className="text-sm text-luna-text">Layout mode</p>
          <p className="text-[11px] text-luna-dim">Shows a mode switcher in the title bar (Jarvis → Classic → Luna)</p>
        </div>
        <Toggle on={layoutModeEnabled} onClick={() => setLayoutModeEnabled(!layoutModeEnabled)} />
      </div>

      <div className="flex items-center justify-between py-3 px-4 rounded-xl bg-luna-card border border-luna-border">
        <div>
          <p className="text-sm text-luna-text">Dev mode</p>
          <p className="text-[11px] text-luna-dim">Enables the orb button in the title bar to switch modes</p>
        </div>
        <Toggle on={devModeEnabled} onClick={() => setDevModeEnabled(!devModeEnabled)} />
      </div>
    </div>
  )
}

function IntegrationsTab() {
  const [configured, setConfigured] = useState<Set<string>>(new Set())

  useEffect(() => {
    window.electronAPI?.getEnvConfig?.().then(res => {
      if (!res?.ok || !res.config) return
      const cfg = res.config
      const done = new Set<string>()
      for (const intg of INTEGRATIONS) {
        if (intg.fields.some(f => !!cfg[f.key])) done.add(intg.id)
      }
      setConfigured(done)
    })
  }, [])

  return (
    <IntegrationStore
      configured={configured}
      onConfigured={id => setConfigured(prev => new Set([...prev, id]))}
    />
  )
}

function MoondreamSection() {
  const [status, setStatus] = useState<{ moondream_installed: boolean; ollama_available: boolean } | null>(null)
  const [installing, setInstalling] = useState(false)
  const [lines, setLines]   = useState<string[]>([])
  const [done, setDone]     = useState(false)
  const [installErr, setInstallErr] = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => { api.getVisionStatus().then(setStatus).catch(() => {}) }, [done])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lines])

  const install = async () => {
    setInstalling(true); setLines([]); setDone(false); setInstallErr('')
    try {
      for await (const chunk of streamMoondreamInstall()) {
        if (chunk.error) { setInstallErr(chunk.error); break }
        if (chunk.line)  setLines(prev => [...prev.slice(-60), chunk.line!])
        if (chunk.done)  { setDone(true); break }
      }
    } catch (e: any) {
      setInstallErr(String(e?.message ?? e))
    } finally {
      setInstalling(false)
    }
  }

  const installed   = status?.moondream_installed
  const ollamaReady = status?.ollama_available

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <Eye size={14} className="text-luna-dim" />
        <h3 className="text-luna-text font-semibold text-sm">Vision Model</h3>
      </div>
      <div className="flex items-center justify-between py-3 px-4 rounded-xl bg-luna-card border border-luna-border">
        <div className="flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full ${installed ? 'bg-green-400' : 'bg-luna-dim'}`} />
          <div>
            <p className="text-sm text-luna-text">moondream</p>
            <p className="text-[11px] text-luna-dim">
              {!ollamaReady ? 'Ollama not reachable' : installed ? 'Ready — Luna can see your screen' : 'Not installed — vision features inactive'}
            </p>
          </div>
        </div>
        {!installed && ollamaReady && (
          <button
            onClick={install}
            disabled={installing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-xs font-medium hover:bg-luna-primary/30 transition-colors disabled:opacity-50"
          >
            <Download size={11} />
            {installing ? 'Installing…' : 'Install'}
          </button>
        )}
      </div>

      {(installing || lines.length > 0) && (
        <div
          ref={logRef}
          className="rounded-lg bg-black/40 border border-luna-border p-3 h-28 overflow-y-auto font-mono text-[10px] text-luna-dim space-y-0.5"
        >
          {lines.map((l, i) => <p key={i}>{l}</p>)}
          {installing && <p className="text-luna-primary animate-pulse">▌</p>}
        </div>
      )}
      {done && !installErr && <p className="text-green-400 text-xs flex items-center gap-1.5"><CheckCircle size={12} />moondream installed — vision is now active</p>}
      {installErr && <p className="text-red-400 text-xs flex items-center gap-1.5"><AlertCircle size={12} />{installErr}</p>}
    </section>
  )
}

function ModelsTab() {
  const [data, setData]     = useState<CodingSettings | null>(null)
  const [form, setForm]     = useState<Partial<CodingSettings>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved]   = useState(false)
  const [err, setErr]       = useState('')

  const load = () => {
    setErr('')
    api.getCodingSettings().then(s => { setData(s); setForm(s) }).catch(() => setErr('Failed to load — is the backend running?'))
  }

  useEffect(() => { load() }, [])

  const set = (k: string, v: unknown) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    setSaving(true); setErr('')
    try { await api.updateCodingSettings(form as Record<string, unknown>); setSaved(true); setTimeout(() => setSaved(false), 2500) }
    catch { setErr('Save failed.') }
    finally { setSaving(false) }
  }

  if (!data) return (
    <div className="flex flex-col items-start gap-3">
      <p className="text-luna-dim text-sm">{err || 'Loading…'}</p>
      {err && <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-luna-card border border-luna-border text-luna-dim text-xs hover:text-luna-text transition-colors"><RefreshCw size={11} />Retry</button>}
    </div>
  )

  const chatProv     = (form.llm_provider    ?? data.llm_provider    ?? 'ollama') as string
  const codingRaw    = (form.coding_provider ?? data.coding_provider ?? '') as string
  const effectiveCod = codingRaw || chatProv
  const chatMK       = modelKey(chatProv)
  const codeMK       = modelKey(effectiveCod)

  return (
    <div className="max-w-xl space-y-6">
      <MoondreamSection />

      <section className="space-y-4">
        <h3 className="text-luna-text font-semibold text-sm">Chat Model</h3>
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Provider</label>
          <SelectField value={chatProv} onChange={v => set('llm_provider', v)} options={PROVIDERS_LIST} />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Model</label>
          {chatProv === 'ollama'
            ? <OllamaModelPicker value={(form as any)[chatMK] ?? ''} onChange={v => set(chatMK, v)} />
            : <input className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
                value={(form as any)[chatMK] ?? ''} onChange={e => set(chatMK, e.target.value)} />
          }
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-luna-text font-semibold text-sm">Coding Agent</h3>
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Provider</label>
          <SelectField value={codingRaw} onChange={v => set('coding_provider', v)} options={CODING_PROVIDERS} />
          {!codingRaw && <p className="text-[11px] text-luna-dim">Using chat provider: <span className="text-luna-text">{chatProv}</span></p>}
        </div>
        {effectiveCod === 'ollama' && (
          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Model (Ollama)</label>
            <OllamaModelPicker value={(form.coding_model ?? data.coding_model) as string} onChange={v => set('coding_model', v)} />
          </div>
        )}
        {effectiveCod !== 'ollama' && effectiveCod !== chatProv && (
          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Model</label>
            <input className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
              value={(form as any)[codeMK] ?? ''} onChange={e => set(codeMK, e.target.value)} />
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Max iterations</label>
            <input type="number" min={1} max={50}
              className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
              value={(form.coding_max_iterations ?? data.coding_max_iterations) as number}
              onChange={e => set('coding_max_iterations', parseInt(e.target.value, 10) || 20)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Shell timeout (s)</label>
            <input type="number" min={10} max={600}
              className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
              value={(form.coding_shell_timeout ?? data.coding_shell_timeout) as number}
              onChange={e => set('coding_shell_timeout', parseInt(e.target.value, 10) || 120)} />
          </div>
        </div>
      </section>

      <div className="flex items-center gap-3 pt-2">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-sm font-medium hover:bg-luna-primary/30 transition-colors disabled:opacity-50">
          <Save size={13} /> {saving ? 'Saving…' : 'Save Changes'}
        </button>
        {saved && <span className="flex items-center gap-1.5 text-green-400 text-xs"><CheckCircle size={13} />Saved</span>}
        {err && <span className="flex items-center gap-1.5 text-red-400 text-xs"><AlertCircle size={13} />{err}</span>}
      </div>
    </div>
  )
}

// ── Provider logos ────────────────────────────────────────────────────────────

function SiIcon({ icon, size = 28, bg, iconColor, rounded = true }: { icon: { path: string; hex: string }; size?: number; bg?: string; iconColor?: string; rounded?: boolean }) {
  const brandFill = `#${icon.hex}`
  const fill = iconColor ?? brandFill
  const padding = Math.round(size * 0.2)
  const inner = size - padding * 2
  const defaultBg = icon.hex === '000000' || icon.hex === '191919' ? '#2a2a2a' : `${brandFill}18`
  return (
    <span
      className={`inline-flex items-center justify-center shrink-0 ${rounded ? 'rounded-lg' : ''}`}
      style={{ width: size, height: size, background: bg ?? defaultBg, border: `1px solid ${iconColor ? bg + '60' : brandFill + '30'}` }}
    >
      <svg viewBox="0 0 24 24" width={inner} height={inner} fill={fill}>
        <path d={icon.path} />
      </svg>
    </span>
  )
}

// Icons sourced from simple-icons where available; inline SVG for the rest
const GroqIcon = () => (
  <span className="inline-flex items-center justify-center rounded-lg shrink-0" style={{ width: 28, height: 28, background: '#F55D3E18', border: '1px solid #F55D3E30' }}>
    <svg viewBox="0 0 24 24" width={18} height={18} fill="#F55D3E">
      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 4a6 6 0 1 1 0 12A6 6 0 0 1 12 6zm0 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm1 1v3.586l2.207 2.207-1.414 1.414L11 13.414V9h2z"/>
    </svg>
  </span>
)

const OpenAIIcon = () => (
  <span className="inline-flex items-center justify-center rounded-lg shrink-0" style={{ width: 28, height: 28, background: '#10a37f18', border: '1px solid #10a37f30' }}>
    <svg viewBox="0 0 24 24" width={18} height={18} fill="#10a37f">
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0L4.01 14.3A4.501 4.501 0 0 1 2.34 7.895zm16.597 3.855l-5.843-3.372 2.019-1.168a.076.076 0 0 1 .072 0l4.008 2.313a4.476 4.476 0 0 1-.692 8.085V11.47a.767.767 0 0 0-.564-.72zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.003-2.309a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08-4.778 2.758a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
    </svg>
  </span>
)

const CohereIcon = () => (
  <span className="inline-flex items-center justify-center rounded-lg shrink-0" style={{ width: 28, height: 28, background: '#D18EE218', border: '1px solid #D18EE230' }}>
    <svg viewBox="0 0 24 24" width={18} height={18} fill="#D18EE2">
      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.5 6.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM9.5 9a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zm2.5 5.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z"/>
    </svg>
  </span>
)

const GoogleIcon = () => (
  <span className="inline-flex items-center justify-center rounded-lg shrink-0" style={{ width: 28, height: 28, background: '#4285F418', border: '1px solid #4285F430' }}>
    <svg viewBox="0 0 24 24" width={18} height={18}>
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  </span>
)

const PROVIDER_ICONS: Record<string, React.ComponentType> = {
  ollama:              () => <SiIcon icon={siOllama} bg="#ffffff" />,
  anthropic:           () => <SiIcon icon={siAnthropic} bg="#CC785C" iconColor="#ffffff" />,
  groq:                GroqIcon,
  google:              GoogleIcon,
  'openai-compatible': OpenAIIcon,
  mistral:             () => <SiIcon icon={siMistralai} />,
  cohere:              CohereIcon,
  'nvidia-nim':        () => <SiIcon icon={siNvidia} />,
}

// env var names + extra fields per provider
// Keys MUST match the lowercase keys used in .env and returned by getEnvConfig
const PROVIDER_FIELDS: Record<string, { envKey?: string; envKeyLabel?: string; urlKey?: string; urlLabel?: string; urlPlaceholder?: string; modelPlaceholder?: string }> = {
  ollama:             { urlKey: 'ollama_base_url', urlLabel: 'Base URL', urlPlaceholder: 'http://localhost:11434', modelPlaceholder: 'e.g. qwen2.5:7b' },
  anthropic:          { envKey: 'anthropic_api_key', envKeyLabel: 'API Key', modelPlaceholder: 'e.g. claude-3-5-sonnet-20241022' },
  groq:               { envKey: 'groq_api_key', envKeyLabel: 'API Key', modelPlaceholder: 'e.g. llama-3.3-70b-versatile' },
  google:             { envKey: 'google_api_key', envKeyLabel: 'API Key', modelPlaceholder: 'e.g. gemini-2.0-flash-exp' },
  'openai-compatible':{ envKey: 'openai_api_key', envKeyLabel: 'API Key', urlKey: 'openai_base_url', urlLabel: 'Base URL (optional)', urlPlaceholder: 'https://api.openai.com/v1', modelPlaceholder: 'e.g. gpt-4o' },
  mistral:            { envKey: 'mistral_api_key', envKeyLabel: 'API Key', modelPlaceholder: 'e.g. mistral-large-latest' },
  cohere:             { envKey: 'cohere_api_key', envKeyLabel: 'API Key', modelPlaceholder: 'e.g. command-r-plus' },
  'nvidia-nim':       { envKey: 'nvidia_nim_api_key', envKeyLabel: 'API Key', urlKey: 'nvidia_nim_base_url', urlLabel: 'Base URL (optional)', urlPlaceholder: 'https://integrate.api.nvidia.com/v1', modelPlaceholder: 'e.g. meta/llama-3.1-70b-instruct' },
}

function ProviderCard({ provKey, info, envCfg, settings, onSaved }: {
  provKey: string
  info: ProviderInfo
  envCfg: Record<string, string>
  settings: CodingSettings
  onSaved: (envPatch: Record<string, string>, settingsPatch: Record<string, unknown>) => void
}) {
  const [open, setOpen]     = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved]   = useState(false)
  const [err, setErr]       = useState('')

  const spec      = PROVIDER_FIELDS[provKey] ?? {}
  const mk        = modelKey(provKey)

  const [apiKey,   setApiKey]   = useState(spec.envKey  ? (envCfg[spec.envKey]  ?? '') : '')
  const [baseUrl,  setBaseUrl]  = useState(spec.urlKey  ? (envCfg[spec.urlKey]  ?? '') : '')
  const [model,    setModel]    = useState((settings as any)[mk] ?? '')

  const save = async () => {
    setSaving(true); setErr('')
    try {
      const envPatch: Record<string, string> = {}
      if (spec.envKey) envPatch[spec.envKey] = apiKey
      if (spec.urlKey) envPatch[spec.urlKey] = baseUrl

      if (Object.keys(envPatch).length) {
        const merged = { ...envCfg, ...envPatch }
        const res = await window.electronAPI?.saveEnvConfig?.(merged)
        if (!res?.ok) throw new Error(res?.error ?? 'Failed to save env')
      }

      const settingsPatch: Record<string, unknown> = {}
      if (model) settingsPatch[mk] = model
      if (Object.keys(settingsPatch).length) {
        await api.updateCodingSettings(settingsPatch)
      }

      onSaved(envPatch, settingsPatch)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e: any) {
      setErr(e.message ?? 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={`rounded-xl border transition-colors ${open ? 'border-luna-primary/30 bg-luna-card' : 'border-luna-border/50 bg-luna-card'}`}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between py-3 px-4 text-left"
      >
        <div className="flex items-center gap-3">
          {(() => { const Icon = PROVIDER_ICONS[provKey]; return Icon ? <Icon /> : <div className="w-7 h-7 rounded-lg bg-luna-surface border border-luna-border" /> })()}
          <span className="text-sm text-luna-text font-medium">{info.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[11px] px-2 py-0.5 rounded-full border ${
            info.configured ? 'text-green-400 border-green-400/30 bg-green-400/10' : 'text-luna-dim border-luna-border'
          }`}>
            {info.configured ? 'configured' : 'not set'}
          </span>
          <ChevronDown size={13} className={`text-luna-dim transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3 border-t border-luna-border/40 pt-3">
              {spec.envKey && (
                <div className="space-y-1.5">
                  <label className="text-[11px] text-luna-dim font-medium uppercase tracking-wide">{spec.envKeyLabel}</label>
                  <input
                    type="password"
                    className="w-full bg-luna-surface border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="sk-…"
                    autoComplete="off"
                  />
                </div>
              )}
              {spec.urlKey && (
                <div className="space-y-1.5">
                  <label className="text-[11px] text-luna-dim font-medium uppercase tracking-wide">{spec.urlLabel}</label>
                  <input
                    className="w-full bg-luna-surface border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
                    value={baseUrl}
                    onChange={e => setBaseUrl(e.target.value)}
                    placeholder={spec.urlPlaceholder}
                  />
                </div>
              )}
              <div className="space-y-1.5">
                <label className="text-[11px] text-luna-dim font-medium uppercase tracking-wide">Model</label>
                {provKey === 'ollama'
                  ? <OllamaModelPicker value={model} onChange={setModel} />
                  : <input
                      className="w-full bg-luna-surface border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
                      value={model}
                      onChange={e => setModel(e.target.value)}
                      placeholder={spec.modelPlaceholder}
                    />
                }
              </div>
              <div className="flex items-center gap-3 pt-1">
                <button onClick={save} disabled={saving}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-xs font-medium hover:bg-luna-primary/30 transition-colors disabled:opacity-50">
                  <Save size={11} /> {saving ? 'Saving…' : 'Save'}
                </button>
                {saved && <span className="flex items-center gap-1 text-green-400 text-[11px]"><CheckCircle size={11} />Saved</span>}
                {err   && <span className="flex items-center gap-1 text-red-400 text-[11px]"><AlertCircle size={11} />{err}</span>}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function ProvidersTab() {
  const [data,   setData]   = useState<CodingSettings | null>(null)
  const [envCfg, setEnvCfg] = useState<Record<string, string>>({})
  const [err,    setErr]    = useState('')

  const load = () => {
    setErr('')
    api.getCodingSettings().then(setData).catch(() => setErr('Failed to load — is the backend running?'))
    window.electronAPI?.getEnvConfig?.().then(res => {
      if (res?.ok && res.config) setEnvCfg(res.config)
    })
  }

  useEffect(() => { load() }, [])

  const handleSaved = (envPatch: Record<string, string>, settingsPatch: Record<string, unknown>) => {
    setEnvCfg(prev => ({ ...prev, ...envPatch }))
    setData(prev => prev ? { ...prev, ...settingsPatch } as CodingSettings : prev)
  }

  if (!data) return (
    <div className="flex flex-col items-start gap-3">
      <p className="text-luna-dim text-sm">{err || 'Loading…'}</p>
      {err && <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-luna-card border border-luna-border text-luna-dim text-xs hover:text-luna-text transition-colors"><RefreshCw size={11} />Retry</button>}
    </div>
  )

  return (
    <div className="max-w-xl space-y-4">
      <p className="text-luna-dim text-xs">Click any provider to expand and configure its API key and default model.</p>
      <div className="space-y-2">
        {Object.entries(data.providers).map(([key, info]) => (
          <ProviderCard
            key={key}
            provKey={key}
            info={info}
            envCfg={envCfg}
            settings={data}
            onSaved={handleSaved}
          />
        ))}
      </div>
    </div>
  )
}

// ── Vosk install section ──────────────────────────────────────────────────────

function VoskSection() {
  const [status, setStatus]       = useState<{ vosk_ready: boolean; vosk_package: boolean } | null>(null)
  const [installing, setInstalling] = useState(false)
  const [lines, setLines]         = useState<string[]>([])
  const [done, setDone]           = useState(false)
  const [installErr, setInstallErr] = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => { api.getVoskStatus().then(setStatus).catch(() => {}) }, [done])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [lines])

  const install = async () => {
    setInstalling(true); setLines([]); setDone(false); setInstallErr('')
    try {
      for await (const chunk of streamVoskInstall()) {
        if (chunk.error) { setInstallErr(chunk.error); break }
        if (chunk.line)  setLines(prev => [...prev.slice(-60), chunk.line!])
        if (chunk.done)  { setDone(true); break }
      }
    } catch (e: any) {
      setInstallErr(String(e?.message ?? e))
    } finally {
      setInstalling(false)
    }
  }

  const voskReady = status?.vosk_ready

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Mic size={14} className="text-luna-dim" />
        <h3 className="text-luna-text font-semibold text-sm">Wake Word Model (Vosk)</h3>
      </div>
      <div className="flex items-center justify-between py-3 px-4 rounded-xl bg-luna-card border border-luna-border">
        <div className="flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full shrink-0 ${voskReady ? 'bg-green-400' : 'bg-luna-dim'}`} />
          <div>
            <p className="text-sm text-luna-text">Vosk offline model</p>
            <p className="text-[11px] text-luna-dim">
              {voskReady ? 'Ready — say "Luna" to activate voice' : 'Not installed — voice activation unavailable (~40 MB)'}
            </p>
          </div>
        </div>
        {!voskReady && (
          <button
            onClick={install}
            disabled={installing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-xs font-medium hover:bg-luna-primary/30 transition-colors disabled:opacity-50 shrink-0"
          >
            <Download size={11} />
            {installing ? 'Installing…' : 'Install'}
          </button>
        )}
      </div>
      {(installing || lines.length > 0) && (
        <div
          ref={logRef}
          className="rounded-lg bg-black/40 border border-luna-border p-3 h-28 overflow-y-auto font-mono text-[10px] text-luna-dim space-y-0.5"
        >
          {lines.map((l, i) => <p key={i}>{l}</p>)}
          {installing && <p className="text-luna-primary animate-pulse">▌</p>}
        </div>
      )}
      {done && !installErr && <p className="text-green-400 text-xs flex items-center gap-1.5"><CheckCircle size={12} />Vosk installed — restart Luna to activate voice</p>}
      {installErr && <p className="text-red-400 text-xs flex items-center gap-1.5"><AlertCircle size={12} />{installErr}</p>}
    </section>
  )
}

// ── Controls tab ─────────────────────────────────────────────────────────────

function DeviceSelect({ value, onChange, options, disabled }: {
  value: string; onChange: (v: string) => void
  options: { id: string; name: string }[]; disabled?: boolean
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      disabled={disabled || options.length === 0}
      className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text
        focus:outline-none focus:border-luna-primary/60 disabled:opacity-40 disabled:cursor-not-allowed
        appearance-none cursor-pointer"
      style={{ backgroundImage: 'none' }}
    >
      {options.length === 0
        ? <option value="">No devices found</option>
        : options.map(o => <option key={o.id} value={o.id}>{o.name}</option>)
      }
    </select>
  )
}

function ControlsTab() {
  const base = window.electronAPI?.apiBase ?? ''

  const [outDevices, setOutDevices] = useState<{ id: string; name: string }[]>([])
  const [outCurrent, setOutCurrent] = useState('')
  const [outBusy, setOutBusy]       = useState(false)

  const [inDevices, setInDevices]   = useState<{ id: string; name: string }[]>([])
  const [inCurrent, setInCurrent]   = useState('')
  const [inBusy, setInBusy]         = useState(false)

  const [camDevices, setCamDevices] = useState<{ id: string; name: string }[]>([])
  const [camCurrent, setCamCurrent] = useState(getSelectedCameraDeviceId() ?? '')

  useEffect(() => {
    fetch(`${base}/api/system/audio-devices`).then(r => r.json())
      .then(d => { setOutDevices(d.devices ?? []); setOutCurrent(d.current ?? '') }).catch(() => {})
    fetch(`${base}/api/system/audio-input-devices`).then(r => r.json())
      .then(d => { setInDevices(d.devices ?? []); setInCurrent(d.current ?? '') }).catch(() => {})
    navigator.mediaDevices.enumerateDevices().then(devs => {
      const cams = devs.filter(d => d.kind === 'videoinput').map(d => ({ id: d.deviceId, name: d.label || `Camera ${d.deviceId.slice(0, 6)}` }))
      setCamDevices(cams)
      if (!getSelectedCameraDeviceId() && cams.length > 0) setCamCurrent(cams[0].id)
    }).catch(() => {})
  }, [base])

  const switchOutput = async (id: string) => {
    setOutCurrent(id); setOutBusy(true)
    try {
      await fetch(`${base}/api/system/audio-device`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ device_id: id }) })
    } catch {}
    setOutBusy(false)
  }

  const switchInput = async (id: string) => {
    setInCurrent(id); setInBusy(true)
    try {
      await fetch(`${base}/api/system/audio-input-device`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ device_id: id }) })
    } catch {}
    setInBusy(false)
  }

  const switchCamera = (id: string) => {
    setCamCurrent(id)
    setCameraDevice(id || null)
  }

  const SHORTCUTS = [
    { keys: ['Ctrl', 'Alt', 'L'], desc: 'Show / focus Luna' },
    { keys: ['F11'],              desc: 'Toggle fullscreen' },
    { keys: ['Esc'],              desc: 'Close settings / overlays' },
  ]

  return (
    <div className="max-w-xl space-y-8">
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Volume2 size={14} className="text-luna-dim" />
          <h3 className="text-luna-text font-semibold text-sm">Audio Output</h3>
          {outBusy && <span className="text-[10px] text-luna-dim animate-pulse">switching…</span>}
        </div>
        <DeviceSelect value={outCurrent} onChange={switchOutput} options={outDevices} disabled={outBusy} />
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Mic size={14} className="text-luna-dim" />
          <h3 className="text-luna-text font-semibold text-sm">Microphone</h3>
          {inBusy && <span className="text-[10px] text-luna-dim animate-pulse">switching…</span>}
        </div>
        <DeviceSelect value={inCurrent} onChange={switchInput} options={inDevices} disabled={inBusy} />
      </section>

      <VoskSection />

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Camera size={14} className="text-luna-dim" />
          <h3 className="text-luna-text font-semibold text-sm">Camera</h3>
        </div>
        <DeviceSelect value={camCurrent} onChange={switchCamera} options={camDevices} />
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Keyboard size={14} className="text-luna-dim" />
          <h3 className="text-luna-text font-semibold text-sm">Keyboard Shortcuts</h3>
        </div>
        <div className="space-y-1.5">
          {SHORTCUTS.map(s => (
            <div key={s.desc} className="flex items-center justify-between px-4 py-3 rounded-xl bg-luna-card border border-luna-border">
              <span className="text-sm text-luna-dim">{s.desc}</span>
              <div className="flex items-center gap-1">
                {s.keys.map((k, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 rounded bg-luna-surface border border-luna-border text-[10px] font-mono text-luna-text">{k}</kbd>
                    {i < s.keys.length - 1 && <span className="text-luna-dim text-[10px]">+</span>}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

// ── Main overlay ──────────────────────────────────────────────────────────────

export function SettingsOverlay() {
  const { settingsOpen, closeSettings } = useStore()
  const [tab, setTab] = useState<Tab>('general')

  useEffect(() => {
    if (!settingsOpen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeSettings() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [settingsOpen, closeSettings])

  return (
    <AnimatePresence>
      {settingsOpen && (
        <motion.div
          className="fixed inset-0 z-50 bg-luna-bg flex flex-col"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          {/* Header bar */}
          <div className="h-12 flex items-center justify-between px-6 border-b border-luna-border shrink-0 bg-luna-surface">
            <div className="flex items-center gap-3">
              <img src={`${import.meta.env.BASE_URL}images/logo.svg`} alt="" className="w-5 h-5 opacity-70" />
              <span className="text-sm font-semibold text-luna-text tracking-wide">Settings</span>
            </div>
            <button
              onClick={closeSettings}
              className="flex items-center gap-1.5 text-luna-dim hover:text-luna-text transition-colors text-xs"
            >
              <X size={14} />
              <span className="opacity-60">Esc</span>
            </button>
          </div>

          {/* Body */}
          <div className="flex flex-1 overflow-hidden">
            {/* Left nav */}
            <div className="w-52 border-r border-luna-border bg-luna-surface shrink-0 p-3 space-y-0.5">
              {TABS.map(t => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all ${
                    tab === t.id
                      ? 'bg-luna-primary/15 text-luna-accent border border-luna-primary/25'
                      : 'text-luna-muted hover:bg-luna-card hover:text-luna-text'
                  }`}
                >
                  <span className={tab === t.id ? 'text-luna-accent' : 'text-luna-dim'}>{t.icon}</span>
                  {t.label}
                </button>
              ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              <AnimatePresence mode="wait">
                <motion.div
                  key={tab}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.12 }}
                  className="p-8"
                >
                  {tab === 'general'      && <GeneralTab />}
                  {tab === 'controls'     && <ControlsTab />}
                  {tab === 'integrations' && <IntegrationsTab />}
                  {tab === 'models'       && <ModelsTab />}
                  {tab === 'providers'    && <ProvidersTab />}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

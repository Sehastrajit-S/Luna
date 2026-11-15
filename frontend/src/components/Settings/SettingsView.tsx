import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useStore } from '../../store'
import { CheckCircle, AlertCircle, RefreshCw, Save, ChevronDown, Mic } from 'lucide-react'

const PROVIDERS = [
  { value: 'ollama',            label: 'Ollama (local)' },
  { value: 'anthropic',         label: 'Anthropic Claude' },
  { value: 'groq',              label: 'Groq' },
  { value: 'google',            label: 'Google Gemini' },
  { value: 'openai-compatible', label: 'OpenAI / Compatible' },
  { value: 'mistral',           label: 'Mistral AI' },
  { value: 'cohere',            label: 'Cohere' },
  { value: 'nvidia-nim',        label: 'NVIDIA NIM' },
]

const CODING_PROVIDERS = [
  { value: '', label: 'Same as chat' },
  ...PROVIDERS,
]

const TTS_PROVIDERS = [
  { value: 'edge',       label: 'Local (edge-tts — free)' },
  { value: 'elevenlabs', label: 'ElevenLabs (cloud)' },
]

const STT_PROVIDERS = [
  { value: 'whisper',    label: 'Local (Whisper — free)' },
  { value: 'elevenlabs', label: 'ElevenLabs Scribe (cloud)' },
]

interface ProviderInfo {
  label: string
  configured: boolean
}

interface CodingSettings {
  llm_provider: string
  coding_provider: string
  effective_coding_provider: string
  coding_model: string
  coding_max_iterations: number
  coding_shell_timeout: number
  ollama_model: string
  anthropic_model: string
  groq_model: string
  google_model: string
  openai_model: string
  mistral_model: string
  cohere_model: string
  nvidia_nim_model: string
  tts_provider: string
  stt_provider: string
  elevenlabs_voice_id: string
  elevenlabs_tts_model: string
  elevenlabs_stt_model: string
  providers: Record<string, ProviderInfo>
  voice_providers: Record<string, ProviderInfo>
}

function modelFieldFor(provider: string, s: CodingSettings): { key: string; value: string } {
  const map: Record<string, string> = {
    ollama: 'ollama_model',
    anthropic: 'anthropic_model',
    groq: 'groq_model',
    google: 'google_model',
    'openai-compatible': 'openai_model',
    mistral: 'mistral_model',
    cohere: 'cohere_model',
    'nvidia-nim': 'nvidia_nim_model',
  }
  const key = map[provider] ?? 'ollama_model'
  return { key, value: (s as any)[key] ?? '' }
}

function Select({
  value, onChange, options,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full appearance-none bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text pr-8 focus:outline-none focus:border-luna-primary/60"
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-luna-dim pointer-events-none" />
    </div>
  )
}

function OllamaModelPicker({
  value, onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const load = () => {
    setLoading(true)
    api.getCodingModels()
      .then(r => setModels(r.models ?? []))
      .catch(() => setModels([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (models.length === 0) {
    return (
      <input
        className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="e.g. qwen2.5-coder:7b"
      />
    )
  }

  return (
    <div className="flex gap-2">
      <div className="flex-1 relative">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full appearance-none bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text pr-8 focus:outline-none focus:border-luna-primary/60"
        >
          {!models.includes(value) && <option value={value}>{value}</option>}
          {models.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-luna-dim pointer-events-none" />
      </div>
      <button
        onClick={load}
        disabled={loading}
        className="p-2 rounded-lg border border-luna-border bg-luna-card hover:bg-luna-surface text-luna-dim hover:text-luna-text transition-colors"
        title="Refresh models"
      >
        <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
      </button>
    </div>
  )
}

function ElevenLabsVoicePicker({
  value, onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const [voices, setVoices] = useState<{ voice_id: string; name: string }[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    api.getElevenLabsVoices()
      .then(r => setVoices(r.voices ?? []))
      .catch(() => setError('Could not fetch voices — check the ElevenLabs API key'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (voices.length === 0) {
    return (
      <div className="space-y-1">
        <div className="flex gap-2">
          <input
            className="flex-1 bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder="Voice ID, e.g. 21m00Tcm4TlvDq8ikWAM"
          />
          <button
            onClick={load}
            disabled={loading}
            className="p-2 rounded-lg border border-luna-border bg-luna-card hover:bg-luna-surface text-luna-dim hover:text-luna-text transition-colors"
            title="Fetch voices"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
        {error && <p className="text-[11px] text-luna-dim">{error}</p>}
      </div>
    )
  }

  return (
    <div className="flex gap-2">
      <div className="flex-1 relative">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full appearance-none bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text pr-8 focus:outline-none focus:border-luna-primary/60"
        >
          {!voices.some(v => v.voice_id === value) && <option value={value}>{value}</option>}
          {voices.map(v => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
        </select>
        <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-luna-dim pointer-events-none" />
      </div>
      <button
        onClick={load}
        disabled={loading}
        className="p-2 rounded-lg border border-luna-border bg-luna-card hover:bg-luna-surface text-luna-dim hover:text-luna-text transition-colors"
        title="Refresh voices"
      >
        <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
      </button>
    </div>
  )
}

export function SettingsView() {
  const { viewMode, toggleViewMode } = useStore()
  const [data, setData] = useState<CodingSettings | null>(null)
  const [form, setForm] = useState<Partial<CodingSettings>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getCodingSettings()
      .then(s => { setData(s); setForm(s) })
      .catch(() => setError('Failed to load settings'))
  }, [])

  const set = (key: string, value: unknown) =>
    setForm(f => ({ ...f, [key]: value }))

  const save = async () => {
    setSaving(true)
    setError('')
    try {
      await api.updateCodingSettings(form as Record<string, unknown>)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch {
      setError('Save failed — check the backend logs.')
    } finally {
      setSaving(false)
    }
  }

  if (!data) {
    return (
      <div className="h-full flex items-center justify-center text-luna-dim text-sm">
        {error || 'Loading…'}
      </div>
    )
  }

  const chatProvider = (form.llm_provider ?? data.llm_provider) as string
  const codingProviderRaw = (form.coding_provider ?? data.coding_provider) as string
  const effectiveCodingProvider = codingProviderRaw || chatProvider

  const chatModelField  = modelFieldFor(chatProvider, { ...data, ...form } as CodingSettings)
  const codeModelField  = modelFieldFor(effectiveCodingProvider, { ...data, ...form } as CodingSettings)

  return (
    <div className="h-full overflow-y-auto px-6 py-6 space-y-6">
      <div>
        <h2 className="text-luna-text font-semibold text-base mb-0.5">Settings</h2>
        <p className="text-luna-dim text-xs">Model providers and coding agent configuration</p>
      </div>

      {/* ── Interface ───────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <h3 className="text-luna-text text-sm font-medium border-b border-luna-border pb-1.5">
          Interface
        </h3>
        <div className="flex items-center justify-between py-2.5 px-3 rounded-xl bg-luna-card border border-luna-border/50">
          <div className="flex items-center gap-3">
            <Mic size={15} className="text-luna-dim" />
            <div>
              <p className="text-sm text-luna-text">Jarvis mode</p>
              <p className="text-[11px] text-luna-dim">Voice-only interface — hides the sidebar and panels</p>
            </div>
          </div>
          <button
            onClick={() => { if (viewMode !== 'luna') toggleViewMode() }}
            className={`relative w-10 h-5 rounded-full transition-colors ${
              viewMode === 'user' ? 'bg-luna-primary/70' : 'bg-luna-border'
            }`}
          >
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
              viewMode === 'user' ? 'translate-x-5' : 'translate-x-0.5'
            }`} />
          </button>
        </div>
      </section>

      {/* ── Model Configuration ─────────────────────────────────────────── */}
      <section className="space-y-4">
        <h3 className="text-luna-text text-sm font-medium border-b border-luna-border pb-1.5">
          Model Configuration
        </h3>

        {/* Chat provider */}
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
            Chat provider
          </label>
          <Select
            value={chatProvider}
            onChange={v => set('llm_provider', v)}
            options={PROVIDERS}
          />
        </div>

        {/* Chat model */}
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
            Chat model
          </label>
          {chatProvider === 'ollama' ? (
            <OllamaModelPicker
              value={(form as any)[chatModelField.key] ?? chatModelField.value}
              onChange={v => set(chatModelField.key, v)}
            />
          ) : (
            <input
              className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
              value={(form as any)[chatModelField.key] ?? chatModelField.value}
              onChange={e => set(chatModelField.key, e.target.value)}
            />
          )}
        </div>

        {/* Coding provider */}
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
            Coding agent provider
          </label>
          <Select
            value={codingProviderRaw}
            onChange={v => set('coding_provider', v)}
            options={CODING_PROVIDERS}
          />
          {codingProviderRaw === '' && (
            <p className="text-[11px] text-luna-dim">
              Using chat provider: <span className="text-luna-text">{chatProvider}</span>
            </p>
          )}
        </div>

        {/* Coding model — only show for Ollama */}
        {effectiveCodingProvider === 'ollama' && (
          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
              Coding model (Ollama)
            </label>
            <OllamaModelPicker
              value={(form.coding_model ?? data.coding_model) as string}
              onChange={v => set('coding_model', v)}
            />
            <p className="text-[11px] text-luna-dim">
              Use a code-specialized model for the coding agent (e.g. qwen2.5-coder:7b)
            </p>
          </div>
        )}

        {/* Non-Ollama coding model */}
        {effectiveCodingProvider !== 'ollama' && effectiveCodingProvider !== chatProvider && (
          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
              Coding model
            </label>
            <input
              className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
              value={(form as any)[codeModelField.key] ?? codeModelField.value}
              onChange={e => set(codeModelField.key, e.target.value)}
            />
          </div>
        )}
      </section>

      {/* ── Voice ────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <h3 className="text-luna-text text-sm font-medium border-b border-luna-border pb-1.5">
          Voice
        </h3>

        {/* TTS provider */}
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
            Text-to-speech
          </label>
          <Select
            value={(form.tts_provider ?? data.tts_provider) as string}
            onChange={v => set('tts_provider', v)}
            options={TTS_PROVIDERS}
          />
        </div>

        {/* STT provider */}
        <div className="space-y-1.5">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
            Speech-to-text
          </label>
          <Select
            value={(form.stt_provider ?? data.stt_provider) as string}
            onChange={v => set('stt_provider', v)}
            options={STT_PROVIDERS}
          />
        </div>

        {((form.tts_provider ?? data.tts_provider) === 'elevenlabs' ||
          (form.stt_provider ?? data.stt_provider) === 'elevenlabs') && (
          <>
            {!data.voice_providers.elevenlabs.configured && (
              <p className="text-[11px] text-amber-400">
                No ElevenLabs API key set — add elevenlabs_api_key to .env, then reload.
              </p>
            )}

            {(form.tts_provider ?? data.tts_provider) === 'elevenlabs' && (
              <div className="space-y-1.5">
                <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
                  ElevenLabs voice
                </label>
                <ElevenLabsVoicePicker
                  value={(form.elevenlabs_voice_id ?? data.elevenlabs_voice_id) as string}
                  onChange={v => set('elevenlabs_voice_id', v)}
                />
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Provider status ─────────────────────────────────────────────── */}
      <section className="space-y-3">
        <h3 className="text-luna-text text-sm font-medium border-b border-luna-border pb-1.5">
          Provider Status
        </h3>
        <div className="space-y-1.5">
          {Object.entries(data.providers).map(([key, info]) => (
            <div key={key} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-luna-card border border-luna-border/50">
              <div className="flex items-center gap-2">
                {info.configured ? (
                  <CheckCircle size={13} className="text-green-400 flex-shrink-0" />
                ) : (
                  <div className="w-3 h-3 rounded-full border border-luna-border flex-shrink-0" />
                )}
                <span className="text-sm text-luna-text">{info.label}</span>
              </div>
              <span className={`text-[11px] ${info.configured ? 'text-green-400' : 'text-luna-dim'}`}>
                {info.configured ? 'configured' : 'not set'}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-luna-dim">
          API keys are configured via the desktop Settings window (title bar gear icon).
        </p>
      </section>

      {/* ── Coding agent settings ────────────────────────────────────────── */}
      <section className="space-y-4">
        <h3 className="text-luna-text text-sm font-medium border-b border-luna-border pb-1.5">
          Coding Agent
        </h3>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
              Max iterations
            </label>
            <input
              type="number"
              min={1}
              max={50}
              className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
              value={(form.coding_max_iterations ?? data.coding_max_iterations) as number}
              onChange={e => set('coding_max_iterations', parseInt(e.target.value, 10) || 20)}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
              Shell timeout (s)
            </label>
            <input
              type="number"
              min={10}
              max={600}
              className="w-full bg-luna-card border border-luna-border rounded-lg px-3 py-2 text-sm text-luna-text focus:outline-none focus:border-luna-primary/60"
              value={(form.coding_shell_timeout ?? data.coding_shell_timeout) as number}
              onChange={e => set('coding_shell_timeout', parseInt(e.target.value, 10) || 120)}
            />
          </div>
        </div>
      </section>

      {/* ── Save ────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-luna-primary/20 border border-luna-primary/40 text-luna-accent text-sm font-medium hover:bg-luna-primary/30 transition-colors disabled:opacity-50"
        >
          <Save size={13} />
          {saving ? 'Saving…' : 'Save Changes'}
        </button>

        {saved && (
          <div className="flex items-center gap-1.5 text-green-400 text-xs">
            <CheckCircle size={13} />
            Saved
          </div>
        )}

        {error && (
          <div className="flex items-center gap-1.5 text-red-400 text-xs">
            <AlertCircle size={13} />
            {error}
          </div>
        )}
      </div>

      <p className="text-[11px] text-luna-dim pb-4">
        Provider and model changes apply immediately to new requests. No restart needed.
      </p>
    </div>
  )
}

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Zap, ArrowRight, AlertCircle, CheckCircle, ChevronDown } from 'lucide-react'
import { setDirectApiKey, setDirectProvider, setDirectModel } from '../../platform'
import { initDirectChat, streamDirect, PROVIDER_OPTIONS, DirectProvider } from '../../api/directChat'

interface Props { onDone: () => void }

export function MobileSetup({ onDone }: Props) {
  const [provider, setProvider] = useState<DirectProvider>('groq')
  const [apiKey, setApiKey]     = useState('')
  const [model, setModel]       = useState('')
  const [testing, setTesting]   = useState(false)
  const [err, setErr]           = useState('')
  const [ok, setOk]             = useState(false)

  const prov = PROVIDER_OPTIONS.find(p => p.value === provider)!

  const test = async () => {
    setErr(''); setOk(false)
    if (!apiKey.trim()) { setErr('Enter your API key first.'); return }
    setTesting(true)
    try {
      initDirectChat({ provider, apiKey: apiKey.trim(), model: model || prov.models[0] })
      let got = ''
      for await (const tok of streamDirect([], 'Reply with just "ok"')) {
        got += tok
        if (got.length > 10) break
      }
      setOk(true)
    } catch (e: any) {
      setErr(e?.message ?? 'Connection failed')
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    if (!apiKey.trim()) { setErr('Enter your API key first.'); return }
    const resolvedModel = model || prov.models[0]
    await setDirectApiKey(apiKey.trim())
    await setDirectProvider(provider)
    await setDirectModel(resolvedModel)
    initDirectChat({ provider, apiKey: apiKey.trim(), model: resolvedModel })
    onDone()
  }

  return (
    <div className="fixed inset-0 bg-luna-bg flex flex-col items-center justify-center px-6 z-50">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-sm space-y-5"
      >
        {/* Header */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-luna-primary/20 border border-luna-primary/30 flex items-center justify-center">
            <Zap size={26} className="text-luna-accent" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-semibold text-luna-text">Set up Luna</h1>
            <p className="text-sm text-luna-dim mt-1">Connect your AI provider to get started.</p>
          </div>
        </div>

        {/* Provider */}
        <div className="space-y-2">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Provider</label>
          <div className="grid grid-cols-3 gap-2">
            {PROVIDER_OPTIONS.map(p => (
              <button
                key={p.value}
                onClick={() => { setProvider(p.value); setModel(''); setErr(''); setOk(false) }}
                className={`py-2.5 rounded-xl text-xs font-medium border transition-all ${
                  provider === p.value
                    ? 'bg-luna-primary/20 border-luna-primary/40 text-luna-accent'
                    : 'bg-luna-card border-luna-border text-luna-muted hover:border-luna-primary/30'
                }`}
              >
                {p.value === 'groq' ? 'Groq' : p.value === 'openai' ? 'OpenAI' : 'Anthropic'}
              </button>
            ))}
          </div>
          {provider === 'groq' && (
            <p className="text-[11px] text-green-400/80">
              Groq has a free tier — get a key at console.groq.com
            </p>
          )}
        </div>

        {/* Model */}
        <div className="space-y-2">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">Model</label>
          <div className="relative">
            <select
              value={model || prov.models[0]}
              onChange={e => { setModel(e.target.value); setErr(''); setOk(false) }}
              className="w-full appearance-none bg-luna-card border border-luna-border rounded-xl px-4 py-3 text-sm text-luna-text outline-none focus:border-luna-primary/60"
            >
              {prov.models.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-luna-dim pointer-events-none" />
          </div>
        </div>

        {/* API Key */}
        <div className="space-y-2">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={e => { setApiKey(e.target.value); setErr(''); setOk(false) }}
            placeholder={`Your ${prov.value === 'groq' ? 'Groq' : prov.value === 'openai' ? 'OpenAI' : 'Anthropic'} API key`}
            autoCapitalize="none" autoCorrect="off" spellCheck={false}
            className="w-full bg-luna-card border border-luna-border rounded-xl px-4 py-3 text-sm text-luna-text placeholder-luna-dim focus:outline-none focus:border-luna-primary/60"
          />
          <p className="text-[11px] text-luna-dim">Stored on-device only — never sent to our servers.</p>
        </div>

        {err && (
          <div className="flex items-start gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            <AlertCircle size={13} className="shrink-0 mt-0.5" /> {err}
          </div>
        )}
        {ok && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-xs">
            <CheckCircle size={13} /> API key works!
          </div>
        )}

        <div className="flex flex-col gap-2.5">
          <button
            onClick={test}
            disabled={testing || !apiKey.trim()}
            className="w-full py-3 rounded-xl border border-luna-border bg-luna-card text-luna-text text-sm font-medium disabled:opacity-40 hover:bg-luna-surface transition-colors"
          >
            {testing ? 'Testing…' : 'Test API key'}
          </button>
          <button
            onClick={save}
            disabled={!apiKey.trim()}
            className="w-full py-3 rounded-xl bg-luna-primary/80 text-white text-sm font-semibold disabled:opacity-40 hover:bg-luna-primary flex items-center justify-center gap-2 transition-colors"
          >
            Start chatting <ArrowRight size={15} />
          </button>
        </div>
      </motion.div>
    </div>
  )
}

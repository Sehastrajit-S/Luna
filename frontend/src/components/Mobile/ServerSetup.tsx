import { useState } from 'react'
import { motion } from 'framer-motion'
import { Wifi, ArrowRight, AlertCircle, CheckCircle } from 'lucide-react'
import { setServerUrl } from '../../platform'
import { initApiBase } from '../../api/client'

interface Props {
  onDone: () => void
}

export function ServerSetup({ onDone }: Props) {
  const [url, setUrl]       = useState('')
  const [testing, setTesting] = useState(false)
  const [err, setErr]       = useState('')
  const [ok, setOk]         = useState(false)

  const normalise = (raw: string) => {
    let u = raw.trim().replace(/\/$/, '')
    if (u && !/^https?:\/\//i.test(u)) u = `http://${u}`
    return u
  }

  const test = async () => {
    setErr(''); setOk(false)
    const base = normalise(url)
    if (!base) { setErr('Enter a server URL first.'); return }
    setTesting(true)
    try {
      const res = await fetch(`${base}/api/system/health`, { signal: AbortSignal.timeout(6000) })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      setOk(true)
    } catch (e: any) {
      setErr(e?.message?.includes('timed out') || e?.name === 'TimeoutError'
        ? 'Connection timed out — is the server reachable from this device?'
        : `Cannot reach server: ${e?.message ?? e}`)
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    const base = normalise(url)
    if (!base) { setErr('Enter a server URL first.'); return }
    await setServerUrl(base)
    initApiBase(base)
    onDone()
  }

  return (
    <div className="fixed inset-0 bg-luna-bg flex flex-col items-center justify-center px-6 z-50">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-sm space-y-8"
      >
        {/* Logo + title */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-16 h-16 rounded-2xl bg-luna-primary/20 border border-luna-primary/30 flex items-center justify-center">
            <Wifi size={28} className="text-luna-accent" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-semibold text-luna-text">Connect to Luna</h1>
            <p className="text-sm text-luna-dim mt-1">
              Enter the address of your Luna backend server.
            </p>
          </div>
        </div>

        {/* URL input */}
        <div className="space-y-3">
          <label className="text-xs text-luna-dim font-medium uppercase tracking-wide">
            Server URL
          </label>
          <input
            type="url"
            value={url}
            onChange={e => { setUrl(e.target.value); setErr(''); setOk(false) }}
            onKeyDown={e => e.key === 'Enter' && test()}
            placeholder="http://192.168.1.x:8899"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            className="w-full bg-luna-card border border-luna-border rounded-xl px-4 py-3 text-sm text-luna-text placeholder-luna-dim focus:outline-none focus:border-luna-primary/60"
          />
          <p className="text-[11px] text-luna-dim">
            Run the Luna desktop app on your PC and use its local IP address, or point to a hosted server.
          </p>
        </div>

        {/* Status feedback */}
        {err && (
          <div className="flex items-start gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            <AlertCircle size={13} className="shrink-0 mt-0.5" />
            {err}
          </div>
        )}
        {ok && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-xs">
            <CheckCircle size={13} />
            Connected — server is reachable.
          </div>
        )}

        {/* Buttons */}
        <div className="flex flex-col gap-3">
          <button
            onClick={test}
            disabled={testing || !url.trim()}
            className="w-full py-3 rounded-xl border border-luna-border bg-luna-card text-luna-text text-sm font-medium disabled:opacity-40 transition-colors hover:bg-luna-surface"
          >
            {testing ? 'Testing…' : 'Test Connection'}
          </button>
          <button
            onClick={save}
            disabled={!url.trim()}
            className="w-full py-3 rounded-xl bg-luna-primary/80 text-white text-sm font-semibold disabled:opacity-40 transition-colors hover:bg-luna-primary flex items-center justify-center gap-2"
          >
            Continue <ArrowRight size={15} />
          </button>
        </div>
      </motion.div>
    </div>
  )
}

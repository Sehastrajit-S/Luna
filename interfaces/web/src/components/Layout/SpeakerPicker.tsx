import { useEffect, useRef, useState } from 'react'
import { Volume2, ChevronDown, Check } from 'lucide-react'
import { authHeaders } from '../../api/client'

interface AudioDevice {
  id: string
  name: string
}

export function SpeakerPicker() {
  const [devices, setDevices]   = useState<AudioDevice[]>([])
  const [current, setCurrent]   = useState<string | null>(null)
  const [open, setOpen]         = useState(false)
  const [switching, setSwitching] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const base = window.electronAPI?.apiBase ?? ''

  useEffect(() => {
    fetch(`${base}/api/system/audio-devices`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => { setDevices(d.devices ?? []); setCurrent(d.current ?? null) })
      .catch(() => {})
  }, [base])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const select = async (id: string) => {
    if (id === current || switching) return
    setSwitching(true)
    setOpen(false)
    try {
      const res = await fetch(`${base}/api/system/audio-device`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ device_id: id }),
      })
      const data = await res.json()
      if (data.ok) setCurrent(id)
    } catch {}
    setSwitching(false)
  }

  const label = (id: string | null) => {
    const d = devices.find(x => x.id === id)
    if (!d) return 'Speaker'
    const name = d.name
    // "Speaker 1 (2- 25609)"  → "Speaker 1"
    const numericMatch = name.match(/^((?:Speaker|Headphones?|Headset)\s+\d+)/i)
    if (numericMatch) return numericMatch[1]
    // "Speakers (Realtek(R) Audio)" → "Realtek"
    // "Speakers (High Definition Audio Device)" → "Speakers"
    const parenMatch = name.match(/\(([^)]*?(?:audio|realtek|nvidia|AMD)[^)]*)\)/i)
    if (parenMatch) {
      return parenMatch[1].replace(/\([^)]*\)/g, '').replace(/\bAudio\b/gi, '').trim() || name.split(' ')[0]
    }
    // Strip all parens, take first word(s)
    const stripped = name.replace(/\s*\(.*\)/g, '').trim()
    return stripped || name.split(' ')[0]
  }

  if (devices.length === 0) return null

  return (
    <div ref={ref} className="relative flex items-center h-full">
      <button
        onClick={() => setOpen(o => !o)}
        className="h-full flex items-center gap-1.5 px-2.5 text-luna-dim hover:text-luna-text hover:bg-white/10 transition-colors"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        title="Switch audio output"
      >
        <Volume2 size={13} strokeWidth={2} className={switching ? 'animate-pulse text-cyan-400' : ''} />
        <span className="text-[10px] font-mono tracking-wide max-w-[80px] truncate">{label(current)}</span>
        <ChevronDown size={10} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          className="absolute top-full right-0 mt-1 z-50 overflow-hidden"
          style={{
            background: 'rgba(9,9,15,0.96)',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8,
            minWidth: 220,
            boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          }}
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-luna-dim/60 border-b border-white/5">
            Audio Output
          </div>
          {devices.map(d => {
            const active = d.id === current
            return (
              <button
                key={d.id}
                onClick={() => select(d.id)}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-white/8"
                style={{ color: active ? 'rgba(34,211,238,0.95)' : 'rgba(255,255,255,0.65)' }}
              >
                <Check size={12} className={active ? 'opacity-100' : 'opacity-0'} />
                <span className="text-xs truncate">{d.name}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

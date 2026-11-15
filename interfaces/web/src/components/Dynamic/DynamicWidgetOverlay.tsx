import { useState, useEffect, useRef } from 'react'
import { Check, ChevronDown, ChevronRight, X } from 'lucide-react'
import { useStore } from '../../store'
import { GeneratedScene, SceneSpec } from './GeneratedScene'
import { authHeaders } from '../../api/client'

// ── helpers ───────────────────────────────────────────────────────────────────
function rows(body: string) {
  return body.split(';').map(s => s.trim()).filter(Boolean)
}
function splitPair(text: string): [string, string] {
  const idx = text.indexOf(':')
  if (idx < 0) return [text, '']
  return [text.slice(0, idx).trim(), text.slice(idx + 1).trim()]
}

// ── Wave loading animation ────────────────────────────────────────────────────
function WaveLoader() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const resize = () => {
      canvas.width  = canvas.offsetWidth  || 300
      canvas.height = canvas.offsetHeight || 360
    }
    resize()

    const COLS = 30
    const ROWS = 24
    let t = 0
    let raf = 0

    const lerp = (a: number, b: number, f: number) => a + (b - a) * f

    const draw = () => {
      raf = requestAnimationFrame(draw)
      t += 0.018

      const W = canvas.width
      const H = canvas.height
      ctx.fillStyle = '#000000'
      ctx.fillRect(0, 0, W, H)

      const cw = W / COLS
      const ch = H / ROWS

      for (let row = 0; row < ROWS; row++) {
        for (let col = 0; col < COLS; col++) {
          const x = (col + 0.5) * cw
          const y = (row + 0.5) * ch

          // Overlapping travelling waves — ocean from above
          const wave =
            Math.sin(col * 0.42 + row * 0.22 + t * 1.3) * 0.45 +
            Math.sin(col * 0.28 - row * 0.52 + t * 0.85) * 0.35 +
            Math.sin((col + row) * 0.31 + t * 1.05) * 0.20

          // wave ≈ [-1, 1] → normalise to [0, 1]
          const n = Math.max(0, Math.min(1, (wave + 1) / 2))

          // Colour ramp: near-black → deep purple → luna purple → bright lavender
          let r: number, g: number, b: number
          if (n < 0.35) {
            const f = n / 0.35
            r = lerp(4,   90,  f); g = lerp(0,  10,  f); b = lerp(12, 180, f)
          } else if (n < 0.65) {
            const f = (n - 0.35) / 0.30
            r = lerp(90,  139, f); g = lerp(10,  92,  f); b = lerp(180, 246, f)
          } else {
            const f = (n - 0.65) / 0.35
            r = lerp(139, 216, f); g = lerp(92,  180, f); b = lerp(246, 254, f)
          }

          const radius = 1.0 + n * 2.8
          const alpha  = 0.25 + n * 0.75

          ctx.beginPath()
          ctx.arc(x, y, radius, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},${alpha.toFixed(2)})`
          ctx.fill()
        }
      }
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <div className="relative w-full h-full">
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      <div className="absolute bottom-4 left-0 right-0 flex items-center justify-center gap-2">
        <div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
        <span className="text-[9px] font-mono tracking-[0.3em] text-purple-300/70 uppercase">Generating</span>
      </div>
    </div>
  )
}

// ── Luna 3D widget ──────────────────────────────────────────────────────────
function LunaModelWidget({ title, items }: { title: string; items: string[] }) {
  const [visible, setVisible] = useState<number[]>([])
  const [scanDone, setScanDone] = useState(false)
  const [sceneSpec, setSceneSpec] = useState<SceneSpec | null>(null)
  const [sceneError, setSceneError] = useState(false)
  const pairs = items.map(splitPair)

  useEffect(() => {
    let cancelled = false
    fetch(`/api/system/scene?topic=${encodeURIComponent(title)}`, { headers: authHeaders() })
      .then(r => r.json())
      .then(data => {
        if (cancelled) return
        if (data?.shapes?.length) setSceneSpec(data as SceneSpec)
        else setSceneError(true)
      })
      .catch(() => { if (!cancelled) setSceneError(true) })
    return () => { cancelled = true }
  }, [title])

  useEffect(() => {
    const t1 = setTimeout(() => setScanDone(true), 900)
    const timers: ReturnType<typeof setTimeout>[] = [t1]
    pairs.forEach((_, i) => {
      timers.push(setTimeout(() => setVisible(v => [...v, i]), 900 + i * 280))
    })
    return () => timers.forEach(clearTimeout)
  }, [pairs.length])

  return (
    <div className="flex h-[360px] gap-0">
      {/* ── Left: 3D canvas ── */}
      <div className="relative w-[46%] shrink-0 bg-black/40 border-r border-luna-primary/20 overflow-hidden">
        <div className="absolute inset-0">
          {sceneSpec ? (
            <GeneratedScene spec={sceneSpec} />
          ) : sceneError ? (
            <div className="flex items-center justify-center h-full text-[10px] font-mono text-luna-dim/50">MODEL UNAVAILABLE</div>
          ) : (
            <WaveLoader />
          )}
        </div>
        {/* scanning line animation */}
        {!scanDone && (
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            <div
              className="absolute left-0 right-0 h-0.5 bg-luna-accent/60"
              style={{ animation: 'scan-line 0.9s linear forwards' }}
            />
          </div>
        )}
        {/* corner brackets */}
        <div className="absolute top-2 left-2 w-5 h-5 border-t-2 border-l-2 border-luna-accent/60" />
        <div className="absolute top-2 right-2 w-5 h-5 border-t-2 border-r-2 border-luna-accent/60" />
        <div className="absolute bottom-2 left-2 w-5 h-5 border-b-2 border-l-2 border-luna-accent/60" />
        <div className="absolute bottom-2 right-2 w-5 h-5 border-b-2 border-r-2 border-luna-accent/60" />
        {/* label */}
        <div className="absolute bottom-3 left-0 right-0 text-center">
          <span className="text-[9px] font-mono tracking-[0.3em] text-luna-accent/50 uppercase">
            {title.toUpperCase()}
          </span>
        </div>
      </div>

      {/* ── Right: animated info panels ── */}
      <div className="flex-1 overflow-y-auto">
        {!scanDone && (
          <div className="flex items-center gap-2 px-4 py-3 border-b border-luna-primary/20">
            <div className="w-2 h-2 rounded-full bg-luna-accent animate-pulse" />
            <span className="text-[10px] font-mono text-luna-accent tracking-widest">SCANNING...</span>
          </div>
        )}
        <div className="divide-y divide-luna-border/40">
          {pairs.map(([label, detail], i) => (
            <div
              key={i}
              className="px-4 py-3 transition-all duration-500"
              style={{
                opacity: visible.includes(i) ? 1 : 0,
                transform: visible.includes(i) ? 'translateX(0)' : 'translateX(16px)',
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <div className="w-1.5 h-1.5 bg-luna-accent rounded-full shrink-0" />
                <span className="text-[10px] font-mono text-luna-accent tracking-[0.18em] uppercase">{label || `Item ${i + 1}`}</span>
              </div>
              {detail && (
                <p className="text-xs text-luna-muted leading-relaxed pl-3.5">{detail}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Email widget ──────────────────────────────────────────────────────────────
function formatEmailDate(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    if (diffDays < 7) return d.toLocaleDateString([], { weekday: 'short' })
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch {
    return dateStr.slice(5, 16)
  }
}

function EmailsWidget({ body }: { body: string }) {
  const [expanded, setExpanded] = useState<number | null>(null)
  let emails: { from: string; subject: string; date: string; snippet: string }[] = []
  try { emails = JSON.parse(body) } catch { emails = [] }

  return (
    <div className="space-y-1.5 max-h-[420px] overflow-y-auto pr-1">
      {emails.length === 0 && (
        <div className="text-xs text-luna-dim text-center py-8 font-mono tracking-widest">NO EMAILS</div>
      )}
      {emails.map((email, i) => {
        const initial = email.from?.match(/[A-Za-z]/)?.[0]?.toUpperCase() ?? '?'
        const senderName = email.from?.replace(/<[^>]+>/, '').trim() || email.from || 'Unknown'
        const open = expanded === i
        return (
          <button
            key={i}
            onClick={() => setExpanded(open ? null : i)}
            className={`w-full text-left border transition-all duration-200 ${open ? 'border-luna-primary/50 bg-luna-primary/8' : 'border-luna-border bg-luna-card hover:border-luna-primary/30'}`}
          >
            <div className="flex items-center gap-3 px-3 py-2.5">
              <div className="w-7 h-7 rounded-full bg-luna-primary/15 border border-luna-primary/25 flex items-center justify-center text-[11px] font-mono font-bold text-luna-accent shrink-0">
                {initial}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[11px] font-medium truncate ${open ? 'text-luna-accent' : 'text-luna-muted'}`}>
                    {senderName}
                  </span>
                  <span className="text-[10px] font-mono text-luna-dim shrink-0">{formatEmailDate(email.date)}</span>
                </div>
                <div className={`text-xs truncate mt-0.5 ${open ? 'text-luna-text font-medium' : 'text-luna-dim'}`}>
                  {email.subject}
                </div>
              </div>
            </div>
            {open && email.snippet && (
              <div className="px-3 pb-3 pt-0 border-t border-luna-primary/15">
                <p className="text-[11px] text-luna-muted leading-relaxed pl-10">{email.snippet}</p>
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}

// ── Classic widget types ───────────────────────────────────────────────────────
function ChecklistWidget({ items }: { items: string[] }) {
  const [checked, setChecked] = useState<Record<number, boolean>>({})
  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <button key={i} onClick={() => setChecked(s => ({ ...s, [i]: !s[i] }))}
          className="w-full flex items-start gap-3 bg-luna-card border border-luna-border px-3 py-2 text-left hover:border-luna-primary/35 transition-colors">
          <span className={`mt-0.5 w-5 h-5 shrink-0 flex items-center justify-center border ${checked[i] ? 'bg-luna-primary border-luna-primary text-white' : 'border-luna-border text-transparent'}`}>
            <Check size={12} />
          </span>
          <span className={`text-xs leading-relaxed ${checked[i] ? 'text-luna-dim line-through' : 'text-luna-muted'}`}>{item}</span>
        </button>
      ))}
    </div>
  )
}

function TabsWidget({ items }: { items: string[] }) {
  const pairs = items.map(splitPair)
  const [active, setActive] = useState(0)
  const cur = pairs[active] ?? pairs[0]
  return (
    <div className="grid grid-cols-[130px_1fr] gap-3">
      <div className="space-y-1">
        {pairs.map(([label], i) => (
          <button key={i} onClick={() => setActive(i)}
            className={`w-full px-3 py-2 text-left text-xs font-mono border transition-colors ${active === i ? 'bg-luna-primary/20 border-luna-primary/40 text-luna-accent' : 'bg-luna-card border-luna-border text-luna-dim hover:text-luna-text'}`}>
            {label}
          </button>
        ))}
      </div>
      <div className="min-h-[140px] border border-luna-border bg-luna-card px-4 py-3">
        <div className="text-xs font-mono text-luna-accent mb-2">{cur?.[0]}</div>
        <div className="text-sm text-luna-muted leading-relaxed">{cur?.[1] || cur?.[0]}</div>
      </div>
    </div>
  )
}

function InteractiveWidget({ items }: { items: string[] }) {
  const pairs = items.map(splitPair)
  const [expanded, setExpanded] = useState<number | null>(0)
  return (
    <div className="space-y-1.5">
      {pairs.map(([label, detail], i) => {
        const open = expanded === i
        return (
          <button key={i} onClick={() => setExpanded(open ? null : i)}
            className={`w-full text-left border transition-all duration-200 ${open ? 'border-luna-primary/50 bg-luna-primary/10' : 'border-luna-border bg-luna-card hover:border-luna-primary/30 hover:bg-luna-primary/5'}`}>
            <div className="flex items-center gap-2 px-3 py-2.5">
              <span className={`shrink-0 transition-colors ${open ? 'text-luna-accent' : 'text-luna-dim'}`}>
                {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              </span>
              <span className={`text-xs font-mono font-medium ${open ? 'text-luna-accent' : 'text-luna-muted'}`}>{label}</span>
            </div>
            {open && detail && (
              <div className="px-4 pb-3 text-sm text-luna-text leading-relaxed border-t border-luna-primary/20 pt-2">{detail}</div>
            )}
          </button>
        )
      })}
    </div>
  )
}

function FlashcardsWidget({ items }: { items: string[] }) {
  const cards = items.map(splitPair)
  const [idx, setIdx] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const card = cards[idx] ?? cards[0]
  const next = () => { setIdx(i => (i + 1) % Math.max(cards.length, 1)); setRevealed(false) }
  return (
    <div className="space-y-3">
      <button onClick={() => setRevealed(r => !r)}
        className="w-full min-h-[150px] border border-luna-primary/30 bg-luna-card px-5 py-4 text-left hover:border-luna-primary/50 transition-colors">
        <div className="text-[10px] uppercase tracking-[0.22em] text-luna-dim font-mono mb-3">{revealed ? 'answer' : 'prompt'}</div>
        <div className="text-base text-luna-text leading-relaxed">{revealed ? (card?.[1] || card?.[0]) : card?.[0]}</div>
      </button>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-luna-dim">{idx + 1} / {cards.length}</span>
        <button onClick={next} className="px-3 py-1.5 text-xs text-luna-accent border border-luna-primary/30 hover:bg-luna-primary/10 transition-colors">Next</button>
      </div>
    </div>
  )
}

// ── Main overlay ───────────────────────────────────────────────────────────────
export function DynamicWidgetOverlay() {
  const widget = useStore(s => s.dynamicWidget)
  const close  = useStore(s => s.closeDynamicWidget)
  if (!widget) return null

  const items = rows(widget.body)
  const kind  = widget.kind.toLowerCase()
  const is3D  = kind === 'model3d'
  const isWide = kind === 'model3d' || kind === 'emails'

  return (
    <div className="fixed inset-0 z-[200] pointer-events-none flex items-center justify-center p-6" style={{ background: 'rgba(2,2,12,0.55)', backdropFilter: 'blur(2px)' }}>
      <div
        className={`pointer-events-auto bg-luna-surface/95 border border-luna-primary/35 shadow-luna-lg backdrop-blur-xl overflow-hidden ${isWide ? 'w-full max-w-2xl' : 'w-full max-w-xl'}`}
        style={{ borderRadius: 8 }}
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-luna-border px-4 py-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.24em] text-luna-dim font-mono">{kind}</div>
            <div className="text-sm text-luna-text font-medium mt-0.5">{widget.title}</div>
          </div>
          <button onClick={close} className="h-8 w-8 flex items-center justify-center text-luna-dim hover:text-luna-text hover:bg-white/5 transition-colors">
            <X size={15} />
          </button>
        </div>

        {/* body */}
        {is3D ? (
          <LunaModelWidget title={widget.title} items={items} />
        ) : kind === 'emails' ? (
          <div className="p-3">
            <EmailsWidget body={widget.body} />
          </div>
        ) : (
          <div className="p-4">
            {kind === 'checklist' ? <ChecklistWidget items={items} />
            : kind === 'interactive' ? <InteractiveWidget items={items} />
            : kind === 'tabs' ? <TabsWidget items={items} />
            : kind === 'flashcards' ? <FlashcardsWidget items={items} />
            : kind === 'compare' ? (
              <div className="grid gap-2">
                {items.map((item, i) => {
                  const [label, detail] = splitPair(item)
                  return (
                    <div key={i} className="grid grid-cols-[120px_1fr] gap-3 border border-luna-border bg-luna-card px-3 py-2">
                      <div className="text-xs font-mono text-luna-accent">{label.trim()}</div>
                      <div className="text-xs text-luna-muted leading-relaxed">{(detail || item).trim()}</div>
                    </div>
                  )
                })}
              </div>
            ) : kind === 'formula' ? (
              <div className="space-y-2">
                {items.map((item, i) => (
                  <div key={i} className="font-mono text-sm text-luna-accent bg-luna-card border border-luna-border px-3 py-2">{item}</div>
                ))}
              </div>
            ) : kind === 'timeline' ? (
              <div className="relative pl-5 space-y-0">
                <div className="absolute left-[7px] top-2 bottom-2 w-px bg-luna-primary/25" />
                {items.map((item, i) => (
                  <div key={i} className="relative flex gap-3 pb-3">
                    <div className="absolute left-[-13px] top-[5px] w-3 h-3 rounded-full border-2 border-luna-primary bg-luna-surface shrink-0" />
                    <div className="text-xs text-luna-muted leading-relaxed">{item}</div>
                  </div>
                ))}
              </div>
            ) : kind === 'summary' ? (
              <div className="space-y-1.5">
                {items.map((item, i) => (
                  <div key={i} className="flex gap-2.5 px-3 py-2 bg-luna-card border border-luna-border">
                    <div className="w-1 h-1 rounded-full bg-luna-primary mt-[7px] shrink-0" />
                    <div className="text-xs text-luna-muted leading-relaxed">{item}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {items.map((item, i) => (
                  <div key={i} className="flex gap-3 bg-luna-card border border-luna-border px-3 py-2">
                    <div className="w-5 h-5 shrink-0 flex items-center justify-center text-[10px] font-mono text-white bg-luna-primary">{i + 1}</div>
                    <div className="text-xs text-luna-muted leading-relaxed">{item}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

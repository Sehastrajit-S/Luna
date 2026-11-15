import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Dna, Send, Loader2, Check, RotateCcw, ChevronDown } from 'lucide-react'
import { authHeaders } from '../../api/client'

type Role = 'user' | 'assistant'

const LUNA_TONES   = ['warm','direct','curious','playful','concerned','casual','neutral']
const USER_STATES  = ['happy','sad','stressed','excited','bored','neutral','tired','anxious','frustrated']

const TONE_COLOR: Record<string, string> = {
  warm:       'bg-orange-500/15 text-orange-300 border-orange-500/25',
  direct:     'bg-blue-500/15 text-blue-300 border-blue-500/25',
  curious:    'bg-cyan-500/15 text-cyan-300 border-cyan-500/25',
  playful:    'bg-pink-500/15 text-pink-300 border-pink-500/25',
  concerned:  'bg-red-500/15 text-red-300 border-red-500/25',
  casual:     'bg-slate-500/15 text-slate-300 border-slate-500/25',
  neutral:    'bg-zinc-500/15 text-zinc-400 border-zinc-500/25',
  happy:      'bg-yellow-500/15 text-yellow-300 border-yellow-500/25',
  sad:        'bg-indigo-500/15 text-indigo-300 border-indigo-500/25',
  stressed:   'bg-red-500/15 text-red-300 border-red-500/25',
  excited:    'bg-amber-500/15 text-amber-300 border-amber-500/25',
  bored:      'bg-slate-500/15 text-slate-400 border-slate-500/25',
  tired:      'bg-purple-500/15 text-purple-300 border-purple-500/25',
  anxious:    'bg-rose-500/15 text-rose-300 border-rose-500/25',
  frustrated: 'bg-orange-500/15 text-orange-300 border-orange-500/25',
}

function EmotionChip({
  label, value, options, onChange, disabled,
}: {
  label: string; value: string; options: string[]; onChange: (v: string) => void; disabled: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  const colorClass = TONE_COLOR[value] ?? 'bg-zinc-500/15 text-zinc-400 border-zinc-500/25'

  return (
    <div ref={ref} className="relative">
      <button
        disabled={disabled}
        onClick={() => !disabled && setOpen(o => !o)}
        className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border font-mono transition-opacity ${colorClass} ${disabled ? 'cursor-default' : 'hover:opacity-80 cursor-pointer'}`}
      >
        <span className="text-[9px] opacity-60 uppercase tracking-wider">{label}</span>
        <span>{value}</span>
        {!disabled && <ChevronDown size={9} className={`transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute top-full left-0 mt-1 z-50 rounded-xl border border-luna-border overflow-hidden"
            style={{ background: 'rgba(9,9,15,0.97)', backdropFilter: 'blur(8px)', minWidth: 110 }}
          >
            {options.map(opt => (
              <button
                key={opt}
                onClick={() => { onChange(opt); setOpen(false) }}
                className={`w-full text-left px-3 py-1.5 text-[11px] font-mono transition-colors hover:bg-white/8 ${opt === value ? 'text-violet-300' : 'text-luna-dim'}`}
              >
                {opt}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

interface GenOption {
  response: string
  luna_tone: string
  user_state: string
}

interface Turn {
  id: number
  userMsg: string
  options: GenOption[]
  chosen: number | null
  state: 'idle' | 'generating' | 'picking'
  // user-corrected emotions for chosen option
  finalTone?: string
  finalUserState?: string
}

interface HistoryMsg { role: Role; content: string }

export function TrainView() {
  const [history, setHistory]     = useState<HistoryMsg[]>([])
  const [turns, setTurns]         = useState<Turn[]>([])
  const [input, setInput]         = useState('')
  const [pairCount, setPairCount] = useState<number | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)
  const base = window.electronAPI?.apiBase ?? ''

  useEffect(() => {
    fetch(`${base}/api/train/pairs`, { headers: authHeaders() })
      .then(r => r.json()).then(d => setPairCount(d.total)).catch(() => {})
  }, [base])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns])

  const send = async () => {
    const msg = input.trim()
    if (!msg) return
    setInput('')
    const turnId = Date.now()
    setTurns(prev => [...prev, { id: turnId, userMsg: msg, options: [], chosen: null, state: 'generating' }])

    try {
      const r = await fetch(`${base}/api/train/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ message: msg, history }),
      })
      const d = await r.json()
      const opts: GenOption[] = d.options ?? []
      setTurns(prev => prev.map(t =>
        t.id === turnId
          ? { ...t, options: opts, state: opts.length ? 'picking' : 'idle' }
          : t
      ))
    } catch {
      setTurns(prev => prev.map(t => t.id === turnId ? { ...t, state: 'idle' } : t))
    }
  }

  const pick = async (turnId: number, optionIdx: number) => {
    const turn = turns.find(t => t.id === turnId)
    if (!turn || turn.chosen !== null) return
    const chosen = turn.options[optionIdx]
    const rejected = turn.options.filter((_, i) => i !== optionIdx)

    setTurns(prev => prev.map(t =>
      t.id === turnId ? {
        ...t, chosen: optionIdx, state: 'idle',
        finalTone: chosen.luna_tone, finalUserState: chosen.user_state,
      } : t
    ))
    setHistory(prev => [...prev, { role: 'user', content: turn.userMsg }, { role: 'assistant', content: chosen.response }])

    try {
      const r = await fetch(`${base}/api/train/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          message: turn.userMsg,
          chosen: chosen.response,
          rejected: rejected.map(r => r.response),
          mode: 'response',
          luna_tone: chosen.luna_tone,
          user_state: chosen.user_state,
          all_options: turn.options,
        }),
      })
      const d = await r.json()
      if (d.ok) setPairCount(d.total)
    } catch {}

    setTimeout(() => inputRef.current?.focus(), 100)
  }

  const updateEmotion = (turnId: number, field: 'finalTone' | 'finalUserState', value: string) => {
    setTurns(prev => prev.map(t => t.id === turnId ? { ...t, [field]: value } : t))
  }

  const regenerate = async (turnId: number) => {
    const turn = turns.find(t => t.id === turnId)
    if (!turn || turn.state !== 'picking') return
    setTurns(prev => prev.map(t => t.id === turnId ? { ...t, options: [], state: 'generating' } : t))
    try {
      const r = await fetch(`${base}/api/train/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ message: turn.userMsg, history }),
      })
      const d = await r.json()
      const opts: GenOption[] = d.options ?? []
      setTurns(prev => prev.map(t =>
        t.id === turnId ? { ...t, options: opts, state: opts.length ? 'picking' : 'idle' } : t
      ))
    } catch {
      setTurns(prev => prev.map(t => t.id === turnId ? { ...t, state: 'picking' } : t))
    }
  }

  const reset = () => { setHistory([]); setTurns([]); setInput('') }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const lastTurn = turns[turns.length - 1]
  const canType = !lastTurn || (lastTurn.state === 'idle' && lastTurn.chosen !== null)

  return (
    <div className="h-full flex flex-col bg-luna-bg text-luna-text overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-luna-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Dna size={16} className="text-violet-400" />
          <div>
            <h2 className="text-sm font-semibold">RLHF Training</h2>
            <p className="text-[11px] text-luna-dim">Pick best response · correct emotions</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {pairCount !== null && (
            <span className="text-[11px] text-luna-dim">
              <span className="text-violet-400 font-mono">{pairCount}</span> pairs
            </span>
          )}
          <button onClick={reset} title="Reset" className="p-1.5 rounded-lg text-luna-dim hover:text-luna-text hover:bg-luna-surface transition-colors">
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-7">
        {turns.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-3">
            <Dna size={32} className="text-violet-400/40" />
            <p className="text-sm text-luna-dim">Start a conversation to train Luna.</p>
            <p className="text-xs text-luna-dim/50">
              Every turn shows 3 responses.<br />
              Pick your preferred one and correct the emotion labels.
            </p>
          </div>
        )}

        {turns.map((turn) => (
          <div key={turn.id} className="space-y-3">
            {/* User bubble */}
            <div className="flex justify-end">
              <div className="bg-luna-primary/20 border border-luna-primary/30 rounded-2xl rounded-tr-sm px-4 py-3 max-w-[70%]">
                <p className="text-sm leading-relaxed">{turn.userMsg}</p>
              </div>
            </div>

            {/* Generating */}
            {turn.state === 'generating' && (
              <div className="flex items-center gap-2 text-luna-dim text-sm">
                <Loader2 size={13} className="animate-spin text-violet-400" />
                Generating 3 responses...
              </div>
            )}

            {/* Options */}
            {(turn.state === 'picking' || turn.chosen !== null) && turn.options.length > 0 && (
              <div className="space-y-2">
                {turn.chosen === null && (
                  <p className="text-[10px] uppercase tracking-wider text-luna-dim">
                    Pick the best response · click chips to correct emotions
                  </p>
                )}
                {turn.options.map((opt, i) => {
                  const isChosen = turn.chosen === i
                  const isRejected = turn.chosen !== null && !isChosen
                  const tone  = isChosen ? (turn.finalTone  ?? opt.luna_tone)  : opt.luna_tone
                  const ustate = isChosen ? (turn.finalUserState ?? opt.user_state) : opt.user_state

                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: isRejected ? 0.28 : 1, y: 0 }}
                      transition={{ delay: i * 0.07 }}
                    >
                      <button
                        onClick={() => turn.chosen === null && pick(turn.id, i)}
                        disabled={turn.chosen !== null}
                        className={`w-full text-left rounded-xl border px-4 py-3.5 transition-all ${
                          isChosen
                            ? 'border-violet-500/50 bg-violet-500/10'
                            : turn.chosen === null
                              ? 'border-luna-border bg-luna-surface hover:border-violet-500/25 hover:bg-luna-card cursor-pointer'
                              : 'border-luna-border bg-luna-surface cursor-default'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${isChosen ? 'bg-violet-500 text-white' : 'bg-luna-border text-luna-dim'}`}>
                            {isChosen ? <Check size={10} /> : ['A','B','C'][i]}
                          </div>
                          <div className="flex-1 space-y-2">
                            <p className={`text-sm leading-relaxed ${isChosen ? 'text-luna-text' : 'text-luna-dim'}`}>
                              {opt.response}
                            </p>
                            <div className="flex items-center gap-2">
                              <EmotionChip
                                label="luna"
                                value={tone}
                                options={LUNA_TONES}
                                disabled={!isChosen}
                                onChange={v => updateEmotion(turn.id, 'finalTone', v)}
                              />
                              <EmotionChip
                                label="you"
                                value={ustate}
                                options={USER_STATES}
                                disabled={!isChosen}
                                onChange={v => updateEmotion(turn.id, 'finalUserState', v)}
                              />
                            </div>
                          </div>
                        </div>
                      </button>
                    </motion.div>
                  )
                })}

                {turn.chosen !== null && (
                  <p className="text-[10px] text-green-400/60">Saved · click emotion chips to correct labels.</p>
                )}
                {turn.chosen === null && turn.state === 'picking' && (
                  <button
                    onClick={() => regenerate(turn.id)}
                    className="flex items-center gap-1.5 text-[11px] text-luna-dim/60 hover:text-luna-dim transition-colors mt-1"
                  >
                    <RotateCcw size={11} /> None of these — try again
                  </button>
                )}
              </div>
            )}
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="px-6 py-4 border-t border-luna-border shrink-0">
        {!canType && lastTurn?.state === 'picking' && (
          <p className="text-[11px] text-luna-dim mb-2">Pick a response above to continue.</p>
        )}
        <div className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            disabled={!canType}
            placeholder={canType ? "Say something..." : "Pick a response first"}
            rows={2}
            className="flex-1 bg-luna-surface border border-luna-border rounded-xl px-4 py-3 text-sm placeholder-luna-dim/50 resize-none focus:outline-none focus:border-violet-500/40 transition-colors disabled:opacity-40"
          />
          <button
            onClick={send}
            disabled={!input.trim() || !canType}
            className="p-3 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors shrink-0"
          >
            <Send size={15} />
          </button>
        </div>
        <p className="text-[10px] text-luna-dim/50 mt-1.5">Enter to send · Shift+Enter newline</p>
      </div>
    </div>
  )
}

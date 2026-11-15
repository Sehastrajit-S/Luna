import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useState } from 'react'
import { Copy, Check, ThumbsUp, ThumbsDown, Loader2, RotateCcw } from 'lucide-react'
import { Message } from '../../types'
import { format } from 'date-fns'
import { authHeaders } from '../../api/client'

interface Props {
  message: Message
  streaming?: boolean
  userMessage?: string   // the user's message that prompted this response
  trainMode?: boolean    // show RLHF controls
}

const MOOD_COLORS: Record<string, string> = {
  happy:       'from-violet-500 to-purple-600',
  playful:     'from-pink-500 to-violet-500',
  thoughtful:  'from-blue-500 to-violet-500',
  excited:     'from-amber-400 to-violet-500',
  concerned:   'from-red-400 to-violet-500',
  warm:        'from-orange-400 to-violet-500',
  neutral:     'from-violet-500 to-indigo-600',
  curious:     'from-cyan-400 to-violet-500',
  melancholic: 'from-slate-400 to-violet-500',
}

function LunaAvatar({ mood }: { mood?: string }) {
  const gradient = MOOD_COLORS[mood ?? 'neutral'] ?? MOOD_COLORS.neutral
  return (
    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${gradient} flex items-center justify-center shadow-glow flex-shrink-0 mt-1`}>
      <span className="text-white text-xs font-bold select-none">L</span>
    </div>
  )
}

export function MessageBubble({ message, streaming, userMessage, trainMode }: Props) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)
  const [regenerating, setRegenerating] = useState(false)
  const [alternatives, setAlternatives] = useState<string[]>([])
  const [picked, setPicked] = useState<number | null>(null)
  const [saved, setSaved] = useState(false)
  const isLuna = message.role === 'assistant'
  const base = window.electronAPI?.apiBase ?? ''

  const copy = async () => {
    const text = message.content
    try {
      if (window.electronAPI?.copyText) {
        await window.electronAPI.copyText(text)
      } else {
        await navigator.clipboard.writeText(text)
      }
    } catch {
      // last-resort fallback
      const el = document.createElement('textarea')
      el.value = text
      el.style.position = 'fixed'
      el.style.opacity = '0'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleLike = async () => {
    setFeedback('up')
    setAlternatives([])
    // Save as positive example
    await fetch(`${base}/api/train/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ message: userMessage ?? '', chosen: message.content, rejected: [], mode: 'response' }),
    }).catch(() => {})
  }

  const handleDislike = async () => {
    if (regenerating) return
    setFeedback('down')
    setAlternatives([])
    setPicked(null)
    setSaved(false)
    setRegenerating(true)
    try {
      const r = await fetch(`${base}/api/train/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ message: userMessage ?? '', current: message.content }),
      })
      const d = await r.json()
      setAlternatives(d.options ?? [])
    } catch {}
    setRegenerating(false)
  }

  const pickAlternative = async (idx: number) => {
    setPicked(idx)
  }

  const savePreference = async () => {
    if (picked === null) return
    const chosen = alternatives[picked]
    const rejected = alternatives.filter((_, i) => i !== picked)
    await fetch(`${base}/api/train/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ message: userMessage ?? '', chosen, rejected, mode: 'response' }),
    }).catch(() => {})
    setSaved(true)
  }

  const parseTimestamp = (timestamp: string) => {
    const hasOffset = /[zZ]|[+\-]\d{2}(:?\d{2})?$/.test(timestamp)
    return new Date(hasOffset ? timestamp : `${timestamp}Z`)
  }

  // Strip embedded command tokens from displayed content
  const displayContent = message.content
    .replace(/\[LAUNCH:[^\]]+\]/g, '')
    .replace(/\[TASK:[^\]]+\]/g, '')
    .replace(/\[EVENT:[^\]]+\]/g, '')
    .replace(/\[WIDGET:[^\]]+\]/g, '')
    .replace(/\[MAP:[^\]]+\]/g, '')
    .replace(/\[BROWSE:[^\]]+\]/g, '')
    .replace(/\[SPOTIFY:[^\]]*\]/g, '')
    .replace(/\[AWAY\]/g, '')
    .trim()
  const autoChunk = (content: string) => {
    if (!isLuna || content.includes('\n\n') || content.includes('```')) return [content]
    const sentences = content.split(/(?<=[.!?])\s+/).filter(Boolean)
    if (sentences.length < 2) return [content]
    if (sentences.length === 2 && sentences[0].split(/\s+/).length <= 4) return sentences
    if (sentences.length >= 3 && sentences[0].split(/\s+/).length <= 4) {
      return [sentences[0], sentences.slice(1).join(' ')]
    }
    if (content.split(/\s+/).length <= 22) return [content]

    const chunks: string[] = []
    let current: string[] = []
    let words = 0
    sentences.forEach((sentence) => {
      const count = sentence.split(/\s+/).length
      if (current.length && words + count > 12) {
        chunks.push(current.join(' '))
        current = [sentence]
        words = count
      } else {
        current.push(sentence)
        words += count
      }
    })
    if (current.length) chunks.push(current.join(' '))
    return chunks.slice(0, 2)
  }
  const lunaParts = isLuna
    ? displayContent.split(/\n{2,}/).flatMap((part) => autoChunk(part.trim())).filter(Boolean)
    : [displayContent]

  const renderMarkdown = (content: string, showCursor: boolean) => (
    <div className="prose prose-invert prose-sm max-w-none text-luna-text leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children }) {
            const isBlock = className?.includes('language-')
            return isBlock ? (
              <pre className="bg-luna-surface border border-luna-border rounded-lg p-3 overflow-x-auto my-2">
                <code className="text-luna-accent text-xs font-mono">{children}</code>
              </pre>
            ) : (
              <code className="bg-luna-surface px-1.5 py-0.5 rounded text-luna-accent text-xs font-mono">
                {children}
              </code>
            )
          },
          p({ children }) {
            return <p className="mb-2 last:mb-0 text-luna-text">{children}</p>
          },
          ul({ children }) {
            return <ul className="list-disc list-inside space-y-1 mb-2 text-luna-text">{children}</ul>
          },
          ol({ children }) {
            return <ol className="list-decimal list-inside space-y-1 mb-2 text-luna-text">{children}</ol>
          },
          strong({ children }) {
            return <strong className="text-luna-accent font-semibold">{children}</strong>
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {showCursor && (
        <span className="inline-block w-1.5 h-4 bg-luna-primary animate-pulse ml-0.5 rounded-sm" />
      )}
    </div>
  )

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className={`flex gap-3 group ${isLuna ? 'justify-start' : 'justify-end'}`}
    >
      {isLuna && <LunaAvatar />}

      <div className={`max-w-[80%] ${isLuna ? '' : 'order-first'}`}>
        {isLuna ? (
          <div className="relative">
            <div className="space-y-1.5">
              {lunaParts.map((part, index) => (
                <div
                  key={`${message.id}-${index}`}
                  className={`bg-luna-card border border-luna-border rounded-2xl px-4 py-3 shadow-luna ${
                    index === 0 ? 'rounded-tl-sm' : 'ml-2'
                  }`}
                >
                  {renderMarkdown(part, Boolean(streaming && index === lunaParts.length - 1))}
                </div>
              ))}
              {streaming && lunaParts.length === 0 && (
                <div className="bg-luna-card border border-luna-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-luna">
                  {renderMarkdown('', true)}
                </div>
              )}
            </div>

            {/* Copy */}
            <button
              onClick={copy}
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg bg-luna-surface border border-luna-border text-luna-dim hover:text-luna-text"
            >
              {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
            </button>

            {/* RLHF feedback — thumb buttons, always visible after streaming */}
            {!streaming && (
              <div className={`flex items-center gap-0.5 mt-1.5 pl-0.5 ${!trainMode ? 'opacity-0 group-hover:opacity-100 transition-opacity' : ''}`}>
                <button
                  onClick={handleLike}
                  title="Good response"
                  className={`p-1.5 rounded-lg border transition-colors ${
                    feedback === 'up'
                      ? 'bg-green-500/20 border-green-500/30 text-green-400'
                      : 'border-transparent text-luna-dim/40 hover:text-green-400 hover:bg-green-500/10'
                  }`}
                >
                  <ThumbsUp size={11} />
                </button>
                <button
                  onClick={handleDislike}
                  disabled={regenerating}
                  title="Show alternatives"
                  className={`p-1.5 rounded-lg border transition-colors ${
                    feedback === 'down'
                      ? 'bg-red-500/15 border-red-500/20 text-red-400'
                      : 'border-transparent text-luna-dim/40 hover:text-red-400 hover:bg-red-500/10'
                  }`}
                >
                  {regenerating
                    ? <Loader2 size={11} className="animate-spin" />
                    : <ThumbsDown size={11} />}
                </button>
                {feedback === 'up' && <span className="text-[10px] text-green-400/50 ml-0.5">saved</span>}
              </div>
            )}

            {/* Alternatives */}
            <AnimatePresence>
              {alternatives.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mt-3 space-y-2"
                >
                  <p className="text-[10px] uppercase tracking-wider text-luna-dim pl-0.5">
                    Pick a better response
                  </p>
                  {alternatives.map((alt, i) => (
                    <button
                      key={i}
                      onClick={() => pickAlternative(i)}
                      className={`w-full text-left rounded-xl border px-4 py-3 text-sm transition-all ${
                        picked === i
                          ? 'border-violet-500/60 bg-violet-500/10 text-luna-text'
                          : 'border-luna-border bg-luna-surface text-luna-dim hover:text-luna-text'
                      }`}
                    >
                      <div className="flex items-start gap-2.5">
                        <span className={`font-mono text-[10px] font-bold mt-0.5 shrink-0 ${picked === i ? 'text-violet-400' : 'text-luna-dim'}`}>
                          {['A','B','C'][i]}
                        </span>
                        <span className="leading-relaxed">{alt}</span>
                      </div>
                    </button>
                  ))}
                  {picked !== null && !saved && (
                    <motion.button
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      onClick={savePreference}
                      className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 transition-colors pl-0.5 pt-1"
                    >
                      <Check size={11} /> Save preference
                    </motion.button>
                  )}
                  {saved && <p className="text-[11px] text-green-400/70 pl-0.5">Preference saved.</p>}
                </motion.div>
              )}
            </AnimatePresence>

            {regenerating && (
              <div className="flex items-center gap-2 mt-2 pl-0.5 text-[11px] text-luna-dim">
                <Loader2 size={11} className="animate-spin" /> Generating alternatives...
              </div>
            )}
          </div>
        ) : (
          <div className="bg-luna-primary/20 border border-luna-primary/30 rounded-2xl rounded-tr-sm px-4 py-3">
            <p className="text-luna-text text-sm leading-relaxed whitespace-pre-wrap">{displayContent}</p>
          </div>
        )}

        <p className={`text-[10px] text-luna-dim mt-1 ${isLuna ? 'pl-1' : 'text-right pr-1'}`}>
          {format(parseTimestamp(message.created_at), 'h:mm a')}
        </p>
      </div>
    </motion.div>
  )
}

import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { MessageBubble } from './MessageBubble'
import { InputBar } from './InputBar'
import { useChat } from '../../hooks/useChat'
import { useStore } from '../../store'
import { Sparkles, Copy, ShieldAlert, CheckCircle, XCircle, ListChecks } from 'lucide-react'
import { VoiceOrb } from '../Voice/VoiceOrb'
import { api } from '../../api/client'

function ConfirmationBanner() {
  const { pendingConfirmation, clearPendingConfirmation } = useStore()
  if (!pendingConfirmation) return null

  const { confirm_id, message } = pendingConfirmation

  const answer = async (approved: boolean) => {
    try {
      await api.confirmTool(confirm_id, approved)
    } catch (_) {}
    clearPendingConfirmation()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      className="absolute top-14 left-1/2 -translate-x-1/2 z-50 w-[90%] max-w-sm"
    >
      <div className="flex items-start gap-3 bg-amber-950/90 border border-amber-500/40 backdrop-blur rounded-xl px-4 py-3 shadow-lg">
        <ShieldAlert size={18} className="text-amber-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-amber-200 font-medium mb-2">{message}</p>
          <div className="flex gap-2">
            <button
              onClick={() => answer(true)}
              className="flex items-center gap-1 text-xs bg-emerald-700/70 hover:bg-emerald-600/80 text-emerald-100 px-3 py-1 rounded-lg transition-colors"
            >
              <CheckCircle size={12} /> Yes
            </button>
            <button
              onClick={() => answer(false)}
              className="flex items-center gap-1 text-xs bg-red-900/60 hover:bg-red-800/70 text-red-200 px-3 py-1 rounded-lg transition-colors"
            >
              <XCircle size={12} /> No
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function PlanProgressBar() {
  const { activePlan } = useStore()
  if (!activePlan) return null
  const pct = Math.round((activePlan.current / activePlan.total) * 100)

  return (
    <motion.div
      initial={{ opacity: 0, scaleX: 0 }}
      animate={{ opacity: 1, scaleX: 1 }}
      exit={{ opacity: 0 }}
      className="absolute top-14 right-4 z-40 w-52"
    >
      <div className="bg-luna-surface/90 border border-luna-border rounded-xl px-3 py-2 text-xs text-luna-muted backdrop-blur">
        <div className="flex items-center gap-2 mb-1.5">
          <ListChecks size={12} className="text-luna-primary" />
          <span>Step {activePlan.current}/{activePlan.total}</span>
        </div>
        <div className="h-1 rounded-full bg-luna-border overflow-hidden">
          <div
            className="h-full bg-luna-primary rounded-full transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </motion.div>
  )
}

function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      className="flex gap-3 justify-start"
    >
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-glow flex-shrink-0 mt-1">
        <span className="text-white text-xs font-bold">L</span>
      </div>
      <div className="bg-luna-card border border-luna-border rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-luna-primary animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  )
}

function ProactiveToast() {
  const { proactiveMessages, clearProactive } = useStore()
  if (!proactiveMessages.length) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="absolute top-3 left-1/2 -translate-x-1/2 z-50 bg-luna-primary/90 backdrop-blur text-white text-sm px-4 py-2 rounded-xl shadow-luna max-w-sm text-center"
    >
      {proactiveMessages[0]}
      <button onClick={clearProactive} className="ml-2 opacity-60 hover:opacity-100">✕</button>
    </motion.div>
  )
}

function WelcomeScreen() {
  return (
    <div className="flex items-center justify-center h-full select-none">
      <VoiceOrb size={200} showLabel />
    </div>
  )
}

export function ChatWindow() {
  const { messages, isStreaming, streamingContent, sendMessage } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)
  const { personality } = useStore()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Handle suggestion clicks from WelcomeScreen
  useEffect(() => {
    const handler = (e: Event) => sendMessage((e as CustomEvent).detail)
    window.addEventListener('luna-suggest', handler)
    return () => window.removeEventListener('luna-suggest', handler)
  }, [sendMessage])

  const mood = personality?.current_mood

  const copyChat = async () => {
    const chatText = messages
      .map(msg => {
        const role = msg.role === 'user' ? 'You' : 'Luna'
        const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        return `[${time}] ${role}: ${msg.content}`
      })
      .join('\n\n')
    try {
      if (window.electronAPI?.copyText) {
        await window.electronAPI.copyText(chatText)
      } else {
        await navigator.clipboard.writeText(chatText)
      }
    } catch {
      const el = document.createElement('textarea')
      el.value = chatText
      el.style.position = 'fixed'
      el.style.opacity = '0'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
  }

  return (
    <div className="flex flex-col h-full relative">
      <ProactiveToast />
      <AnimatePresence>
        <ConfirmationBanner key="confirm" />
        <PlanProgressBar key="plan" />
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-luna-border bg-luna-surface/50 backdrop-blur">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-luna-primary" />
          <span className="text-xs text-luna-muted font-medium">
            {mood ? `${mood.charAt(0).toUpperCase() + mood.slice(1)} · ` : ''}Luna is listening
          </span>
        </div>
        <div className="flex items-center gap-3">
          {messages.length > 0 && (
            <button
              onClick={copyChat}
              className="flex items-center gap-1 text-xs text-luna-muted hover:text-luna-accent transition-colors"
              title="Copy entire chat"
            >
              <Copy size={12} />
              Copy Chat
            </button>
          )}
          {personality && (
            <div className="flex gap-3 text-[10px] text-luna-dim">
              <span>memory {Math.round(personality.verbosity * 100)}% verbose</span>
              <span>·</span>
              <span>{personality.total_interactions} interactions</span>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 ? (
          <WelcomeScreen />
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg, idx) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                userMessage={
                  msg.role === 'assistant'
                    ? [...messages.slice(0, idx)].reverse().find(m => m.role === 'user')?.content
                    : undefined
                }
              />
            ))}
            {isStreaming && streamingContent && (
              <MessageBubble
                key="streaming"
                message={{
                  id: -1,
                  role: 'assistant',
                  content: streamingContent,
                  created_at: new Date().toISOString(),
                }}
                streaming
              />
            )}
            {isStreaming && !streamingContent && <TypingIndicator key="typing" />}
          </AnimatePresence>
        )}
        <div ref={bottomRef} />
      </div>

      <InputBar onSend={sendMessage} disabled={isStreaming} />
    </div>
  )
}

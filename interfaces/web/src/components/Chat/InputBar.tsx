import { useState, useRef, KeyboardEvent } from 'react'
import { Send, Loader2 } from 'lucide-react'
import { motion } from 'framer-motion'

interface Props {
  onSend: (msg: string) => void
  disabled?: boolean
}

export function InputBar({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (ref.current) {
      ref.current.style.height = 'auto'
    }
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const onInput = () => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="border-t border-luna-border bg-luna-surface/80 backdrop-blur px-4 py-3"
    >
      <div className="flex items-end gap-3 max-w-3xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => { setValue(e.target.value); onInput() }}
            onKeyDown={onKey}
            rows={1}
            placeholder="Talk to Luna…"
            disabled={disabled}
            className="w-full resize-none bg-luna-card border border-luna-border rounded-xl px-4 py-3 text-luna-text placeholder-luna-dim text-sm leading-relaxed outline-none focus:border-luna-primary/50 focus:ring-1 focus:ring-luna-primary/30 transition-all disabled:opacity-50 min-h-[48px] max-h-40"
            style={{ height: 48 }}
          />
          <p className="absolute bottom-2 right-3 text-[10px] text-luna-dim select-none">
            {value.length > 0 && `${value.length}`}
          </p>
        </div>

        <button
          onClick={submit}
          disabled={!value.trim() || disabled}
          className="w-10 h-10 rounded-xl bg-luna-primary hover:bg-luna-glow disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center flex-shrink-0 transition-all shadow-glow hover:shadow-luna"
        >
          {disabled ? (
            <Loader2 size={16} className="text-white animate-spin" />
          ) : (
            <Send size={16} className="text-white" />
          )}
        </button>
      </div>
      <p className="text-center text-[10px] text-luna-dim mt-2">
        Enter to send · Shift+Enter for newline
      </p>
    </motion.div>
  )
}

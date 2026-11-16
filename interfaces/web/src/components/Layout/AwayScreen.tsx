import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useStore } from '../../store'
import { authHeaders } from '../../api/client'

export function AwayScreen() {
  const { awayMode, exitAwayMode } = useStore(s => ({
    awayMode: s.awayMode,
    exitAwayMode: s.exitAwayMode,
  }))
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (awayMode) {
      window.electronAPI?.awayEnter?.()
    } else {
      window.electronAPI?.awayExit?.()
    }
  }, [awayMode])

  useEffect(() => {
    if (!awayMode) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleDismiss()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [awayMode])

  const handleDismiss = () => {
    const base = window.electronAPI?.apiBase ?? ''
    fetch(`${base}/api/voice/away/off`, { method: 'POST', headers: authHeaders() }).catch(() => {})
    window.electronAPI?.awayExit?.()
    exitAwayMode()
  }

  const pad = (n: number) => n.toString().padStart(2, '0')
  const h = pad(time.getHours())
  const m = pad(time.getMinutes())
  const s = pad(time.getSeconds())
  const dateStr = time.toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  })

  return (
    <AnimatePresence>
      {awayMode && (
        <motion.div
          className="fixed inset-0 flex flex-col items-center justify-center select-none cursor-pointer"
          style={{ background: 'rgba(2,2,8,0.97)', backdropFilter: 'blur(8px)', zIndex: 300 }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          onClick={handleDismiss}
        >
          {/* Luna label */}
          <div className="absolute top-8 left-0 right-0 flex justify-center">
            <span
              className="text-[10px] font-mono tracking-[0.4em] uppercase"
              style={{ color: 'rgba(255,255,255,0.1)' }}
            >
              Luna
            </span>
          </div>

          {/* Clock */}
          <motion.div
            className="flex flex-col items-center"
            animate={{ opacity: [0.6, 0.85, 0.6] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
          >
            <div
              className="font-mono tabular-nums"
              style={{
                fontSize: 'clamp(80px, 14vw, 150px)',
                fontWeight: 100,
                letterSpacing: '-0.03em',
                color: 'rgba(255,255,255,0.78)',
                lineHeight: 1,
              }}
            >
              {h}:{m}
              <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.42em' }}>:{s}</span>
            </div>

            <div
              className="font-mono mt-5 uppercase"
              style={{
                fontSize: 12,
                letterSpacing: '0.22em',
                color: 'rgba(255,255,255,0.22)',
              }}
            >
              {dateStr}
            </div>
          </motion.div>

          {/* Hint */}
          <div className="absolute bottom-8 left-0 right-0 flex justify-center">
            <span
              className="text-[10px] font-mono tracking-widest uppercase"
              style={{ color: 'rgba(255,255,255,0.08)' }}
            >
              say "luna" to wake · click or esc to dismiss
            </span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

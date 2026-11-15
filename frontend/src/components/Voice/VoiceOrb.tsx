import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { authHeaders } from '../../api/client'
import { useStore } from '../../store'

type VoiceState = 'idle' | 'listening' | 'followup' | 'active' | 'processing' | 'speaking'

const OUTER_SPEED: Record<VoiceState, number> = {
  idle: 0, listening: 0, followup: 7, active: 3, processing: 1.2, speaking: 4,
}
const INNER_SPEED: Record<VoiceState, number> = {
  idle: 0, listening: 0, followup: 5, active: 2, processing: 0.8, speaking: 2.5,
}
const PULSE: Record<VoiceState, number[]> = {
  idle: [1, 1], listening: [1, 1], followup: [1, 1.06, 1],
  active: [1, 1.12, 1], processing: [1, 1.08, 1], speaking: [1, 1.22, 1],
}
const PULSE_DUR: Record<VoiceState, number> = {
  idle: 2, listening: 2, followup: 3.5, active: 1.4, processing: 0.9, speaking: 1.2,
}
const SUBTITLE: Record<VoiceState, string> = {
  idle:       'voice off',
  listening:  'sleeping',
  followup:   'listening...',
  active:     'listening...',
  processing: 'thinking...',
  speaking:   'speaking...',
}

interface VoiceOrbProps {
  size?:      number        // default 36
  showLabel?: boolean       // show subtitle text below
  onToggle?:  () => void    // override default voice-toggle behaviour
}

export function VoiceOrb({ size = 36, showLabel = false, onToggle }: VoiceOrbProps) {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const esRef = useRef<EventSource | null>(null)
  const { openMapOverlay, setMapPendingSearch, setMapPendingRoute } = useStore(s => ({
    openMapOverlay: s.openMapOverlay,
    setMapPendingSearch: s.setMapPendingSearch,
    setMapPendingRoute: s.setMapPendingRoute,
  }))

  useEffect(() => {
    const base = window.electronAPI?.apiBase ?? ''

    const syncState = () =>
      fetch(`${base}/api/voice/state`, { headers: authHeaders() })
        .then(r => r.json())
        .then(d => { setVoiceState(d.state) })
        .catch(() => {})

    syncState()
    const pollTimer = setInterval(syncState, 4000)

    const es = new EventSource(`${base}/api/voice/events`)
    esRef.current = es
    es.onmessage = e => {
      if (e.data === 'ping') return
      try {
        const d = JSON.parse(e.data)
        if (d.type === 'quit') {
          window.electronAPI?.quit?.()
          return
        }
        if (d.type === 'away') {
          if (d.action === 'on') useStore.getState().enterAwayMode()
          else useStore.getState().exitAwayMode()
          return
        }
        if (d.type === 'map') {
          if (d.action === 'close') {
            useStore.getState().closeMapOverlay()
          } else if (d.action === 'search' && d.query) {
            openMapOverlay()
            setMapPendingSearch(d.query)
          } else if (d.action === 'route' && d.query) {
            openMapOverlay()
            setMapPendingRoute(d.query)
          } else {
            openMapOverlay()
          }
          return
        }
        if (d.type === 'widget') {
          useStore.getState().openDynamicWidget({
            kind: d.kind ?? 'summary',
            title: d.title ?? 'Visual',
            body: d.body ?? '',
          })
          return
        }
        if (d.state) {
          setVoiceState(d.state as VoiceState)
        }
      } catch { /* skip */ }
    }
    return () => { es.close(); clearInterval(pollTimer) }
  }, [openMapOverlay])

  const toggle = () => {
    if (onToggle) { onToggle(); return }
    const base = window.electronAPI?.apiBase ?? ''
    fetch(`${base}/api/voice/toggle`, { method: 'POST', headers: authHeaders() })
      .then(r => r.json())
      .then(d => { setVoiceState(d.state) })
      .catch(() => {})
  }

  const isActive    = voiceState !== 'idle' && voiceState !== 'listening'
  const isListening = voiceState === 'active' || voiceState === 'followup'
  const outerSpeed = OUTER_SPEED[voiceState]
  const innerSpeed = INNER_SPEED[voiceState]

  const outerColor = isActive ? 'rgba(139,92,246,0.75)' : 'rgba(100,116,139,0.25)'
  const innerColor = isActive ? 'rgba(167,139,250,0.60)' : 'rgba(100,116,139,0.15)'
  const glowColor  = isActive ? 'rgba(139,92,246,0.35)'  : 'transparent'

  const s           = size / 36
  const perspective = Math.round(220 * s)
  const nucleusPx   = Math.max(4, Math.round(6 * s))
  const borderOuter = size > 80 ? 2   : 1.5
  const borderInner = size > 80 ? 1.5 : 1
  const glowSize    = Math.round(10 * s)

  const orb = (
    <button
      onClick={toggle}
      title={SUBTITLE[voiceState]}
      className="relative flex items-center justify-center focus:outline-none flex-shrink-0"
      style={{ width: size, height: size, WebkitAppRegion: 'no-drag' } as React.CSSProperties}
    >
      <div
        style={{
          width: '100%', height: '100%',
          perspective: `${perspective}px`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {/* ── Listening ripple (expands + fades outward) ─────────────── */}
        {isListening && (
          <motion.div
            style={{
              position: 'absolute',
              width: '100%', height: '100%',
              borderRadius: '50%',
              border: `1px solid rgba(139,92,246,0.5)`,
            }}
            animate={{ scale: [1, 1.65], opacity: [0.55, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
          />
        )}

        {/* ── Outer orbital ring ───────────────────────────────────────── */}
        <motion.div
          style={{
            position: 'absolute',
            width: '100%', height: '100%',
            borderRadius: '50%',
            border: `${borderOuter}px solid ${outerColor}`,
            boxShadow: `0 0 ${glowSize}px ${glowColor}`,
            rotateX: 62,
          }}
          animate={
            outerSpeed > 0
              ? { rotateZ: [0, 360], scale: PULSE[voiceState] }
              : { rotateZ: 0,        scale: 1 }
          }
          transition={
            outerSpeed > 0
              ? {
                  rotateZ: { duration: outerSpeed, repeat: Infinity, ease: 'linear', repeatType: 'loop' },
                  scale:   { duration: PULSE_DUR[voiceState], repeat: Infinity, ease: 'easeInOut' },
                }
              : { duration: 0.4 }
          }
        />

        {/* ── Inner orbital ring (cross-axis) ─────────────────────────── */}
        <motion.div
          style={{
            position: 'absolute',
            width: '58%', height: '58%',
            borderRadius: '50%',
            border: `${borderInner}px solid ${innerColor}`,
            rotateX: 62,
            rotateY: 52,
          }}
          animate={
            innerSpeed > 0
              ? { rotateZ: [360, 0] }
              : { rotateZ: 0 }
          }
          transition={
            innerSpeed > 0
              ? { duration: innerSpeed, repeat: Infinity, ease: 'linear', repeatType: 'loop' }
              : { duration: 0.4 }
          }
        />

        {/* ── Centre nucleus ───────────────────────────────────────────── */}
        <motion.div
          style={{
            borderRadius: '50%',
            position: 'absolute',
            width: nucleusPx,
            height: nucleusPx,
          }}
          animate={
            isActive
              ? { backgroundColor: ['#8b5cf6', '#c4b5fd', '#8b5cf6'], scale: [1, 1.4, 1] }
              : { backgroundColor: '#334155', scale: 1 }
          }
          transition={
            isActive
              ? { duration: PULSE_DUR[voiceState], repeat: Infinity, ease: 'easeInOut' }
              : { duration: 0.4 }
          }
        />
      </div>
    </button>
  )

  if (!showLabel) return orb

  return (
    <div className="flex flex-col items-center" style={{ gap: Math.round(16 * s) }}>
      {orb}
      <AnimatePresence mode="wait">
        <motion.p
          key={voiceState}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25 }}
          className="text-xs tracking-widest uppercase select-none"
          style={{
            color: isActive ? 'rgba(139,92,246,0.85)' : 'rgba(100,116,139,0.5)',
            letterSpacing: '0.18em',
          }}
        >
          {SUBTITLE[voiceState]}
        </motion.p>
      </AnimatePresence>
    </div>
  )
}

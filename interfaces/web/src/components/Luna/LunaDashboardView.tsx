import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useStore } from '../../store'
import { P } from './palette'
import { LiveClock } from './shared/LiveClock'
import { DefaultLayout } from './layout/DefaultLayout'
import { DEFAULT_LAYOUT, saveLayout } from './layout/gridConfig'
import { ModeCycleButton } from '../Layout/TitleBar'

export function LunaDashboardView() {
  const exitLunaDashboard = useStore(s => s.exitLunaDashboard)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [layoutKey, setLayoutKey] = useState(0)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !expanded) exitLunaDashboard() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [exitLunaDashboard, expanded])

  const resetLayout = () => {
    saveLayout(DEFAULT_LAYOUT)
    setLayoutKey(k => k + 1)
  }

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.28 }}
      style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', flexDirection: 'column', background: '#09090f', overflow: 'hidden' }}
    >
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 44% 36% at 50% 44%, rgba(139,92,246,0.12) 0%, transparent 72%)', pointerEvents: 'none' }} />

      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: `1px solid ${P.border}`, background: P.surface, backdropFilter: 'blur(8px)', flexShrink: 0, zIndex: 60, WebkitAppRegion: 'drag' } as React.CSSProperties}>
        <span style={{ fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.45em', textTransform: 'uppercase', color: P.textDim }}>Luna</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
          <ModeCycleButton />
          <button
            onClick={resetLayout}
            title="Reset widget positions to default"
            style={{ background: 'none', border: `1px solid ${P.border}`, cursor: 'pointer', color: P.textDim, fontFamily: 'monospace', fontSize: 8, letterSpacing: '0.18em', padding: '3px 8px', transition: 'all 0.15s' }}
            onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.text; el.style.borderColor = `rgba(139,92,246,0.5)` }}
            onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.textDim; el.style.borderColor = P.border }}
          >
            RESET LAYOUT
          </button>
          <LiveClock />
        </div>
      </div>

      <motion.div
        key="default"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
      >
        <DefaultLayout key={layoutKey} expanded={expanded} setExpanded={setExpanded} />
      </motion.div>
    </motion.div>
  )
}

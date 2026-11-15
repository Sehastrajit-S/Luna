import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { P } from '../palette'
import { Corners } from './Corners'

export function ExpandedOverlay({
  title, onClose, children, headerRight,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
  headerRight?: React.ReactNode
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      style={{ position: 'absolute', inset: 0, zIndex: 50, display: 'flex', flexDirection: 'column', background: 'rgba(1,0,8,0.98)', border: `1px solid ${P.borderBright}`, backdropFilter: 'blur(12px)' }}
    >
      <Corners color={P.borderBright} />
      <div
        role="button" tabIndex={0}
        onClick={onClose}
        onKeyDown={e => e.key === 'Enter' && onClose()}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 14px', borderBottom: `1px solid ${P.border}`, flexShrink: 0, cursor: 'pointer', userSelect: 'none', transition: 'background 0.15s' }}
        onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.07)')}
        onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
      >
        <span style={{ fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.3em', textTransform: 'uppercase', color: P.text }}>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }} onClick={e => e.stopPropagation()}>
          {headerRight}
          <button
            onClick={onClose}
            style={{ background: 'none', border: `1px solid ${P.border}`, cursor: 'pointer', color: P.textDim, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 22, height: 22, transition: 'all 0.15s' }}
            onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.text; el.style.borderColor = `${P.glow}0.5)` }}
            onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.textDim; el.style.borderColor = P.border }}
          >
            <X size={11} strokeWidth={1.5} />
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>{children}</div>
    </motion.div>
  )
}

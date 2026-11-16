import { motion } from 'framer-motion'
import { useStore } from '../../store'

export function LunaDashboardToggle() {
  const { viewMode, enterLunaDashboard, exitLunaDashboard } = useStore(s => ({
    viewMode: s.viewMode,
    enterLunaDashboard: s.enterLunaDashboard,
    exitLunaDashboard: s.exitLunaDashboard,
  }))

  const active = viewMode === 'luna'
  const toggle = () => (active ? exitLunaDashboard() : enterLunaDashboard())

  return (
    <button
      onClick={toggle}
      title={active ? 'Exit Luna dashboard' : 'Luna dashboard'}
      className="relative flex items-center justify-center focus:outline-none"
      style={{
        width: 32,
        height: 32,
        WebkitAppRegion: 'no-drag',
      } as React.CSSProperties}
    >
      {/* Outer ring — rotates slowly */}
      <motion.div
        style={{
          position: 'absolute',
          width: 26,
          height: 26,
          borderRadius: '50%',
          border: `1px solid ${active ? 'rgba(167,139,250,0.9)' : 'rgba(139,92,246,0.35)'}`,
          borderTopColor: active ? 'rgba(216,180,254,1)' : 'rgba(167,139,250,0.7)',
          boxShadow: active
            ? '0 0 8px rgba(139,92,246,0.7), inset 0 0 6px rgba(139,92,246,0.25)'
            : '0 0 4px rgba(139,92,246,0.2)',
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
      />

      {/* Inner dot — pulses when active */}
      <motion.div
        style={{ borderRadius: '50%', position: 'relative', zIndex: 1 }}
        animate={
          active
            ? {
                width: [7, 9, 7],
                height: [7, 9, 7],
                backgroundColor: ['#a78bfa', '#e9d5ff', '#a78bfa'],
                boxShadow: [
                  '0 0 6px rgba(167,139,250,0.8)',
                  '0 0 14px rgba(216,180,254,1)',
                  '0 0 6px rgba(167,139,250,0.8)',
                ],
              }
            : { width: 7, height: 7, backgroundColor: '#6d28d9', boxShadow: '0 0 4px rgba(109,40,217,0.5)' }
        }
        transition={
          active
            ? { duration: 2.2, repeat: Infinity, ease: 'easeInOut' }
            : { duration: 0.3 }
        }
      />
    </button>
  )
}

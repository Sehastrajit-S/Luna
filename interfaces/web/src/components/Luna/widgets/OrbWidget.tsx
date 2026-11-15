import { motion, AnimatePresence } from 'framer-motion'
import { P } from '../palette'
import { VoiceOrb } from '../../Voice/VoiceOrb'
import { useStore } from '../../../store'

export function OrbCluster() {
  const pulse = useStore(s => s.proactivePulse)

  const rings = [
    { size: 244, dur: 28, rev: false, op: 0.14, bT: `${P.bright}0.5)`,  bR: `${P.glow}0.06)` },
    { size: 192, dur: 16, rev: true,  op: 0.22, bT: `${P.bright}0.72)`, bB: `${P.bright}0.5)`, bL: `${P.glow}0.08)`, bR: `${P.glow}0.08)` },
    { size: 138, dur: 9,  rev: false, op: 0.32, bT: `${P.bright}0.85)`, bR: `${P.bright}0.6)`, bB: `${P.glow}0.12)`, bL: `${P.glow}0.12)`, bW: 1.5 },
  ]

  return (
    <div style={{ position: 'relative', width: 248, height: 248, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      {rings.map((ring, i) => (
        <motion.div key={i}
          style={{ position: 'absolute', width: ring.size, height: ring.size, borderRadius: '50%', border: `${ring.bW ?? 1}px solid ${P.glow}${ring.op})`, borderTopColor: ring.bT, borderRightColor: ring.bR ?? `${P.glow}${ring.op})`, borderBottomColor: (ring as any).bB ?? `${P.glow}${ring.op})`, borderLeftColor: (ring as any).bL ?? `${P.glow}${ring.op})` }}
          animate={{ rotate: ring.rev ? -360 : 360, scale: pulse ? 1.06 : 1 }}
          transition={{ rotate: { duration: ring.dur, repeat: Infinity, ease: 'linear' }, scale: { duration: 0.4, ease: 'easeOut' } }}
        />
      ))}

      {/* Ambient pulse ring */}
      <motion.div
        style={{ position: 'absolute', width: 112, height: 112, borderRadius: '50%', border: `1px solid ${P.glow}0.28)` }}
        animate={{ scale: [1, 1.65], opacity: [0.45, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeOut' }}
      />

      {/* Proactive initiation burst */}
      <AnimatePresence>
        {pulse && (
          <motion.div
            key="proactive-burst"
            style={{ position: 'absolute', width: 180, height: 180, borderRadius: '50%', border: `1.5px solid ${P.bright}0.6)`, pointerEvents: 'none' }}
            initial={{ scale: 0.7, opacity: 0.8 }}
            animate={{ scale: 1.7, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.6, ease: 'easeOut' }}
          />
        )}
      </AnimatePresence>

      <div style={{ position: 'relative', zIndex: 5 }}><VoiceOrb size={88} /></div>
    </div>
  )
}

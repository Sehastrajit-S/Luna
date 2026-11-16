import { useEffect, useState } from 'react'
import { P } from '../palette'

export function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    <div style={{ textAlign: 'right', fontFamily: 'monospace', lineHeight: 1.3 }}>
      <div style={{ fontSize: 15, letterSpacing: '0.1em', color: P.text }}>{pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}</div>
      <div style={{ fontSize: 9, letterSpacing: '0.2em', textTransform: 'uppercase', color: P.textDim, marginTop: 1 }}>{now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</div>
    </div>
  )
}

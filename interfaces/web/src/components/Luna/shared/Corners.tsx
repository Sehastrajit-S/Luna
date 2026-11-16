import { P } from '../palette'

export function Corners({ color = P.borderBright }: { color?: string }) {
  const s: React.CSSProperties = { position: 'absolute', width: 9, height: 9, zIndex: 2 }
  const b = `1px solid ${color}`
  return (
    <>
      <div style={{ ...s, top: 0,    left: 0,  borderTop: b,    borderLeft: b  }} />
      <div style={{ ...s, top: 0,    right: 0, borderTop: b,    borderRight: b }} />
      <div style={{ ...s, bottom: 0, left: 0,  borderBottom: b, borderLeft: b  }} />
      <div style={{ ...s, bottom: 0, right: 0, borderBottom: b, borderRight: b }} />
    </>
  )
}

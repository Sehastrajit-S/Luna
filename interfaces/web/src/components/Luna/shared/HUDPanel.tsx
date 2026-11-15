import { P } from '../palette'
import { Corners } from './Corners'

export function HUDPanel({
  id, title, children, style, headerRight, expanded, onExpand,
}: {
  id: string
  title: string
  children: React.ReactNode
  style?: React.CSSProperties
  headerRight?: React.ReactNode
  expanded: boolean
  onExpand: (id: string | null) => void
}) {
  return (
    <div style={{ border: `1px solid ${expanded ? P.borderBright : P.border}`, background: P.bg, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative', height: '100%', transition: 'border-color 0.25s', ...style }}>
      <Corners color={expanded ? P.borderBright : P.border} />
      <div
        className="luna-drag-handle"
        role="button"
        tabIndex={0}
        onClick={() => onExpand(expanded ? null : id)}
        onKeyDown={e => e.key === 'Enter' && onExpand(expanded ? null : id)}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 10px', borderBottom: `1px solid ${P.border}`, background: expanded ? 'rgba(139,92,246,0.1)' : 'transparent', cursor: 'grab', flexShrink: 0, userSelect: 'none', transition: 'background 0.2s', outline: 'none' }}
        onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.09)')}
        onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = expanded ? 'rgba(139,92,246,0.1)' : 'transparent')}
      >
        <span style={{ fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.28em', textTransform: 'uppercase', color: expanded ? P.text : P.textDim, pointerEvents: 'none' }}>
          {title}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div onClick={e => e.stopPropagation()}>{headerRight}</div>
          <span style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, opacity: 0.7, pointerEvents: 'none' }}>
            {expanded ? '▼' : '▲'}
          </span>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>{children}</div>
    </div>
  )
}

export function GridPanel({
  title, children, headerRight, style,
}: {
  title: string
  children: React.ReactNode
  headerRight?: React.ReactNode
  style?: React.CSSProperties
}) {
  return (
    <div style={{ border: `1px solid ${P.border}`, background: P.bg, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative', height: '100%', ...style }}>
      <Corners />
      <div
        className="luna-drag-handle"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 10px', borderBottom: `1px solid ${P.border}`, cursor: 'grab', flexShrink: 0, userSelect: 'none' }}
      >
        <span style={{ fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.28em', textTransform: 'uppercase', color: P.textDim, pointerEvents: 'none' }}>
          {title}
        </span>
        {headerRight}
      </div>
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>{children}</div>
    </div>
  )
}

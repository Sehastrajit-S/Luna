import { useEffect, useState } from 'react'
import { P } from '../palette'
import { fetchLunaCached } from '../lunaDashboardApi'

export interface StockItem { symbol: string; price: number; pct: number; change?: number; source?: string; stale?: boolean; date?: string }
interface StockPoint { date: string; price: number }
interface StockHistory { symbol: string; source: string; points: StockPoint[]; high: number; low: number; open: number; close: number }

export function fmtPrice(sym: string, price: number) {
  if (['BTC', 'ETH'].includes(sym)) return price >= 1000 ? `$${(price / 1000).toFixed(1)}k` : `$${price.toFixed(0)}`
  return `$${price.toFixed(2)}`
}

function StockChart({ points, positive }: { points: StockPoint[]; positive: boolean }) {
  const width = 360, height = 112
  const prices = points.map(p => p.price)
  const min = Math.min(...prices), max = Math.max(...prices)
  const span = max - min || 1
  const d = points.map((p, i) => {
    const x = points.length === 1 ? 0 : (i / (points.length - 1)) * width
    const y = height - ((p.price - min) / span) * height
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  const stroke = positive ? P.green : P.red
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: 112, display: 'block' }}>
      <path d={`M0,${height} ${d.replace(/^M/, 'L')} L${width},${height} Z`} fill={positive ? 'rgba(74,222,128,0.08)' : 'rgba(248,113,113,0.08)'} />
      <path d={d} fill="none" stroke={stroke} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

function StockDetails({ stock }: { stock: StockItem }) {
  const [history, setHistory] = useState<StockHistory | null>(null)
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    let cancelled = false
    setStatus('loading'); setHistory(null)
    fetchLunaCached<StockHistory>(`/api/luna/stocks/${stock.symbol}/history`, 5 * 60_000)
      .then(d => { if (!cancelled) { setHistory(d); setStatus('ok') } })
      .catch(e => { console.warn('[luna] stock history unavailable', e); if (!cancelled) setStatus('error') })
    return () => { cancelled = true }
  }, [stock.symbol])

  const positive = stock.pct >= 0
  return (
    <div style={{ borderBottom: `1px solid ${P.border}`, background: P.card, padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
        <div>
          <div style={{ fontFamily: 'monospace', fontSize: 18, color: P.text, letterSpacing: '0.08em' }}>{stock.symbol}</div>
          <div style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim }}>{stock.source ?? (['BTC', 'ETH'].includes(stock.symbol) ? 'Crypto' : 'Equity')}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'monospace', fontSize: 18, color: P.text }}>{fmtPrice(stock.symbol, stock.price)}</div>
          <div style={{ fontFamily: 'monospace', fontSize: 11, color: positive ? P.green : P.red }}>{positive ? '+' : ''}{stock.pct.toFixed(2)}%</div>
        </div>
      </div>
      {status === 'loading' && <div style={{ height: 112, display: 'flex', alignItems: 'center', justifyContent: 'center', color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>LOADING GRAPH...</div>}
      {status === 'error' && <div style={{ height: 112, display: 'flex', alignItems: 'center', justifyContent: 'center', color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>GRAPH UNAVAILABLE</div>}
      {history && (
        <>
          <StockChart points={history.points} positive={history.close >= history.open} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 10 }}>
            {[['OPEN', fmtPrice(stock.symbol, history.open)], ['CLOSE', fmtPrice(stock.symbol, history.close)], ['HIGH', fmtPrice(stock.symbol, history.high)], ['LOW', fmtPrice(stock.symbol, history.low)]].map(([label, value]) => (
              <div key={label} style={{ border: `1px solid ${P.border}`, padding: '6px 7px', background: 'rgba(9,9,15,0.45)' }}>
                <div style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, letterSpacing: '0.16em' }}>{label}</div>
                <div style={{ fontFamily: 'monospace', fontSize: 10, color: P.text, marginTop: 2 }}>{value}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export function StocksList({ large }: { large?: boolean }) {
  const [stocks, setStocks] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<StockItem | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const d = await fetchLunaCached<unknown>('/api/luna/stocks', 90_000)
        setStocks(Array.isArray(d) ? d : [])
      } catch (e) {
        console.warn('[luna] market unavailable', e); setStocks([])
      }
      setLoading(false)
    }
    load()
    const t = setInterval(load, 90_000)
    return () => clearInterval(t)
  }, [])

  if (loading) return <div style={{ padding: 12, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>loading...</div>
  if (!stocks.length) return <div style={{ padding: 12, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>unavailable</div>

  return (
    <div style={{ overflowY: 'auto', height: '100%', scrollbarWidth: 'none' }}>
      {selected && <StockDetails stock={selected} />}
      {stocks.some(s => s.stale) && (
        <div style={{ padding: '3px 10px', fontSize: 9, fontFamily: 'monospace', color: '#facc15', letterSpacing: '0.08em', borderBottom: `1px solid rgba(139,92,246,0.07)` }}>
          PREV CLOSE — markets closed
        </div>
      )}
      {stocks.map((s, i) => (
        <div key={i} role="button" tabIndex={0} onClick={() => setSelected(s)} onKeyDown={e => e.key === 'Enter' && setSelected(s)}
          style={{ display: 'grid', gridTemplateColumns: '52px 1fr auto', alignItems: 'center', padding: large ? '10px 14px' : '6px 10px', borderBottom: `1px solid rgba(139,92,246,0.07)`, gap: 8, cursor: 'pointer', background: selected?.symbol === s.symbol ? 'rgba(139,92,246,0.11)' : 'transparent', opacity: s.stale ? 0.75 : 1 }}>
          <span style={{ fontFamily: 'monospace', fontSize: large ? 13 : 11, color: P.text, fontWeight: 500 }}>{s.symbol}</span>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontFamily: 'monospace', fontSize: large ? 12 : 11, color: 'rgba(255,255,255,0.58)' }}>{fmtPrice(s.symbol, s.price)}</span>
            {s.stale && s.date && <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#facc1580', letterSpacing: '0.05em' }}>{s.date}</span>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <span style={{ fontFamily: 'monospace', fontSize: large ? 11 : 10, color: s.pct >= 0 ? P.green : P.red, whiteSpace: 'nowrap' }}>{s.pct >= 0 ? '+' : ''}{s.pct.toFixed(2)}%</span>
            {large && s.pct !== 0 && (
              <div style={{ width: 48, height: 2, marginTop: 3, background: 'rgba(255,255,255,0.08)', borderRadius: 1, overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, Math.abs(s.pct) * 20)}%`, height: '100%', background: s.pct >= 0 ? P.green : P.red, borderRadius: 1 }} />
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

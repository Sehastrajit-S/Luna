import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../../../store'
import { P } from '../palette'
import { fetchLunaCached } from '../lunaDashboardApi'
import type { StockItem } from './StocksWidget'

interface Weather { temp_f: number; condition: string; city: string }
interface NewsItem { title: string }
interface DashboardBrief { weather: Weather | null; stocks: StockItem[]; news: NewsItem[] }

export function LunaMessages() {
  const { messages, isStreaming, streamingContent } = useStore(s => ({
    messages: s.messages,
    isStreaming: s.isStreaming,
    streamingContent: s.streamingContent,
  }))
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages.length, streamingContent])

  return (
    <div style={{ width: '100%', maxHeight: '22vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4, scrollbarWidth: 'none' }}>
      <AnimatePresence initial={false}>
        {messages.slice(-7).map(m => (
          <motion.div key={m.id} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
            style={{ fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5, color: m.role === 'user' ? 'rgba(255,255,255,0.42)' : P.text, textAlign: m.role === 'user' ? 'right' : 'left', padding: '3px 0', borderBottom: `1px solid ${P.border}` }}>
            {m.role === 'assistant' && <span style={{ color: P.textDim, marginRight: 6, fontSize: 9 }}>LUNA</span>}
            {m.content}
          </motion.div>
        ))}
      </AnimatePresence>
      {isStreaming && streamingContent && (
        <div style={{ fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5, color: P.text, padding: '3px 0' }}>
          <span style={{ color: P.textDim, marginRight: 6, fontSize: 9 }}>LUNA</span>
          {streamingContent}
          <motion.span animate={{ opacity: [1, 0] }} transition={{ duration: 0.7, repeat: Infinity }}>▊</motion.span>
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}

export function LunaDataBrief() {
  const [brief, setBrief] = useState<DashboardBrief | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [weather, stocksRaw, newsRaw] = await Promise.all([
          fetchLunaCached<Weather | null>('/api/luna/weather', 10 * 60_000),
          fetchLunaCached<unknown>('/api/luna/stocks', 90_000),
          fetchLunaCached<unknown>('/api/luna/news', 4 * 60_000),
        ])
        setBrief({ weather, stocks: Array.isArray(stocksRaw) ? stocksRaw : [], news: Array.isArray(newsRaw) ? newsRaw : [] })
      } catch (e) {
        console.warn('[luna] data brief unavailable', e)
      }
    }
    load()
    const t = setInterval(load, 90_000)
    return () => clearInterval(t)
  }, [])

  const lead = brief?.news[0]?.title ?? 'Waiting for live feed data.'
  const movers = brief?.stocks.slice(0, 3).map(s => `${s.symbol} ${s.pct >= 0 ? '+' : ''}${s.pct.toFixed(2)}%`).join('  /  ') || 'Market data loading.'
  const weather = brief?.weather ? `${brief.weather.city}: ${brief.weather.temp_f}F, ${brief.weather.condition}` : 'Weather loading.'

  return (
    <div style={{ padding: '8px 12px', display: 'grid', gap: 5, height: '100%', alignContent: 'center' }}>
      <div style={{ fontFamily: 'monospace', fontSize: 9, color: P.accent, letterSpacing: '0.18em' }}>VISUALIZING</div>
      <div style={{ fontFamily: 'monospace', fontSize: 10, color: P.text, lineHeight: 1.35 }}>{weather}</div>
      <div style={{ fontFamily: 'monospace', fontSize: 9, color: P.textDim, lineHeight: 1.35 }}>{movers}</div>
      <div style={{ fontSize: 10, color: 'rgba(226,232,240,0.68)', lineHeight: 1.35, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{lead}</div>
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import ReactGridLayout, { getCompactor } from 'react-grid-layout'
import type { LayoutItem } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import './gridOverrides.css'

const freeCompactor = getCompactor(null, true) // no compaction, free overlap (Windows-like)

import { P } from '../palette'
import { HUDPanel, GridPanel } from '../shared/HUDPanel'
import { ExpandedOverlay } from '../shared/ExpandedOverlay'
import { Corners } from '../shared/Corners'
import { NewsList } from '../widgets/NewsWidget'
import { YoutubeIframe } from '../widgets/YoutubeWidget'
import { StocksList } from '../widgets/StocksWidget'
import { WeatherWidget } from '../widgets/WeatherWidget'
import { OrbCluster } from '../widgets/OrbWidget'
import { LunaMessages, LunaDataBrief } from '../widgets/ConsoleWidget'
import { COLS, ROWS, DEFAULT_LAYOUT, loadLayout, saveLayout } from './gridConfig'

const EXPANDED_TITLES: Record<string, string> = {
  youtube: 'DW NEWS LIVE',
  market:  'MARKET',
  news:    'NEWS FEED',
  weather: 'WEATHER',
}

function ExpandedContent({ id }: { id: string }) {
  if (id === 'youtube') return <YoutubeIframe muted={false} />
  if (id === 'market')  return <StocksList large />
  if (id === 'news')    return <NewsList />
  if (id === 'weather') return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}><WeatherWidget /></div>
  return null
}

export function DefaultLayout({
  expanded, setExpanded,
}: {
  expanded: string | null
  setExpanded: (id: string | null) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const rglWrapperRef = useRef<HTMLDivElement>(null)
  const [rowHeight, setRowHeight] = useState(60)
  const [width, setWidth] = useState(1280)
  const [layout, setLayout] = useState<LayoutItem[]>(loadLayout)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      const { width: w, height: h } = entry.contentRect
      setWidth(w)
      setRowHeight(Math.max(20, (h - (ROWS - 1) * 8 - 16) / ROWS))
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Single handler on the grid wrapper — walks e.target up to the RGL item
  // wrapper (direct child of the grid container) and lifts its z-index.
  // Fires for any click anywhere inside any widget, including canvases and iframes.
  const handleGridMouseDown = useCallback((e: React.MouseEvent) => {
    const grid = rglWrapperRef.current?.firstElementChild as HTMLElement | null
    if (!grid) return
    let el: HTMLElement | null = e.target as HTMLElement
    while (el && el.parentElement !== grid) {
      el = el.parentElement as HTMLElement | null
    }
    if (!el) return
    Array.from(grid.children).forEach(child => {
      (child as HTMLElement).style.zIndex = '2'
    })
    el.style.zIndex = '10'
  }, [])

  // Keep React state in sync during drag (required for controlled mode)
  const onLayoutChange = (l: readonly LayoutItem[]) => {
    setLayout([...l] as LayoutItem[])
  }

  // Only persist the final position/size — not intermediate drag frames
  const onDragStop = (l: readonly LayoutItem[]) => {
    const mutable = [...l] as LayoutItem[]
    setLayout(mutable)
    saveLayout(mutable)
  }

  const onResizeStop = (l: readonly LayoutItem[]) => {
    const mutable = [...l] as LayoutItem[]
    setLayout(mutable)
    saveLayout(mutable)
  }

  return (
    <div ref={containerRef} style={{ flex: 1, overflow: 'hidden', position: 'relative', WebkitAppRegion: 'no-drag' } as React.CSSProperties}>

      {/* Orb — fixed center, not part of the grid */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 1, pointerEvents: 'auto',
      }}>
        <div style={{ transform: 'scale(1.06)', transformOrigin: 'center center' }}>
          <OrbCluster />
        </div>
      </div>

      <div ref={rglWrapperRef} onMouseDown={handleGridMouseDown} style={{ position: 'relative', zIndex: 2 }}>
        <ReactGridLayout
          layout={layout}
          width={width}
          gridConfig={{ cols: COLS, rowHeight, margin: [8, 8], containerPadding: [8, 8], maxRows: ROWS }}
          dragConfig={{ handle: '.luna-drag-handle', bounded: true }}
          resizeConfig={{ handles: ['se', 'sw', 'ne', 'nw'] }}
          compactor={freeCompactor}
          onLayoutChange={onLayoutChange}
          onDragStop={onDragStop}
          onResizeStop={onResizeStop}
        >
          <div key="news" style={{ overflow: 'hidden' }}>
            <HUDPanel id="news" title="NEWS FEED" expanded={expanded === 'news'} onExpand={setExpanded}>
              <NewsList limit={20} />
            </HUDPanel>
          </div>

          <div key="youtube" style={{ overflow: 'hidden' }}>
            <HUDPanel id="youtube" title="DW NEWS" expanded={expanded === 'youtube'} onExpand={setExpanded}>
              <YoutubeIframe muted={expanded === 'youtube'} />
            </HUDPanel>
          </div>

          <div key="weather" style={{ overflow: 'hidden' }}>
            <GridPanel title="WEATHER">
              <WeatherWidget />
            </GridPanel>
          </div>

          <div key="console" style={{ overflow: 'hidden' }}>
            <div style={{ border: `1px solid ${P.border}`, background: P.bg, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative', height: '100%' }}>
              <Corners />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', height: '100%' }}>
                <div style={{ minWidth: 0, borderRight: `1px solid ${P.border}` }}>
                  <div className="luna-drag-handle" style={{ padding: '4px 8px', borderBottom: `1px solid ${P.border}`, fontFamily: 'monospace', fontSize: 8, letterSpacing: '0.25em', color: P.textDim, cursor: 'grab', userSelect: 'none' }}>LUNA</div>
                  <div style={{ height: 'calc(100% - 22px)', overflow: 'hidden' }}>
                    <LunaMessages />
                  </div>
                </div>
                <div style={{ minWidth: 0 }}>
                  <LunaDataBrief />
                </div>
              </div>
            </div>
          </div>

          <div key="market" style={{ overflow: 'hidden' }}>
            <HUDPanel id="market" title="MARKET" expanded={expanded === 'market'} onExpand={setExpanded}>
              <StocksList />
            </HUDPanel>
          </div>
        </ReactGridLayout>
      </div>

      <AnimatePresence>
        {expanded && (
          <ExpandedOverlay
            key={expanded}
            title={EXPANDED_TITLES[expanded] ?? expanded}
            onClose={() => setExpanded(null)}
          >
            <ExpandedContent id={expanded} />
          </ExpandedOverlay>
        )}
      </AnimatePresence>
    </div>
  )
}

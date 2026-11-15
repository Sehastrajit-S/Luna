import type { LayoutItem } from 'react-grid-layout'

export type { LayoutItem }

export const LAYOUT_KEY = 'luna-dashboard-layout-v3'
export const COLS = 12
export const ROWS = 10

// Orb is NOT a grid item — it's fixed-centered behind the widgets
export const DEFAULT_LAYOUT: LayoutItem[] = [
  { i: 'news',      x: 0, y: 0, w: 3, h: 5 },
  { i: 'youtube',   x: 0, y: 5, w: 3, h: 5 },
  { i: 'weather',   x: 3, y: 0, w: 6, h: 2 },
  { i: 'console',   x: 3, y: 8, w: 6, h: 2 },
  { i: 'market',    x: 9, y: 0, w: 3, h: 10 },
]

export function loadLayout(): LayoutItem[] {
  try {
    const raw = localStorage.getItem(LAYOUT_KEY)
    if (!raw) return DEFAULT_LAYOUT
    const saved: LayoutItem[] = JSON.parse(raw)
    const ids = new Set(saved.map(l => l.i))
    if (DEFAULT_LAYOUT.every(d => ids.has(d.i))) return saved
  } catch { /* ignore */ }
  return DEFAULT_LAYOUT
}

export function saveLayout(layout: readonly LayoutItem[]) {
  try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)) } catch { /* ignore */ }
}

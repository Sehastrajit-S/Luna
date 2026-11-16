import { useEffect, useRef, useState, useCallback } from 'react'
import { getApiBase } from '../../api/client'

// ── Constants ──────────────────────────────────────────────────────────────────

const COLORS: Record<string, string> = {
  personal:     '#8b5cf6',
  preference:   '#3b82f6',
  relationship: '#ec4899',
  event:        '#f59e0b',
  goal:         '#10b981',
  health:       '#ef4444',
  default:      '#6b7280',
}

const CHARS = 'アイウエオカキクケコサシスセソ01234ABCDEF'
const GOLDEN_RATIO = (1 + Math.sqrt(5)) / 2

// Brain scale in 3D space (pixels)
const BRX = 205, BRY = 185, BRZ = 165

// 3D region centers per category (normalized, will be scaled by brain dims)
const REGIONS_3D: Record<string, [number, number, number]> = {
  personal:     [-0.50,  0.40,  0.15],
  goal:         [ 0.50,  0.40,  0.15],
  preference:   [-0.55,  0.00, -0.05],
  relationship: [ 0.55,  0.00, -0.05],
  event:        [ 0.00,  0.62,  0.00],
  health:       [ 0.00, -0.52,  0.00],
  default:      [ 0.00,  0.00,  0.00],
}

// ── Types ──────────────────────────────────────────────────────────────────────

interface GNode {
  id: number; content: string; category: string
  importance: number; confidence: number
  x: number; y: number; z: number
  vx: number; vy: number; vz: number
  radius: number; color: string; phase: number
}

interface GEdge { source: number; target: number }
interface BPt   { x: number; y: number; z: number; a: number; rgb: [number, number, number] }
interface RDrop { x: number; y: number; speed: number; chars: string[]; len: number; op: number }

// ── 3D helpers ─────────────────────────────────────────────────────────────────

function rotY(x: number, y: number, z: number, a: number) {
  const c = Math.cos(a), s = Math.sin(a)
  return { x: x * c + z * s, y, z: -x * s + z * c }
}

function project(x: number, y: number, z: number, cx: number, cy: number, fov: number) {
  const d = fov / (fov + z)
  return { px: cx + x * d, py: cy - y * d, d }
}

// ── Lobe segmentation ──────────────────────────────────────────────────────────
// bx=left/right  by=up/down (+1=top)  bz=front/back (+1=front)
// Boundaries approximate real sulcal landmarks on the unit sphere.
const LOBES: Array<{ name: string; rgb: [number, number, number]; test: (bx: number, by: number, bz: number) => boolean }> = [
  // Brainstem — narrow bottom column
  { name: 'brainstem', rgb: [210, 120,  55],
    test: (bx, by)     => by < -0.68 && Math.abs(bx) < 0.38 },
  // Cerebellum — inferior posterior
  { name: 'cerebellum', rgb: [160,  80, 220],
    test: (bx, by, bz) => by < -0.32 && bz < 0.08 },
  // Temporal — lateral sides, below lateral sulcus
  { name: 'temporal',   rgb: [ 60, 200, 110],
    test: (bx, by, bz) => Math.abs(bx) > 0.52 && by < 0.30 && bz > -0.55 },
  // Occipital — posterior pole
  { name: 'occipital',  rgb: [240,  80,  80],
    test: (_bx, by, bz) => bz < -0.35 && by > -0.32 },
  // Frontal — anterior, above lateral sulcus
  { name: 'frontal',    rgb: [ 80, 150, 240],
    test: (_bx, by, bz) => bz > -0.08 && by > -0.18 },
  // Parietal — superior posterior (default upper region)
  { name: 'parietal',   rgb: [245, 185,  40],
    test: () => true },
]

function getLobeRgb(bx: number, by: number, bz: number): [number, number, number] {
  for (const lobe of LOBES) if (lobe.test(bx, by, bz)) return lobe.rgb
  return [180, 140, 255]
}

// ── Brain surface point cloud (generated once) ─────────────────────────────────
// Uses Fibonacci lattice for uniform distribution, then deforms for brain shape.

function buildBrainCloud(n: number): BPt[] {
  const pts: BPt[] = []
  for (let i = 0; i < n; i++) {
    const theta = Math.acos(1 - 2 * (i + 0.5) / n)
    const phi   = 2 * Math.PI * i / GOLDEN_RATIO

    // Unit sphere — bx=left/right  by=up/down  bz=front/back
    const bx = Math.sin(theta) * Math.cos(phi)
    const by = Math.cos(theta)
    const bz = Math.sin(theta) * Math.sin(phi)

    // ── Gyri/sulci — article formula: sin(12φ)·cos(12θ) ───────────────────
    // Creates a uniform grid of ridges across the whole surface (like real cortex)
    const primary   = 0.08 * Math.sin(12 * phi) * Math.cos(12 * theta)
    const secondary = 0.04 * Math.sin( 8 * phi + 0.9) * Math.cos( 9 * theta + 1.1)
    const tertiary  = 0.02 * Math.cos(16 * phi) * Math.sin( 7 * theta + 0.5)
    const gyri = primary + secondary + tertiary

    // ── Macrostructure ─────────────────────────────────────────────────────

    // Hemisphere widen — each lobe bulges strongly outward
    const hemiWiden = 0.42 * bx * bx

    // Two-bump crown — left and right crown peaks, separated at center
    const crownBump = 0.30 * bx * bx * Math.max(0, by) * (1.6 - Math.abs(by) * 0.8)

    // Interhemispheric fissure — sharp midline groove in upper brain
    const fissure = -0.52 * Math.exp(-28 * bx * bx) * Math.max(0, by) * Math.max(0, by)

    // Temporal lobes — downward bulge on each side at mid-height
    const temporal = 0.20 * bx * bx
      * Math.max(0, -(by - 0.05))
      * Math.max(0, 0.75 - Math.abs(by + 0.18))

    // Frontal lobe — slight forward protrusion at upper-front (bz > 0 = front)
    const frontal   = 0.10 * Math.max(0,  bz) * Math.max(0, by)

    // Occipital lobe — rounder/more prominent at back (bz < 0 = back)
    const occipital = 0.10 * Math.max(0, -bz) * Math.max(0, by + 0.4)

    // Brainstem taper — narrow at bottom
    const taper = by < -0.50 ? (by + 0.50) * 0.28 : 0

    const r = 1.0 + hemiWiden + crownBump + fissure + temporal + frontal + occipital + taper + gyri

    // Ridge brightness — peaks lit, valleys dim
    const ridge      = Math.max(0, primary + secondary)
    const brightness = 0.14 + ridge * 4.2 + hemiWiden * 0.10

    pts.push({
      x:   bx * r * BRX,
      y:   by * r * BRY,
      z:   bz * r * BRZ,
      a:   Math.min(0.96, brightness),
      rgb: getLobeRgb(bx, by, bz),
    })
  }
  return pts
}

// ── Component ──────────────────────────────────────────────────────────────────

export function BrainMemoryCanvas() {
  const canvasRef    = useRef<HTMLCanvasElement>(null)
  const tooltipRef   = useRef<HTMLDivElement>(null)
  const nodesRef     = useRef<GNode[]>([])
  const edgesRef     = useRef<GEdge[]>([])
  const brainPtsRef  = useRef<BPt[]>([])
  const rainRef      = useRef<RDrop[]>([])
  const hoveredRef   = useRef<GNode | null>(null)
  const angleRef     = useRef(0)
  const dragRef      = useRef<{ startX: number; startAngle: number } | null>(null)
  const frameRef     = useRef(0)
  const tickRef      = useRef(0)
  const [tooltipNode, setTooltipNode] = useState<GNode | null>(null)
  const [isDragging,  setIsDragging]  = useState(false)

  const makeRain = useCallback((w: number, h: number) => {
    rainRef.current = Array.from({ length: Math.floor(w / 28) }, (_, i) => ({
      x:     i * 28,
      y:     Math.random() * -h,
      speed: 0.4 + Math.random() * 1.3,
      len:   Math.floor(3 + Math.random() * 8),
      op:    0.04 + Math.random() * 0.09,
      chars: Array.from({ length: 12 }, () => CHARS[Math.floor(Math.random() * CHARS.length)]),
    }))
  }, [])

  const simulate = useCallback(() => {
    const nodes = nodesRef.current
    if (!nodes.length) return

    // Repulsion (3D)
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j]
        const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z
        const d2 = Math.max(dx*dx + dy*dy + dz*dz, 1)
        const d  = Math.sqrt(d2)
        const f  = 700 / d2
        a.vx -= f*dx/d; a.vy -= f*dy/d; a.vz -= f*dz/d
        b.vx += f*dx/d; b.vy += f*dy/d; b.vz += f*dz/d
      }
    }

    // Edge springs (keep related nodes close)
    const map = new Map(nodes.map(n => [n.id, n]))
    for (const e of edgesRef.current) {
      const a = map.get(e.source), b = map.get(e.target)
      if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z
      const d  = Math.sqrt(dx*dx + dy*dy + dz*dz) || 1
      const f  = (d - 48) * 0.11
      a.vx += f*dx/d; a.vy += f*dy/d; a.vz += f*dz/d
      b.vx -= f*dx/d; b.vy -= f*dy/d; b.vz -= f*dz/d
    }

    // Region attraction (shapes the lobe layout)
    for (const n of nodes) {
      const [rx, ry, rz] = REGIONS_3D[n.category] ?? REGIONS_3D.default
      n.vx += (rx * BRX * 0.68 - n.x) * 0.008
      n.vy += (ry * BRY * 0.68 - n.y) * 0.008
      n.vz += (rz * BRZ * 0.68 - n.z) * 0.008
    }

    // Integrate + damp + ellipsoidal clamp
    for (const n of nodes) {
      n.vx *= 0.84; n.vy *= 0.84; n.vz *= 0.84
      n.x  += n.vx;  n.y  += n.vy;  n.z  += n.vz
      const ex = n.x / (BRX * 0.84)
      const ey = n.y / (BRY * 0.84)
      const ez = n.z / (BRZ * 0.70)
      const ed = ex*ex + ey*ey + ez*ez
      if (ed > 1) {
        const s = 1 / Math.sqrt(ed)
        n.x *= s; n.y *= s; n.z *= s
        n.vx *= 0.1; n.vy *= 0.1; n.vz *= 0.1
      }
    }
  }, [])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const W = canvas.width, H = canvas.height
    const tick = ++tickRef.current

    // Background
    ctx.fillStyle = 'rgba(9, 9, 15, 0.94)'
    ctx.fillRect(0, 0, W, H)

    // Matrix rain
    ctx.font = '11px "JetBrains Mono", monospace'
    for (const d of rainRef.current) {
      d.y += d.speed
      if (d.y > H + d.len * 16) {
        d.y = -d.len * 16
        d.chars = Array.from({ length: 12 }, () => CHARS[Math.floor(Math.random() * CHARS.length)])
      }
      if (Math.random() < 0.02)
        d.chars[Math.floor(Math.random() * d.chars.length)] = CHARS[Math.floor(Math.random() * CHARS.length)]
      for (let i = 0; i < d.len; i++) {
        const cy2 = d.y - i * 16
        if (cy2 < 0 || cy2 > H) continue
        const a = i === 0 ? d.op : d.op * (1 - i / d.len) * 0.4
        ctx.fillStyle = i === 0 ? `rgba(200, 178, 255, ${a})` : `rgba(120, 70, 230, ${a})`
        ctx.fillText(d.chars[i % d.chars.length], d.x, cy2)
      }
    }

    // Auto-rotate when not dragging
    if (!dragRef.current) angleRef.current += 0.003
    const angle = angleRef.current
    const cx = W / 2, cy = H / 2
    const FOV = 580

    // Physics settle
    if (tick < 700 || nodesRef.current.some(n => Math.abs(n.vx) + Math.abs(n.vy) + Math.abs(n.vz) > 0.04))
      simulate()

    // ── Brain point cloud ──────────────────────────────────────────────────────
    type ProjPt = { px: number; py: number; z: number; d: number; a: number; rgb: [number,number,number] }
    const bProj: ProjPt[] = brainPtsRef.current.map(p => {
      const rot = rotY(p.x, p.y, p.z, angle)
      const { px, py, d } = project(rot.x, rot.y, rot.z, cx, cy, FOV)
      return { px, py, z: rot.z, d, a: p.a, rgb: p.rgb }
    })
    bProj.sort((a, b) => a.z - b.z)

    // Draw brain surface — lobe colors, ridge-brightened toward white
    for (const p of bProj) {
      const size  = Math.max(0.8, 2.4 * p.d)
      const alpha = Math.min(0.93, p.a * p.d * 1.15)
      // Blend lobe color toward white on gyri ridges
      const lit   = Math.min(1, p.a * 1.6)
      const cr    = Math.round(p.rgb[0] + (255 - p.rgb[0]) * lit * 0.45)
      const cg    = Math.round(p.rgb[1] + (255 - p.rgb[1]) * lit * 0.45)
      const cb    = Math.round(p.rgb[2] + (255 - p.rgb[2]) * lit * 0.45)
      ctx.beginPath()
      ctx.arc(p.px, p.py, size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${cr},${cg},${cb},${alpha.toFixed(2)})`
      ctx.fill()
    }

    // ── Memory nodes – project ─────────────────────────────────────────────────
    const nodes = nodesRef.current
    const edges = edgesRef.current
    const nMap  = new Map(nodes.map(n => [n.id, n]))

    type ProjNode = { n: GNode; px: number; py: number; z: number; d: number; r: number }
    const nProj: ProjNode[] = nodes.map(n => {
      const rot = rotY(n.x, n.y, n.z, angle)
      const { px, py, d } = project(rot.x, rot.y, rot.z, cx, cy, FOV)
      n.phase = (n.phase + 0.018) % (Math.PI * 2)
      return { n, px, py, z: rot.z, d, r: n.radius * (1 + Math.sin(n.phase) * 0.12) }
    })

    // ── Edges ──────────────────────────────────────────────────────────────────
    const tEdge = (tick % 150) / 150
    for (const e of edges) {
      const a = nMap.get(e.source), b = nMap.get(e.target)
      if (!a || !b) continue
      const rA = rotY(a.x, a.y, a.z, angle), rB = rotY(b.x, b.y, b.z, angle)
      const pA = project(rA.x, rA.y, rA.z, cx, cy, FOV)
      const pB = project(rB.x, rB.y, rB.z, cx, cy, FOV)

      const grad = ctx.createLinearGradient(pA.px, pA.py, pB.px, pB.py)
      grad.addColorStop(0, `${a.color}cc`)
      grad.addColorStop(1, `${b.color}cc`)
      ctx.beginPath()
      ctx.moveTo(pA.px, pA.py)
      ctx.lineTo(pB.px, pB.py)
      ctx.strokeStyle = grad
      ctx.lineWidth   = 1.5
      ctx.stroke()

      // Traveling spark
      const phase = (tEdge + (a.id * 0.137) % 1) % 1
      ctx.beginPath()
      ctx.arc(pA.px + (pB.px - pA.px) * phase, pA.py + (pB.py - pA.py) * phase, 2.5, 0, Math.PI * 2)
      ctx.fillStyle = `${a.color}ff`
      ctx.fill()
    }

    // ── Nodes (back-to-front) ──────────────────────────────────────────────────
    nProj.sort((a, b) => a.z - b.z)

    for (const p of nProj) {
      const hov  = p.n === hoveredRef.current
      const size = Math.max(2, p.r * p.d)

      // Glow halo
      const grd = ctx.createRadialGradient(p.px, p.py, 0, p.px, p.py, size * 4)
      grd.addColorStop(0, `${p.n.color}55`)
      grd.addColorStop(1, `${p.n.color}00`)
      ctx.beginPath()
      ctx.arc(p.px, p.py, size * 4, 0, Math.PI * 2)
      ctx.fillStyle = grd
      ctx.fill()

      // Core sphere
      ctx.beginPath()
      ctx.arc(p.px, p.py, size, 0, Math.PI * 2)
      ctx.fillStyle = hov ? p.n.color : `${p.n.color}cc`
      ctx.fill()

      if (hov) {
        ctx.strokeStyle = `${p.n.color}ee`
        ctx.lineWidth   = 2
        ctx.stroke()
      }
    }

    // ── Tooltip position tracking (direct DOM – no re-render per frame) ────────
    const tt = tooltipRef.current
    if (tt) {
      const hov = hoveredRef.current
      if (hov) {
        const rot = rotY(hov.x, hov.y, hov.z, angle)
        const { px, py } = project(rot.x, rot.y, rot.z, cx, cy, FOV)
        tt.style.left    = `${px > W * 0.6 ? px - 260 : px + 16}px`
        tt.style.top     = `${Math.max(8, py - 24)}px`
        tt.style.opacity = '1'
      } else {
        tt.style.opacity = '0'
      }
    }

    frameRef.current = requestAnimationFrame(draw)
  }, [simulate])

  // Generate brain cloud + load graph data
  useEffect(() => {
    brainPtsRef.current = buildBrainCloud(8000)

    fetch(`${getApiBase()}/api/memory/graph`)
      .then(r => r.json())
      .then(data => {
        nodesRef.current = (data.nodes ?? []).slice(0, 80).map((n: any) => {
          const [rx, ry, rz] = REGIONS_3D[n.category] ?? REGIONS_3D.default
          return {
            ...n,
            x:  rx * BRX * 0.60 + (Math.random() - 0.5) * BRX * 0.25,
            y:  ry * BRY * 0.60 + (Math.random() - 0.5) * BRY * 0.25,
            z:  rz * BRZ * 0.60 + (Math.random() - 0.5) * BRZ * 0.25,
            vx: 0, vy: 0, vz: 0,
            radius: 4 + (n.importance ?? 0.5) * 7,
            color:  COLORS[n.category] ?? COLORS.default,
            phase:  Math.random() * Math.PI * 2,
          }
        })
        edgesRef.current = (data.edges ?? []).map((e: any) => ({ source: e.source, target: e.target }))
      })
      .catch(() => {})
  }, [])

  // Canvas setup + animation loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const resize = () => {
      canvas.width  = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
      makeRain(canvas.width, canvas.height)
    }
    resize()
    window.addEventListener('resize', resize)
    frameRef.current = requestAnimationFrame(draw)
    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(frameRef.current)
    }
  }, [draw, makeRain])

  // Drag-to-rotate
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragRef.current = { startX: e.clientX, startAngle: angleRef.current }
    setIsDragging(true)
  }, [])

  const onMouseUp = useCallback(() => {
    dragRef.current = null
    setIsDragging(false)
  }, [])

  // Hover + drag
  const onMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (dragRef.current) {
      const dx = e.clientX - dragRef.current.startX
      angleRef.current = dragRef.current.startAngle + dx * 0.007
      return
    }
    const canvas = canvasRef.current
    if (!canvas) return
    const rect  = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left, my = e.clientY - rect.top
    const angle = angleRef.current
    const cx = canvas.width / 2, cy = canvas.height / 2, FOV = 580

    let hit: GNode | null = null
    let best = Infinity
    for (const n of nodesRef.current) {
      const rot = rotY(n.x, n.y, n.z, angle)
      const { px, py } = project(rot.x, rot.y, rot.z, cx, cy, FOV)
      const d = Math.hypot(px - mx, py - my)
      if (d < n.radius * 4 && d < best) { hit = n; best = d }
    }

    if (hit !== hoveredRef.current) {
      hoveredRef.current = hit
      setTooltipNode(hit)
    }
  }, [])

  const onLeave = useCallback(() => {
    dragRef.current    = null
    hoveredRef.current = null
    setIsDragging(false)
    setTooltipNode(null)
  }, [])

  return (
    <div className="relative w-full h-full overflow-hidden rounded-b-2xl select-none">
      <canvas
        ref={canvasRef}
        className="w-full h-full block"
        onMouseMove={onMouseMove}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        onMouseLeave={onLeave}
        style={{ cursor: isDragging ? 'grabbing' : tooltipNode ? 'crosshair' : 'grab' }}
      />

      <div className="absolute bottom-3 right-3 text-[10px] text-luna-dim font-mono opacity-40 pointer-events-none">
        drag to rotate
      </div>

      {/* Tooltip – position updated directly by draw loop, content by React */}
      <div
        ref={tooltipRef}
        className="absolute z-20 pointer-events-none transition-opacity duration-100"
        style={{ opacity: 0, top: 0, left: 0 }}
      >
        {tooltipNode && (
          <div className="bg-luna-bg/95 border border-luna-border rounded-xl px-3 py-2.5 w-56 shadow-2xl backdrop-blur-sm">
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: tooltipNode.color }}>
              {tooltipNode.category}
            </span>
            <p className="text-xs text-luna-text mt-1 leading-snug">{tooltipNode.content}</p>
            <div className="flex gap-3 mt-1.5">
              <span className="text-[10px] text-luna-dim">{Math.round(tooltipNode.confidence * 100)}% conf</span>
              <span className="text-[10px] text-luna-dim">{Math.round(tooltipNode.importance * 100)}% imp</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

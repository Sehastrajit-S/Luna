import { useEffect, useRef } from 'react'
import * as THREE from 'three'

const HOLO_FILL  = 0x00ccff   // translucent fill
const HOLO_WIRE  = 0x00ffff   // wireframe / edges
const HOLO_GLOW  = 0x004488   // ambient / star colour
const HOLO_SCAN  = 0x44ffff   // scanning plane

interface ShapeSpec {
  type: 'cylinder' | 'sphere' | 'box' | 'torus' | 'cone'
  pos: [number, number, number]
  label: string
  r?: number
  h?: number
  w?: number
  d?: number
  tube?: number
  rot?: [number, number, number]
}

export interface SceneSpec {
  shapes: ShapeSpec[]
  animate?: string
}

function makeGeometry(s: ShapeSpec): THREE.BufferGeometry {
  switch (s.type) {
    case 'cylinder': return new THREE.CylinderGeometry(s.r ?? 0.3, s.r ?? 0.3, s.h ?? 1, 48, 1)
    case 'sphere':   return new THREE.SphereGeometry(s.r ?? 0.4, 48, 48)
    case 'box':      return new THREE.BoxGeometry(s.w ?? 1, s.h ?? 1, s.d ?? 1)
    case 'torus':    return new THREE.TorusGeometry(s.r ?? 1, s.tube ?? 0.12, 24, 80)
    case 'cone':     return new THREE.ConeGeometry(s.r ?? 0.3, s.h ?? 1, 32)
    default:         return new THREE.SphereGeometry(0.3, 24, 24)
  }
}

export function GeneratedScene({ spec }: { spec: SceneSpec }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !spec?.shapes?.length) return

    const w = canvas.offsetWidth  || 340
    const h = canvas.offsetHeight || 300

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    renderer.setSize(w, h, false)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.4

    const scene  = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 200)
    camera.position.set(5, 3, 7)
    camera.lookAt(0, 0, 0)

    // ── Lighting ─────────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(HOLO_GLOW, 3))
    const pLight = new THREE.PointLight(HOLO_WIRE, 4, 30)
    pLight.position.set(3, 5, 4)
    scene.add(pLight)
    const pLight2 = new THREE.PointLight(0x003366, 2, 25)
    pLight2.position.set(-4, -2, -3)
    scene.add(pLight2)

    // ── Star field ───────────────────────────────────────────────────────────
    const starPos = new Float32Array(2400)
    for (let i = 0; i < 2400; i++) starPos[i] = (Math.random() - 0.5) * 120
    const starGeo = new THREE.BufferGeometry()
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3))
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x113355, size: 0.08 })))

    // ── Build holographic model from spec ────────────────────────────────────
    const group = new THREE.Group()

    // Shared materials (cloned per shape so opacity can vary slightly)
    const baseFillMat = new THREE.MeshBasicMaterial({
      color: HOLO_FILL,
      transparent: true,
      opacity: 0.10,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    const baseWireMat = new THREE.MeshBasicMaterial({
      color: HOLO_WIRE,
      wireframe: true,
      transparent: true,
      opacity: 0.55,
    })
    const edgeMat = new THREE.LineBasicMaterial({
      color: HOLO_WIRE,
      transparent: true,
      opacity: 0.85,
    })

    spec.shapes.forEach(s => {
      const geo  = makeGeometry(s)
      const fill = new THREE.Mesh(geo, baseFillMat.clone())
      const wire = new THREE.Mesh(geo, baseWireMat.clone())
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geo), edgeMat.clone())

      const obj = new THREE.Group()
      obj.add(fill, wire, edge)
      obj.position.set(...s.pos)

      if (s.rot) {
        obj.rotation.x = (s.rot[0] ?? 0) * Math.PI / 180
        obj.rotation.y = (s.rot[1] ?? 0) * Math.PI / 180
        obj.rotation.z = (s.rot[2] ?? 0) * Math.PI / 180
      }
      group.add(obj)
    })

    // ── Bounding box helper — fits camera to model ───────────────────────────
    const bbox = new THREE.Box3().setFromObject(group)
    const size = bbox.getSize(new THREE.Vector3())
    const center = bbox.getCenter(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    const dist = maxDim * 1.8
    camera.position.set(center.x + dist * 0.7, center.y + dist * 0.5, center.z + dist)
    camera.lookAt(center)

    // ── Scanning plane ───────────────────────────────────────────────────────
    const scanGeo  = new THREE.PlaneGeometry(maxDim * 3, 0.04)
    const scanMat  = new THREE.MeshBasicMaterial({ color: HOLO_SCAN, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false })
    const scanPlane = new THREE.Mesh(scanGeo, scanMat)
    scanPlane.rotation.x = Math.PI / 2
    group.add(scanPlane)

    // ── Grid floor ───────────────────────────────────────────────────────────
    const grid = new THREE.GridHelper(maxDim * 4, 20, 0x003355, 0x001122)
    grid.position.y = bbox.min.y - 0.05
    ;(grid.material as THREE.Material).transparent = true
    ;(grid.material as THREE.Material).opacity = 0.3
    scene.add(grid)

    scene.add(group)

    // ── Animation ────────────────────────────────────────────────────────────
    let t = 0, raf = 0
    let scanY  = bbox.min.y
    let scanDir = 1

    const animate = () => {
      raf = requestAnimationFrame(animate)
      t += 0.008

      // Slow turntable
      group.rotation.y = t * 0.22

      // Scan line sweep
      scanY += 0.018 * scanDir
      if (scanY > bbox.max.y + 0.3) scanDir = -1
      if (scanY < bbox.min.y - 0.3) scanDir =  1
      scanPlane.position.y = scanY
      scanMat.opacity = 0.15 + Math.sin(t * 4) * 0.1

      // Pulse fill opacity
      group.children.forEach((child, ci) => {
        if (!(child instanceof THREE.Group)) return
        child.children.forEach(m => {
          if (m instanceof THREE.Mesh) {
            const mat = m.material as THREE.MeshBasicMaterial
            if (!mat.wireframe && mat.side === THREE.DoubleSide) {
              mat.opacity = 0.07 + Math.sin(t * 1.5 + ci * 0.7) * 0.04
            }
          }
        })
      })

      // Pulse light
      pLight.intensity = 3.5 + Math.sin(t * 2.2) * 0.8

      renderer.render(scene, camera)
    }
    animate()

    return () => { cancelAnimationFrame(raf); renderer.dispose() }
  }, [spec])

  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
}

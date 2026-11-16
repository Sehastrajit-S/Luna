import { useEffect, useRef } from 'react'
import * as THREE from 'three'

// ── Scene classifier ───────────────────────────────────────────────────────────
export function resolveScene(title: string): string {
  const t = title.toLowerCase()
  if (/black.?hole|singularity|event.?horizon|hawking/.test(t))       return 'blackhole'
  if (/atom|electron|proton|neutron|nucleus|quantum|particle/.test(t)) return 'atom'
  if (/dna|helix|gene|chromosome|rna|protein/.test(t))                return 'dna'
  if (/solar.?system|planet|orbit|mars|jupiter|saturn/.test(t))       return 'solar'
  if (/earth|globe|world|continent/.test(t))                          return 'earth'
  if (/star|nebula|galaxy|cosmos|universe|supernova/.test(t))         return 'stars'
  if (/engine|v8|piston|cylinder|motor|turbine|gear|mechanical/.test(t))  return 'engine'
  if (/gun|cannon|pistol|rifle|firearm|bullet|weapon|projectile|ballistic|explosive/.test(t)) return 'engine'
  if (/machine|pump|compressor|hydraulic|valve|actuator/.test(t))          return 'engine'
  if (/molecule|chemical|compound|bond|reaction|chemistry/.test(t))        return 'molecule'
  if (/cell|mitochondria|virus|bacteria|biology/.test(t))                  return 'cell'
  if (/brain|neural|neuron|synapse|mind|cognition/.test(t))                return 'neural'
  // Universal fallback: node-graph (NOT orbiting spheres — avoids "solar system" confusion)
  return 'neural'
}

// ── Shared Three.js setup hook ─────────────────────────────────────────────────
function useThree(
  build: (scene: THREE.Scene, camera: THREE.PerspectiveCamera, renderer: THREE.WebGLRenderer) => () => void
) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const w = canvas.offsetWidth || 340
    const h = canvas.offsetHeight || 300
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    renderer.setSize(w, h, false)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000)
    const cleanup = build(scene, camera, renderer)
    return () => { cleanup(); renderer.dispose() }
  }, [])
  return ref
}

function addStars(scene: THREE.Scene, n = 1600, spread = 100) {
  const pos = new Float32Array(n * 3)
  for (let i = 0; i < n * 3; i++) pos[i] = (Math.random() - 0.5) * spread
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.1 })))
}

// ── Black Hole ─────────────────────────────────────────────────────────────────
function BlackHoleScene() {
  const ref = useThree((scene, camera, renderer) => {
    camera.position.set(0, 2.5, 7); camera.lookAt(0, 0, 0)
    addStars(scene)

    scene.add(new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 64),
      new THREE.MeshBasicMaterial({ color: 0x000000 })
    ))
    scene.add(new THREE.Mesh(
      new THREE.SphereGeometry(1.18, 64, 64),
      new THREE.MeshBasicMaterial({ color: 0x5500cc, transparent: true, opacity: 0.22, side: THREE.BackSide })
    ))
    const disk = new THREE.Mesh(
      new THREE.TorusGeometry(2.4, 0.28, 16, 128),
      new THREE.MeshBasicMaterial({ color: 0xff5500 })
    )
    disk.rotation.x = Math.PI / 5.5
    scene.add(disk)

    const inner = new THREE.Mesh(
      new THREE.TorusGeometry(1.45, 0.09, 8, 64),
      new THREE.MeshBasicMaterial({ color: 0xffaa33, transparent: true, opacity: 0.9 })
    )
    inner.rotation.x = Math.PI / 5.5
    scene.add(inner)

    const jetMat = new THREE.MeshBasicMaterial({ color: 0x3399ff, transparent: true, opacity: 0.55 })
    const makeJet = (y: number, flip: boolean) => {
      const j = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.14, 3.5, 8), jetMat)
      j.position.y = y
      if (flip) j.rotation.z = Math.PI
      return j
    }
    scene.add(makeJet(2.4, false))
    scene.add(makeJet(-2.4, true))

    let t = 0, raf = 0
    const animate = () => {
      raf = requestAnimationFrame(animate)
      t += 0.008
      disk.rotation.z = t * 0.4
      inner.rotation.z = t * 1.1
      camera.position.x = Math.sin(t * 0.12) * 2
      camera.position.z = 7 + Math.cos(t * 0.09) * 1.2
      camera.lookAt(0, 0, 0)
      renderer.render(scene, camera)
    }
    animate()
    return () => cancelAnimationFrame(raf)
  })
  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
}

// ── Atom ───────────────────────────────────────────────────────────────────────
function AtomScene() {
  const ref = useThree((scene, camera, renderer) => {
    camera.position.set(0, 0, 8); camera.lookAt(0, 0, 0)
    addStars(scene, 800, 60)

    scene.add(new THREE.Mesh(
      new THREE.SphereGeometry(0.6, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0xff4422 })
    ))

    const tilts = [0, Math.PI / 3, -Math.PI / 3]
    const electrons: { mesh: THREE.Mesh; speed: number; tilt: number }[] = []

    tilts.forEach((tilt, i) => {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(2.2, 0.02, 8, 64),
        new THREE.MeshBasicMaterial({ color: 0x2266ff, transparent: true, opacity: 0.4 })
      )
      ring.rotation.x = tilt; ring.rotation.y = tilt * 0.5
      scene.add(ring)
      const e = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16), new THREE.MeshBasicMaterial({ color: 0x44aaff }))
      scene.add(e)
      electrons.push({ mesh: e, speed: 0.6 + i * 0.3, tilt })
    })

    let t = 0, raf = 0
    const animate = () => {
      raf = requestAnimationFrame(animate)
      t += 0.012
      electrons.forEach(({ mesh, speed, tilt }, i) => {
        const a = t * speed + (i * Math.PI * 2) / 3
        mesh.position.set(Math.cos(a) * 2.2, Math.sin(a) * 2.2 * Math.sin(tilt), Math.sin(a) * 2.2 * Math.cos(tilt))
      })
      renderer.render(scene, camera)
    }
    animate()
    return () => cancelAnimationFrame(raf)
  })
  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
}

// ── DNA Helix ──────────────────────────────────────────────────────────────────
function DNAScene() {
  const ref = useThree((scene, camera, renderer) => {
    camera.position.set(0, 0, 10); camera.lookAt(0, 0, 0)
    addStars(scene, 600, 50)

    const group = new THREE.Group()
    const matA = new THREE.MeshBasicMaterial({ color: 0x3399ff })
    const matB = new THREE.MeshBasicMaterial({ color: 0xff4488 })
    const matR = new THREE.MeshBasicMaterial({ color: 0x66ffaa, transparent: true, opacity: 0.6 })

    for (let i = 0; i < 40; i++) {
      const t = (i / 40) * Math.PI * 4
      const y = (i / 40) * 8 - 4
      const r = 1.2
      const bA = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), matA)
      bA.position.set(Math.cos(t) * r, y, Math.sin(t) * r)
      group.add(bA)
      const bB = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), matB)
      bB.position.set(Math.cos(t + Math.PI) * r, y, Math.sin(t + Math.PI) * r)
      group.add(bB)
      if (i % 4 === 0) {
        const rung = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, r * 2, 6), matR)
        rung.position.set(0, y, 0); rung.rotation.z = Math.PI / 2; rung.rotation.y = t
        group.add(rung)
      }
    }
    scene.add(group)

    let raf = 0, rot = 0
    const animate = () => { raf = requestAnimationFrame(animate); rot += 0.006; group.rotation.y = rot; renderer.render(scene, camera) }
    animate()
    return () => cancelAnimationFrame(raf)
  })
  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
}

// ── V8 / Engine ────────────────────────────────────────────────────────────────
function EngineScene() {
  const ref = useThree((scene, camera, renderer) => {
    camera.position.set(0, 4, 10); camera.lookAt(0, 0, 0)
    scene.add(new THREE.AmbientLight(0x334455, 3))
    const dl = new THREE.DirectionalLight(0x88aaff, 2)
    dl.position.set(5, 8, 5); scene.add(dl)

    const cylMat  = new THREE.MeshStandardMaterial({ color: 0x778899, metalness: 0.8, roughness: 0.3 })
    const pistonMat = new THREE.MeshStandardMaterial({ color: 0xaabbcc, metalness: 0.9, roughness: 0.2 })

    // 8 cylinders in V arrangement
    const pistons: { mesh: THREE.Mesh; phase: number; x: number; side: number }[] = []
    for (let i = 0; i < 4; i++) {
      const xPos = (i - 1.5) * 1.6
      ;[-1, 1].forEach(side => {
        const cyl = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 1.8, 16), cylMat)
        cyl.position.set(xPos, side * 0.8, side * 0.6)
        cyl.rotation.z = side * Math.PI / 5
        scene.add(cyl)

        const piston = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 0.5, 16), pistonMat)
        scene.add(piston)
        pistons.push({ mesh: piston, phase: (i / 4) * Math.PI * 2 + (side > 0 ? Math.PI : 0), x: xPos, side })
      })
    }

    // Crankshaft
    const crankMat = new THREE.MeshStandardMaterial({ color: 0x556677, metalness: 1, roughness: 0.2 })
    const crank = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 7, 12), crankMat)
    crank.rotation.z = Math.PI / 2; crank.position.y = -1.5
    scene.add(crank)

    let t = 0, raf = 0
    const animate = () => {
      raf = requestAnimationFrame(animate)
      t += 0.025
      crank.rotation.y = t * 2
      pistons.forEach(({ mesh, phase, x, side }) => {
        const stroke = Math.sin(t * 2 + phase) * 0.6
        mesh.position.set(x, side * (0.8 + stroke * 0.3), side * (0.6 + stroke * 0.2))
        mesh.rotation.z = side * Math.PI / 5
      })
      renderer.render(scene, camera)
    }
    animate()
    return () => cancelAnimationFrame(raf)
  })
  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
}

// ── Neural Network ─────────────────────────────────────────────────────────────
function NeuralScene() {
  const ref = useThree((scene, camera, renderer) => {
    camera.position.set(0, 0, 8); camera.lookAt(0, 0, 0)
    addStars(scene, 600, 50)

    const nodeMat = new THREE.MeshBasicMaterial({ color: 0x44aaff })
    const lineMat = new THREE.LineBasicMaterial({ color: 0x2255aa, transparent: true, opacity: 0.5 })
    const nodes: THREE.Vector3[] = []
    const meshes: THREE.Mesh[] = []

    for (let i = 0; i < 30; i++) {
      const v = new THREE.Vector3((Math.random() - 0.5) * 7, (Math.random() - 0.5) * 5, (Math.random() - 0.5) * 3)
      nodes.push(v)
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), nodeMat)
      m.position.copy(v); scene.add(m); meshes.push(m)
    }
    nodes.forEach((a, i) => {
      nodes.forEach((b, j) => {
        if (j <= i) return
        if (a.distanceTo(b) < 3) {
          const geo = new THREE.BufferGeometry().setFromPoints([a, b])
          scene.add(new THREE.Line(geo, lineMat))
        }
      })
    })

    const group = new THREE.Group()
    ;[...meshes].forEach(m => { scene.remove(m); group.add(m) })
    scene.add(group)

    let t = 0, raf = 0
    const animate = () => {
      raf = requestAnimationFrame(animate)
      t += 0.007
      group.rotation.y = t * 0.4
      group.rotation.x = Math.sin(t * 0.2) * 0.15
      renderer.render(scene, camera)
    }
    animate()
    return () => cancelAnimationFrame(raf)
  })
  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
}

// ── Universal concept sphere (fallback for any topic) ──────────────────────────
function ConceptScene() {
  const ref = useThree((scene, camera, renderer) => {
    camera.position.set(0, 0, 7); camera.lookAt(0, 0, 0)
    addStars(scene, 1200, 80)

    // Central glowing sphere
    const core = new THREE.Mesh(
      new THREE.SphereGeometry(0.8, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0x3366ff, transparent: true, opacity: 0.85 })
    )
    scene.add(core)
    scene.add(new THREE.Mesh(
      new THREE.SphereGeometry(1.0, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0x2244cc, transparent: true, opacity: 0.15, side: THREE.BackSide })
    ))

    // Orbiting concept nodes
    const orbits: { mesh: THREE.Mesh; ring: THREE.Mesh; speed: number; r: number; tilt: number }[] = []
    const colors = [0x44aaff, 0xff6644, 0x44ffaa, 0xffaa44, 0xaa44ff]
    for (let i = 0; i < 5; i++) {
      const r = 2.0 + i * 0.3
      const tilt = (i / 5) * Math.PI
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(r, 0.015, 6, 64),
        new THREE.MeshBasicMaterial({ color: colors[i], transparent: true, opacity: 0.25 })
      )
      ring.rotation.x = tilt; ring.rotation.z = tilt * 0.4
      scene.add(ring)
      const node = new THREE.Mesh(
        new THREE.SphereGeometry(0.18, 12, 12),
        new THREE.MeshBasicMaterial({ color: colors[i] })
      )
      scene.add(node)
      orbits.push({ mesh: node, ring, speed: 0.3 + i * 0.15, r, tilt })
    }

    let t = 0, raf = 0
    const animate = () => {
      raf = requestAnimationFrame(animate)
      t += 0.01
      core.rotation.y = t * 0.3
      orbits.forEach(({ mesh, ring, speed, r, tilt }) => {
        const a = t * speed
        mesh.position.set(
          Math.cos(a) * r,
          Math.sin(a) * r * Math.sin(tilt),
          Math.sin(a) * r * Math.cos(tilt)
        )
        ring.rotation.z = t * 0.05
      })
      camera.position.x = Math.sin(t * 0.08) * 1.5
      camera.lookAt(0, 0, 0)
      renderer.render(scene, camera)
    }
    animate()
    return () => cancelAnimationFrame(raf)
  })
  return <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
}

// ── Scene picker ───────────────────────────────────────────────────────────────
export function ThreeDScene({ title }: { title: string }) {
  const scene = resolveScene(title)
  if (scene === 'blackhole') return <BlackHoleScene />
  if (scene === 'atom')      return <AtomScene />
  if (scene === 'dna')       return <DNAScene />
  if (scene === 'engine')    return <EngineScene />
  if (scene === 'neural')    return <NeuralScene />
  return <ConceptScene />   // universal fallback — works for V8, philosophy, history, etc.
}

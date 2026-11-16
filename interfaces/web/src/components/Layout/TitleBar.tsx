import { useEffect, useState } from 'react'
import { useStore } from '../../store'
import { VoiceOrb } from '../Voice/VoiceOrb'
import { Minus, Square, X, Maximize2, Minimize2, Settings, Mic, LayoutDashboard, Orbit } from 'lucide-react'

const MODE_META = {
  user:  { label: 'Voice',   Icon: Mic },
  dev:   { label: 'Classic', Icon: LayoutDashboard },
  luna:  { label: 'Luna',    Icon: Orbit },
}

export function ModeCycleButton() {
  const { viewMode, enterLunaDashboard, setViewMode } = useStore()

  const cycle = () => {
    if (viewMode === 'user') setViewMode('dev')       // voice → classic
    else if (viewMode === 'dev') enterLunaDashboard() // classic → luna
    else setViewMode('user')                          // luna → voice (completes the circle)
  }

  const { label, Icon } = MODE_META[viewMode as keyof typeof MODE_META] ?? MODE_META.user
  return (
    <button
      onMouseDown={(e) => e.stopPropagation()}
      onClick={cycle}
      title="Switch mode"
      className="flex items-center gap-1.5 px-2.5 h-6 rounded-full border text-[10px] font-medium transition-all select-none
        border-luna-border bg-luna-card text-luna-dim hover:border-luna-primary/50 hover:text-luna-text"
    >
      <Icon size={10} />
      <span>{label}</span>
    </button>
  )
}

function TrafficLights({ maximized, fullscreen }: { maximized: boolean; fullscreen: boolean }) {
  const stopDrag = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation()
  }

  return (
    <div className="flex items-center h-full" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.minimize()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
        title="Minimize"
      >
        <Minus size={14} strokeWidth={2} />
      </button>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.maximize()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
        title={maximized ? 'Restore' : 'Maximize'}
      >
        <Square size={12} strokeWidth={2} />
      </button>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.toggleFullscreen()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
        title={fullscreen ? 'Exit fullscreen (F11)' : 'Fullscreen (F11)'}
      >
        {fullscreen ? <Minimize2 size={13} strokeWidth={2} /> : <Maximize2 size={13} strokeWidth={2} />}
      </button>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.close()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-red-500/80 hover:text-white transition-colors"
        title="Close to tray"
      >
        <X size={15} strokeWidth={2} />
      </button>
    </div>
  )
}

export function TitleBar() {
  const [maximized, setMaximized]   = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const { viewMode, openSettings } = useStore()

  useEffect(() => {
    window.electronAPI?.isMaximized().then(setMaximized)
    window.electronAPI?.isFullscreen?.().then(setFullscreen)
    const cleanMax  = window.electronAPI?.onMaximizeChange(setMaximized)
    const cleanFull = window.electronAPI?.onFullscreenChange?.(setFullscreen)
    const onKey = (e: KeyboardEvent) => { if (e.key === 'F11') { e.preventDefault(); window.electronAPI?.toggleFullscreen() } }
    window.addEventListener('keydown', onKey)
    return () => { cleanMax?.(); cleanFull?.(); window.removeEventListener('keydown', onKey) }
  }, [])

  // ── User mode: bare strip — orb on left, traffic lights on right ──────────
  if (viewMode === 'user') {
    return (
      <div
        className="relative z-40 h-10 flex items-center justify-between bg-luna-surface border-b border-luna-border shrink-0 select-none"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      >
        <div
          className="flex items-center gap-3 px-4 h-full"
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <VoiceOrb size={28} onToggle={undefined} />
          <span className="text-[10px] font-mono tracking-[0.3em] text-luna-dim uppercase">
            Luna
          </span>
        </div>
        <div className="flex items-center gap-2 px-2 h-full" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
          <ModeCycleButton />
          <div className="w-px h-4 bg-luna-border" />
          <button
            onMouseDown={(event) => event.stopPropagation()}
            onClick={() => openSettings()}
            className="h-full w-10 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
            title="Settings"
          >
            <Settings size={14} strokeWidth={2} />
          </button>
          <div className="w-px h-4 bg-luna-border" />
          <TrafficLights maximized={maximized} fullscreen={fullscreen} />
        </div>
      </div>
    )
  }

  // ── Dev / Luna mode: full title bar ──────────────────────────────────────
  return (
    <div
      className="relative z-40 h-10 flex items-center justify-between bg-luna-surface border-b border-luna-border shrink-0 select-none"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      <span className="px-4 text-[10px] font-mono tracking-[0.3em] text-luna-dim uppercase">
        Luna
      </span>
      <div
        className="flex items-center gap-2 px-2 h-full"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        <ModeCycleButton />
        <div className="w-px h-4 bg-luna-border" />
        <VoiceOrb size={36} onToggle={undefined} />
        <div className="w-px h-4 bg-luna-border" />
        <button
          onMouseDown={(event) => event.stopPropagation()}
          onClick={() => openSettings()}
          className="h-full w-10 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
          title="Settings"
        >
          <Settings size={14} strokeWidth={2} />
        </button>
        <div className="w-px h-4 bg-luna-border" />
        <TrafficLights maximized={maximized} fullscreen={fullscreen} />
      </div>
    </div>
  )
}

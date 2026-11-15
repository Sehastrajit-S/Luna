import { useEffect, useRef, useState } from 'react'
import { SkipBack, SkipForward, Play, Pause } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { authHeaders } from '../../api/client'

interface Track {
  title: string
  artist: string
  album: string
  cover: string | null
  progress_ms: number
  duration_ms: number
  is_playing: boolean
}

function fmt(ms: number): string {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function SpotifyPlayer() {
  const BASE = window.electronAPI?.apiBase ?? ''
  const [connected, setConnected]   = useState(false)
  const [track, setTrack]           = useState<Track | null>(null)
  const [progress, setProgress]     = useState(0)
  const [coverLoaded, setCoverLoaded] = useState(false)
  const [coverError, setCoverError]   = useState(false)
  const pollRef                     = useRef<ReturnType<typeof setInterval> | null>(null)
  const tickRef                     = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStatus = async () => {
    try {
      const d = await fetch(`${BASE}/api/spotify/status`, { headers: authHeaders() }).then(r => r.json())
      setConnected(d.connected)
      if (d.current) {
        setTrack(prev => {
          if (prev?.cover !== d.current.cover) { setCoverLoaded(false); setCoverError(false) }
          return d.current
        })
        setProgress(d.current.progress_ms)
      } else setTrack(null)
    } catch {}
  }

  useEffect(() => {
    fetchStatus()
    pollRef.current = setInterval(fetchStatus, 3000)
    const cleanup = window.electronAPI?.onSpotifyConnected?.(() => fetchStatus())
    return () => { if (pollRef.current) clearInterval(pollRef.current); cleanup?.() }
  }, [])

  useEffect(() => {
    if (tickRef.current) clearInterval(tickRef.current)
    if (track?.is_playing) {
      tickRef.current = setInterval(() => {
        setProgress(p => Math.min(p + 1000, track.duration_ms))
      }, 1000)
    }
    return () => { if (tickRef.current) clearInterval(tickRef.current) }
  }, [track?.is_playing, track?.progress_ms])

  const action = async (endpoint: string, body?: object) => {
    try {
      const d = await fetch(`${BASE}/api/spotify/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: body ? JSON.stringify(body) : undefined,
      }).then(r => r.json())
      if (d.current) { setTrack(d.current); setProgress(d.current.progress_ms) }
      setTimeout(fetchStatus, 400)
    } catch {}
  }

  const authorize = async () => {
    try {
      const { url } = await fetch(`${BASE}/api/spotify/auth-url`, { headers: authHeaders() }).then(r => r.json())
      if (!url) return
      if (window.electronAPI?.spotifyOpenAuth) await window.electronAPI.spotifyOpenAuth(url)
      else window.open(url, '_blank')
    } catch {}
  }

  if (!connected) {
    return (
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        onClick={authorize}
        className="text-[11px] tracking-widest uppercase select-none transition-colors"
        style={{ color: 'rgba(100,116,139,0.45)', letterSpacing: '0.18em' }}
        onMouseEnter={e => (e.currentTarget.style.color = 'rgba(167,139,250,0.8)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.45)')}
      >
        connect spotify
      </motion.button>
    )
  }

  if (!track) {
    return (
      <div
        className="text-[11px] tracking-widest uppercase select-none"
        style={{ color: 'rgba(100,116,139,0.3)', letterSpacing: '0.18em' }}
      >
        nothing playing
      </div>
    )
  }

  const pct = track.duration_ms > 0 ? (progress / track.duration_ms) * 100 : 0

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 8 }}
        transition={{ duration: 0.3 }}
        className="flex items-center select-none"
        style={{ gap: 14, width: 300 }}
      >
        {/* ── Cover (left) ─────────────────────────────────── */}
        <div className="relative flex-shrink-0 rounded-lg overflow-hidden" style={{ width: 72, height: 72 }}>
          {/* Placeholder always underneath */}
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: 8 }}
          >
            <span style={{ fontSize: 24, opacity: 0.5 }}>♪</span>
          </div>
          {/* Image fades in once loaded */}
          {track.cover && !coverError && (
            <img
              src={track.cover}
              alt={track.album}
              className="absolute inset-0 w-full h-full object-cover rounded-lg shadow-lg transition-opacity duration-300"
              style={{ opacity: coverLoaded ? 1 : 0 }}
              onLoad={() => setCoverLoaded(true)}
              onError={() => setCoverError(true)}
            />
          )}
        </div>

        {/* ── Right side: title / controls / progress ───────── */}
        <div className="flex flex-col flex-1 min-w-0" style={{ gap: 6 }}>

          {/* Title + artist */}
          <div className="min-w-0">
            <p
              className="text-xs font-medium truncate leading-tight"
              style={{ color: 'rgba(255,255,255,0.9)' }}
              title={track.title}
            >
              {track.title}
            </p>
            <p
              className="text-[10px] truncate leading-tight"
              style={{ color: 'rgba(100,116,139,0.65)' }}
              title={track.artist}
            >
              {track.artist}
            </p>
          </div>

          {/* Controls */}
          <div className="flex items-center" style={{ gap: 14 }}>
            <button
              onClick={() => action('prev')}
              className="transition-colors focus:outline-none"
              style={{ color: 'rgba(100,116,139,0.55)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.9)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.55)')}
            >
              <SkipBack size={14} fill="currentColor" />
            </button>

            <button
              onClick={() => action(track.is_playing ? 'pause' : 'play')}
              className="transition-colors focus:outline-none flex items-center justify-center rounded-full flex-shrink-0"
              style={{
                width: 34, height: 34,
                background: 'rgba(139,92,246,0.18)',
                color: 'rgba(167,139,250,1)',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(139,92,246,0.35)'
                e.currentTarget.style.color = '#fff'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'rgba(139,92,246,0.18)'
                e.currentTarget.style.color = 'rgba(167,139,250,1)'
              }}
            >
              {track.is_playing
                ? <Pause size={16} fill="currentColor" />
                : <Play  size={16} fill="currentColor" style={{ marginLeft: 2 }} />
              }
            </button>

            <button
              onClick={() => action('next')}
              className="transition-colors focus:outline-none"
              style={{ color: 'rgba(100,116,139,0.55)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.9)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(100,116,139,0.55)')}
            >
              <SkipForward size={14} fill="currentColor" />
            </button>
          </div>

          {/* Progress bar + times */}
          <div className="flex items-center" style={{ gap: 5 }}>
            <span
              className="font-mono tabular-nums flex-shrink-0"
              style={{ fontSize: 10, color: 'rgba(100,116,139,0.6)', minWidth: 28 }}
            >
              {fmt(progress)}
            </span>

            <div
              className="flex-1 rounded-full overflow-hidden"
              style={{ height: 3, background: 'rgba(100,116,139,0.18)' }}
            >
              <div
                className="h-full rounded-full transition-[width] duration-1000 ease-linear"
                style={{ width: `${pct}%`, background: 'rgba(139,92,246,0.8)' }}
              />
            </div>

            <span
              className="font-mono tabular-nums flex-shrink-0"
              style={{ fontSize: 10, color: 'rgba(100,116,139,0.6)', minWidth: 28, textAlign: 'right' }}
            >
              {fmt(track.duration_ms)}
            </span>
          </div>

        </div>
      </motion.div>
    </AnimatePresence>
  )
}

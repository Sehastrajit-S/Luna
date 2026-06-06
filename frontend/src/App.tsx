import { useEffect, useState } from 'react'
import { useStore } from './store'
import { useCamera } from './hooks/useCamera'
import { Sidebar } from './components/Layout/Sidebar'
import { TitleBar } from './components/Layout/TitleBar'
import { VoiceOrb } from './components/Voice/VoiceOrb'
import { PhoneMic } from './components/Voice/PhoneMic'
import { ChatWindow } from './components/Chat/ChatWindow'
import { MemoryPanel } from './components/Memory/MemoryPanel'
import { CalendarView } from './components/Calendar/CalendarView'
import { ActivitiesView } from './components/Activities/ActivitiesView'
import { api } from './api/client'
import { AnimatePresence, motion } from 'framer-motion'
import { SpotifyPlayer } from './components/Spotify/SpotifyPlayer'
import { HologramMapOverlay } from './components/Map/HologramMapOverlay'
import { TrainView } from './components/Train/TrainView'
import { ExtractTrainView } from './components/ExtractTrain/ExtractTrainView'
import { SleepView } from './components/Sleep/SleepView'
import { AwayScreen } from './components/Layout/AwayScreen'
import { LunaDashboardView } from './components/Luna/LunaDashboardView'
import { DynamicWidgetOverlay } from './components/Dynamic/DynamicWidgetOverlay'
import { AgentView } from './components/Agent/AgentView'
import { SettingsOverlay } from './components/Settings/SettingsOverlay'
import { useProactiveStream } from './hooks/useProactiveStream'

function StartupSplash({ show }: { show: boolean }) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-luna-bg"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.45, ease: 'easeOut' }}
          style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
        >
          <motion.div
            className="flex flex-col items-center"
            initial={{ opacity: 0, scale: 0.9, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 1.04, y: -6 }}
            transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
            style={{ gap: 18 }}
          >
            <div style={{ pointerEvents: 'none' }}>
              <VoiceOrb size={164} />
            </div>
            <div
              className="text-[11px] font-mono uppercase text-luna-dim"
              style={{ letterSpacing: '0.32em' }}
            >
              Luna
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default function App() {
  const { activeView, setOllamaOnline, setPersonality, addMessage, viewMode, theme } = useStore()
  useCamera()
  useProactiveStream()
  const [showSplash, setShowSplash] = useState(true)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    const t = setTimeout(() => setShowSplash(false), 1700)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {

    // Health check on load
    api.health().then(h => {
      setOllamaOnline(h.ollama)
    }).catch(() => setOllamaOnline(false))

    // Load personality state
    api.getPersonality().then(setPersonality).catch(() => {})

    // Periodic health check
    const t = setInterval(() => {
      api.health().then(h => setOllamaOnline(h.ollama)).catch(() => setOllamaOnline(false))
    }, 30_000)

    const proactive = setInterval(() => {
      api.getProactive()
        .then(({ messages }) => {
          messages.forEach((content, index) => {
            addMessage({
              id: Date.now() + index,
              role: 'assistant',
              content,
              created_at: new Date().toISOString(),
            })
          })
        })
        .catch(() => {})
    }, 20_000)

    return () => {
      clearInterval(t)
      clearInterval(proactive)
    }
  }, [setOllamaOnline, setPersonality, addMessage])

  // ── Luna dashboard: full-screen HUD ─────────────────────────────────────────
  if (viewMode === 'luna') {
    return (
      <>
        <LunaDashboardView />
        <HologramMapOverlay />
        <DynamicWidgetOverlay />
        <AwayScreen />
        <StartupSplash show={showSplash} />
        <SettingsOverlay />
      </>
    )
  }

  // ── User mode: pure voice screen ─────────────────────────────────────────
  if (viewMode === 'user') {
    return (
      <>
        <div className="flex flex-col h-full bg-luna-bg overflow-hidden">
          <TitleBar />
          <div className="flex flex-1 items-center justify-center">
            <div className="flex flex-col items-center" style={{ gap: 40 }}>
              <VoiceOrb size={200} showLabel />
              <PhoneMic />
              <SpotifyPlayer />
            </div>
          </div>
        </div>
        <HologramMapOverlay />
        <DynamicWidgetOverlay />
        <AwayScreen />
        <StartupSplash show={showSplash} />
        <SettingsOverlay />
      </>
    )
  }

  const views = {
    chat: ChatWindow,
    memory: MemoryPanel,
    calendar: CalendarView,
    activities: ActivitiesView,
    agent: AgentView,
    sleep: SleepView,
    train: TrainView,
    extract: ExtractTrainView,
  }
  const View = views[activeView as keyof typeof views] ?? views.chat

  return (
    <>
      <div className="flex flex-col h-full bg-luna-bg text-luna-text overflow-hidden">
        <TitleBar />
        <div className="flex flex-1 overflow-hidden min-h-0">
          <Sidebar />
          <main className="flex-1 overflow-hidden">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeView}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="h-full"
              >
                <View />
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>
      <HologramMapOverlay />
      <DynamicWidgetOverlay />
      <AwayScreen />
      <StartupSplash show={showSplash} />
      <SettingsOverlay />
    </>
  )
}

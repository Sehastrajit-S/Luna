import { useEffect } from 'react'
import { useStore } from '../store'

// Base URL from Electron preload or same-origin
const BASE = (window as any).electronAPI?.apiBase ?? ''

export function useProactiveStream() {
  const addMessage       = useStore(s => s.addMessage)
  const setProactivePulse = useStore(s => s.setProactivePulse)

  useEffect(() => {
    let active = true
    let retryDelay = 3000
    let abortCtrl: AbortController | null = null

    async function connect() {
      if (!active) return
      abortCtrl = new AbortController()
      try {
        const res = await fetch(`${BASE}/api/proactive/stream`, {
          signal: abortCtrl.signal,
          headers: { Accept: 'text/event-stream' },
        })
        if (!res.ok || !res.body) throw new Error('stream unavailable')

        retryDelay = 3000
        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buf = ''

        while (active) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const ev = JSON.parse(line.slice(6))
              if (ev.type === 'luna_speak' && ev.message) {
                addMessage({
                  id: Date.now() + Math.random(),
                  role: 'assistant',
                  content: ev.message,
                  created_at: new Date().toISOString(),
                })
                setProactivePulse(true)
                setTimeout(() => setProactivePulse(false), 3500)
              }
            } catch { /* skip malformed */ }
          }
        }
      } catch (err: any) {
        if (err?.name === 'AbortError' || !active) return
        // reconnect with backoff
        retryDelay = Math.min(retryDelay * 1.5, 30_000)
        setTimeout(connect, retryDelay)
      }
    }

    connect()
    return () => {
      active = false
      abortCtrl?.abort()
    }
  }, [addMessage, setProactivePulse])
}

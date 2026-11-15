import { useRef, useState } from 'react'
import { Mic, Square } from 'lucide-react'
import { authHeaders } from '../../api/client'

type MicState = 'idle' | 'recording' | 'thinking'

export function PhoneMic() {
  const [state, setState] = useState<MicState>('idle')
  const [message, setMessage] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  const speak = (text: string) => {
    if (!text || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1
    utterance.volume = 1
    window.speechSynthesis.speak(utterance)
  }

  const sendAudio = async (blob: Blob) => {
    setState('thinking')
    setMessage('thinking...')
    try {
      const form = new FormData()
      form.append('audio', blob, 'phone.webm')
      const res = await fetch('/api/voice/mobile', {
        method: 'POST',
        headers: authHeaders(),
        body: form,
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const data = await res.json()
      setMessage(data.response || data.transcript || '')
      speak(data.response || '')
    } catch {
      setMessage('phone mic failed')
    } finally {
      setState('idle')
    }
  }

  const start = async () => {
    setMessage('')
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    recorderRef.current = recorder
    chunksRef.current = []
    recorder.ondataavailable = event => {
      if (event.data.size > 0) chunksRef.current.push(event.data)
    }
    recorder.onstop = () => {
      stream.getTracks().forEach(track => track.stop())
      void sendAudio(new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' }))
    }
    recorder.start()
    setState('recording')
    setMessage('listening...')
  }

  const stop = () => {
    recorderRef.current?.stop()
    recorderRef.current = null
  }

  if (window.electronAPI?.isElectron) {
    return null
  }

  const micAvailable = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia

  if (!micAvailable) {
    return (
      <div className="flex flex-col items-center" style={{ gap: 10 }}>
        <button
          disabled
          className="flex items-center justify-center rounded-full"
          style={{
            width: 54,
            height: 54,
            background: 'rgba(100,116,139,0.10)',
            color: 'rgba(100,116,139,0.45)',
            border: '1px solid rgba(100,116,139,0.20)',
            WebkitAppRegion: 'no-drag',
          } as React.CSSProperties}
          title="Phone mic needs HTTPS"
        >
          <Mic size={20} />
        </button>
        <p
          className="max-w-[280px] text-center text-[10px] uppercase select-none"
          style={{ color: 'rgba(100,116,139,0.65)', letterSpacing: '0.14em' }}
        >
          phone mic needs https
        </p>
      </div>
    )
  }

  const active = state !== 'idle'

  return (
    <div className="flex flex-col items-center" style={{ gap: 12 }}>
      <button
        onClick={state === 'recording' ? stop : start}
        disabled={state === 'thinking'}
        className="flex items-center justify-center rounded-full transition-colors"
        style={{
          width: 54,
          height: 54,
          background: active ? 'rgba(139,92,246,0.28)' : 'rgba(100,116,139,0.14)',
          color: active ? 'rgba(216,196,255,1)' : 'rgba(148,163,184,0.85)',
          border: `1px solid ${active ? 'rgba(167,139,250,0.55)' : 'rgba(100,116,139,0.25)'}`,
          WebkitAppRegion: 'no-drag',
        } as React.CSSProperties}
        title={state === 'recording' ? 'Stop phone mic' : 'Use phone mic'}
      >
        {state === 'recording' ? <Square size={18} fill="currentColor" /> : <Mic size={20} />}
      </button>
      {message && (
        <p
          className="max-w-[300px] text-center text-xs uppercase select-none"
          style={{ color: 'rgba(100,116,139,0.65)', letterSpacing: '0.16em' }}
        >
          {message}
        </p>
      )}
    </div>
  )
}

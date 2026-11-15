import { useEffect, useMemo, useRef, useState } from 'react'
import { useMomentum } from '../../store/momentum'
import { pickNextStep, isToday } from './logic'

export function useNextStep() {
  const { tasks, steps, availableMinutes, energy, skipped } = useMomentum()
  return useMemo(
    () => pickNextStep(tasks, steps, availableMinutes, energy, skipped),
    [tasks, steps, availableMinutes, energy, skipped],
  )
}

export function useDoneToday() {
  const steps = useMomentum(s => s.steps)
  return useMemo(() => steps.filter(s => s.done && isToday(s.doneAt)).length, [steps])
}

/** Remaining ms of the focus session, ticking once a second while it runs. */
export function useFocusRemaining(): number | null {
  const focus = useMomentum(s => s.focus)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!focus?.endsAt) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [focus?.endsAt])
  if (!focus) return null
  return focus.endsAt ? Math.max(0, focus.endsAt - now) : focus.remainingMs
}

type Recognition = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}

/** Browser Web Speech API; `supported` is false where it is missing (text box still works). */
export function useSpeech(onText: (text: string) => void) {
  const Ctor = (window as unknown as Record<string, (new () => Recognition) | undefined>).SpeechRecognition
    ?? (window as unknown as Record<string, (new () => Recognition) | undefined>).webkitSpeechRecognition
  const [listening, setListening] = useState(false)
  const rec = useRef<Recognition | null>(null)
  const cb = useRef(onText)
  cb.current = onText

  useEffect(() => () => rec.current?.stop(), [])

  const toggle = () => {
    if (!Ctor) return
    if (listening) { rec.current?.stop(); return }
    const r = new Ctor()
    r.lang = 'en-US'
    r.interimResults = false
    r.continuous = true
    r.onresult = (e) => {
      const text = Array.from(e.results).map(res => res[0].transcript).join(' ')
      cb.current(text)
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    rec.current = r
    r.start()
    setListening(true)
  }

  return { supported: !!Ctor, listening, toggle }
}

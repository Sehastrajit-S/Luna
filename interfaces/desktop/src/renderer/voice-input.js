/**
 * Voice input for the chat box (local, open-source speech-to-text).
 *
 * Click the mic to start, click again to stop — or hold it (or hold Alt+L
 * anywhere in the window) and release. The
 * audio is recorded here (WebM/Opus), transcribed by the backend's local
 * Whisper model, and the text is placed in the message box to review/send.
 * Esc cancels a recording. The microphone is released as soon as it stops.
 *
 * Voice mode (the button beside the mic) is a hands-free spoken conversation:
 * see the section at the bottom of this file.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const HOLD_MS = 350                 // press longer than this = push-to-talk
  const MAX_RECORDING_MS = 5 * 60 * 1000

  const micBtn = document.getElementById('mic-btn')
  const input = document.querySelector('.composer-input')
  const voiceBtn = document.getElementById('voice-mode-btn')
  if (!micBtn || !input || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    voiceBtn?.remove()
    return
  }
  const composerBar = micBtn.closest('.composer-bar')
  const wave = document.getElementById('voice-wave')
  const waveBars = wave?.querySelector('.voice-wave-bars')
  const waveTime = wave?.querySelector('.voice-wave-time')

  // ── Live waveform ──────────────────────────────────────────────────────────
  // Black/charcoal rounded bars, mirrored around the center: low (voice)
  // frequencies in the middle, higher ones toward the edges, so the shape
  // peaks centrally and tapers out — driven by the real microphone signal.
  const BAR_COUNT = 45
  const MIN_H = 3
  const MAX_H = 30
  const bars = []
  const levels = new Float32Array(BAR_COUNT)
  const texture = Array.from({ length: BAR_COUNT }, (_, i) => 0.78 + 0.22 * Math.abs(Math.sin(i * 12.9898) * 43758.5453 % 1))
  const envelope = Array.from({ length: BAR_COUNT }, (_, i) => {
    const x = Math.abs(i - (BAR_COUNT - 1) / 2) / ((BAR_COUNT - 1) / 2)
    return 0.18 + 0.82 * Math.pow(Math.cos(x * Math.PI / 2), 1.4)
  })
  let audioCtx = null
  let analyser = null
  let outputAnalyser = null           // voice mode: Luna's own voice drives the bars while she speaks
  let waveFrozen = false              // hold the resting silhouette (transcribing / thinking)
  let freq = null
  let rafId = 0

  if (waveBars) {
    for (let i = 0; i < BAR_COUNT; i++) {
      const bar = document.createElement('span')
      bar.className = 'voice-wave-bar' + (i % 3 === 1 ? ' is-charcoal' : '')
      bar.style.setProperty('--i', String(Math.abs(i - (BAR_COUNT - 1) / 2)))
      waveBars.append(bar)
      bars.push(bar)
    }
  }

  function startWaveform(mediaStream) {
    if (!bars.length) return
    try {
      audioCtx = new AudioContext()
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 1024
      analyser.smoothingTimeConstant = 0.55
      audioCtx.createMediaStreamSource(mediaStream).connect(analyser)
      freq = new Uint8Array(analyser.frequencyBinCount)
    } catch (error) {
      console.warn('Waveform unavailable', error)
      analyser = null
    }
    levels.fill(0)
    const half = Math.ceil(BAR_COUNT / 2)
    const binHz = (audioCtx?.sampleRate || 48000) / 1024
    const lo = Math.max(1, Math.round(90 / binHz))
    const hi = Math.round(4200 / binHz)
    const render = () => {
      rafId = requestAnimationFrame(render)
      if (waveFrozen) return
      const source = outputAnalyser || analyser
      if (source) source.getByteFrequencyData(freq)
      for (let j = 0; j < half; j++) {
        // Log-spaced speech band: j = 0 is the center bar (lowest band).
        const b0 = Math.round(lo * Math.pow(hi / lo, j / half))
        const b1 = Math.max(b0 + 1, Math.round(lo * Math.pow(hi / lo, (j + 1) / half)))
        let sum = 0
        for (let b = b0; b < b1; b++) sum += source ? freq[b] : 0
        const value = Math.min(1, Math.pow((sum / (b1 - b0)) / 255 * 1.5, 1.25))
        for (const i of [Math.floor((BAR_COUNT - 1) / 2) - j, Math.ceil((BAR_COUNT - 1) / 2) + j]) {
          if (i < 0 || i >= BAR_COUNT) continue
          const target = value * envelope[i] * texture[i]
          levels[i] += (target - levels[i]) * (target > levels[i] ? 0.55 : 0.16)   // fast attack, soft release
          bars[i].style.height = `${(MIN_H + levels[i] * (MAX_H - MIN_H)).toFixed(1)}px`
        }
      }
    }
    render()
  }

  function stopWaveform() {
    cancelAnimationFrame(rafId)
    rafId = 0
    audioCtx?.close().catch(() => {})
    audioCtx = analyser = outputAnalyser = freq = null
    waveFrozen = false
  }

  // Resting silhouette (center-peaked) that ripples while text is prepared.
  function restingBars() {
    bars.forEach((bar, i) => { bar.style.height = `${(MIN_H + envelope[i] * texture[i] * 16).toFixed(1)}px` })
  }

  const defaultPlaceholder = input.placeholder
  let state = 'idle'                  // idle | starting | recording | transcribing
  let recorder = null
  let stream = null
  let chunks = []
  let cancelled = false
  let startedAt = 0
  let timer = null
  let pressTimer = null
  let holdMode = false
  let noticeTimer = null
  let stopRequested = false          // released before the mic finished opening
  let keyHeld = false                // Alt+L push-to-talk in progress

  function setState(next) {
    state = next
    micBtn.classList.toggle('is-recording', next === 'recording')
    micBtn.classList.toggle('is-busy', next === 'starting' || next === 'transcribing')
    micBtn.setAttribute('aria-pressed', String(next === 'recording'))
    // Voice mode: the waveform replaces the text box, and the model picker hides.
    composerBar?.classList.toggle('is-voice', next === 'recording' || next === 'transcribing')
    wave?.classList.toggle('is-transcribing', next === 'transcribing')
    if (next === 'transcribing') restingBars()
    if (next === 'idle') {
      input.placeholder = defaultPlaceholder
      if (waveTime) waveTime.textContent = ''
    }
  }

  function notice(text) {
    clearTimeout(noticeTimer)
    input.placeholder = text
    noticeTimer = setTimeout(() => { if (state === 'idle') input.placeholder = defaultPlaceholder }, 6000)
  }

  function tick() {
    const secs = Math.floor((Date.now() - startedAt) / 1000)
    if (waveTime) waveTime.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`
    micBtn.title = holdMode ? 'Release to stop' : 'Click to stop · Esc to cancel'
    if (Date.now() - startedAt >= MAX_RECORDING_MS) stop()
  }

  function releaseMic() {
    stopWaveform()
    stream?.getTracks().forEach(track => track.stop())
    stream = null
    micBtn.title = 'Voice input — click to talk, or hold (Alt+L)'
  }

  function openMic() {
    return navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
  }

  function micUnavailable(error) {
    const blocked = error?.name === 'NotAllowedError' || error?.name === 'SecurityError'
    notice(blocked
      ? 'Microphone is blocked — allow it in Windows Settings › Privacy › Microphone.'
      : 'No microphone found.')
    console.error('Microphone unavailable', error)
  }

  function recorderMimeType() {
    return MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
  }

  async function transcribeBlob(blob) {
    const form = new FormData()
    form.append('audio', blob, 'dictation.webm')
    const response = await fetch(`${API}/api/voice/transcribe`, { method: 'POST', body: form })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.error || `Transcription failed (${response.status})`)
    return String(data.text || '').trim()
  }

  function describeError(error) {
    return error.message.includes('fetch') ? 'Couldn’t reach Luna’s backend.' : error.message
  }

  async function start() {
    if (state !== 'idle' || voiceMode) return
    setState('starting')
    cancelled = false
    stopRequested = false
    chunks = []
    try {
      stream = await openMic()
    } catch (error) {
      setState('idle')
      micUnavailable(error)
      return
    }
    const mimeType = recorderMimeType()
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
    recorder.onstop = onRecorderStop
    recorder.start(250)
    startedAt = Date.now()
    setState('recording')
    startWaveform(stream)
    tick()
    timer = setInterval(tick, 500)
    if (stopRequested) stop()
  }

  function stop({ cancel = false } = {}) {
    if (state === 'starting') {
      stopRequested = true       // applied as soon as recording actually begins
      return
    }
    if (state !== 'recording' || !recorder) return
    cancelled = cancel
    clearInterval(timer)
    recorder.stop()
  }

  async function onRecorderStop() {
    releaseMic()
    const blob = new Blob(chunks, { type: recorder?.mimeType || 'audio/webm' })
    recorder = null
    chunks = []
    if (cancelled) {
      setState('idle')
      return
    }
    if (blob.size < 2000 || Date.now() - startedAt < 400) {
      setState('idle')
      notice('Didn’t catch that — hold the mic a little longer.')
      return
    }
    setState('transcribing')
    try {
      const text = await transcribeBlob(blob)
      setState('idle')
      if (!text) {
        notice('Didn’t hear any speech — try again.')
        return
      }
      insertText(text)
    } catch (error) {
      setState('idle')
      notice(describeError(error))
      console.error('Transcription failed', error)
    }
  }

  function insertText(text) {
    const current = input.value
    const needsSpace = current && !/\s$/.test(current)
    input.value = current + (needsSpace ? ' ' : '') + text
    input.focus()
    input.setSelectionRange(input.value.length, input.value.length)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }

  // Click = toggle; press-and-hold = push-to-talk (release stops).
  micBtn.addEventListener('pointerdown', event => {
    if (event.button !== 0 || voiceMode) return
    if (state === 'recording') return          // the click handler below stops it
    holdMode = false
    clearTimeout(pressTimer)
    pressTimer = setTimeout(() => { holdMode = true }, HOLD_MS)
    start()
  })
  micBtn.addEventListener('pointerup', () => {
    clearTimeout(pressTimer)
    if (holdMode && state === 'recording') stop()
  })
  micBtn.addEventListener('pointerleave', () => {
    clearTimeout(pressTimer)
    if (holdMode && state === 'recording') stop()
  })
  micBtn.addEventListener('click', () => {
    // A click that started the recording (pointerdown) must not immediately stop it.
    if (state === 'recording' && !holdMode && Date.now() - startedAt > HOLD_MS) stop()
  })

  window.addEventListener('keydown', event => {
    if (event.key === 'Escape' && state === 'recording') {
      event.preventDefault()
      stop({ cancel: true })
      return
    }
    // Hold Alt+L anywhere in the window to talk; release to stop.
    if (event.altKey && !event.ctrlKey && !event.metaKey && event.code === 'KeyL') {
      event.preventDefault()
      if (event.repeat || keyHeld || state !== 'idle' || voiceMode) return
      keyHeld = true
      holdMode = true
      start()
    }
  })

  function releaseKey() {
    if (!keyHeld) return
    keyHeld = false
    if (state === 'recording' || state === 'starting') stop()
  }

  window.addEventListener('keyup', event => {
    // Letting go of either key ends the recording.
    if (event.code === 'KeyL' || event.key === 'Alt') {
      // Releasing Alt would otherwise focus the window's menu bar.
      if (keyHeld && event.key === 'Alt') event.preventDefault()
      releaseKey()
    }
  })
  // Switching away mid-hold never leaves the mic running.
  window.addEventListener('blur', releaseKey)

  // ── Voice mode (voice-to-voice) ────────────────────────────────────────────
  // Hands-free conversation: Luna listens, detects when you've finished
  // speaking, sends the transcript as a normal chat message, reads the reply
  // aloud as it streams in, then listens again. Talking over Luna interrupts
  // her. Click the button again (or press Esc) to leave voice mode.
  const TICK_MS = 50
  const SPEECH_MIN_MS = 200           // sustained sound before it counts as speech
  const END_OF_SPEECH_MS = 1100       // silence that ends your turn
  const BARGE_IN_MS = 350             // sustained loud speech that interrupts Luna
  const IDLE_RESTART_MS = 20 * 1000   // drop silent audio instead of growing the buffer
  const MAX_TURN_MS = 2 * 60 * 1000
  const SPEAK_CHUNK_CHARS = 320
  const PHASE_LABELS = { listening: 'Listening', thinking: 'Thinking', speaking: 'Speaking' }

  let voiceMode = null

  function micLevel(v) {
    if (!analyser) return 0
    analyser.getFloatTimeDomainData(v.samples)
    let sum = 0
    for (const sample of v.samples) sum += sample * sample
    return Math.sqrt(sum / v.samples.length)
  }

  function setPhase(v, phase) {
    v.phase = phase
    try { v.opts?.onPhase?.(phase) } catch { /* the view's problem, not the conversation's */ }
    composerBar?.setAttribute('data-voice-phase', phase)
    if (waveTime) waveTime.textContent = PHASE_LABELS[phase] || ''
    wave?.classList.toggle('is-transcribing', phase === 'thinking')
    waveFrozen = phase === 'thinking'
    if (waveFrozen) restingBars()
  }

  // opts (voice-only mode): onPhase(phase), onHeard(text), onReplyPart(text), onExit(),
  // beforeSend(text) → { text, files } to send, or null to skip this turn (e.g. a scan was cancelled).
  async function enterVoiceMode(opts = {}) {
    if (voiceMode || state !== 'idle') return false
    voiceBtn.classList.add('is-busy')
    let micStream
    try {
      micStream = await openMic()
    } catch (error) {
      voiceBtn.classList.remove('is-busy')
      micUnavailable(error)
      return
    }
    voiceBtn.classList.remove('is-busy')
    const v = {
      stream: micStream, phase: '', turn: 0, samples: null, timer: null,
      recording: null, heard: false, speechMs: 0, silenceMs: 0, turnStart: 0, noise: 0.01, loudMs: 0,
      queue: [], synthChain: Promise.resolve(), playing: false, current: null,
      replyDone: true, pendingReply: Promise.resolve(), opts,
    }
    voiceMode = v
    startWaveform(micStream)
    if (!analyser) {
      exitVoiceMode()
      notice('Voice mode needs microphone audio analysis, which isn’t available here.')
      return
    }
    audioCtx.resume().catch(() => {})
    v.samples = new Float32Array(analyser.fftSize)
    composerBar?.classList.add('is-voice', 'is-conversation')
    voiceBtn.classList.add('is-active')
    voiceBtn.setAttribute('aria-pressed', 'true')
    voiceBtn.title = 'End voice mode (Esc)'
    v.timer = setInterval(monitor, TICK_MS)
    listen(v)
    return true
  }

  function exitVoiceMode() {
    const v = voiceMode
    if (!v) return
    voiceMode = null
    clearInterval(v.timer)
    stopPlayback(v)
    if (v.recording?.recorder.state === 'recording') v.recording.recorder.stop()
    v.recording = null
    stopWaveform()
    v.stream.getTracks().forEach(track => track.stop())
    composerBar?.classList.remove('is-voice', 'is-conversation')
    composerBar?.removeAttribute('data-voice-phase')
    wave?.classList.remove('is-transcribing')
    if (waveTime) waveTime.textContent = ''
    voiceBtn.classList.remove('is-active')
    voiceBtn.setAttribute('aria-pressed', 'false')
    voiceBtn.title = 'Voice mode — talk with Luna hands-free'
    try { v.opts?.onExit?.() } catch { /* ignore */ }
  }

  // ── Listening ──
  function listen(v) {
    if (voiceMode !== v) return
    setPhase(v, 'listening')
    startRecording(v)
  }

  function startRecording(v) {
    const mimeType = recorderMimeType()
    const recorder = new MediaRecorder(v.stream, mimeType ? { mimeType } : undefined)
    const parts = []
    recorder.ondataavailable = event => { if (event.data.size) parts.push(event.data) }
    recorder.start(250)
    v.recording = { recorder, parts }
    v.heard = false
    v.speechMs = v.silenceMs = 0
    v.turnStart = Date.now()
  }

  function finishRecording(v) {
    const recording = v.recording
    v.recording = null
    return new Promise(resolve => {
      if (!recording || recording.recorder.state === 'inactive') return resolve(null)
      recording.recorder.onstop = () => resolve(new Blob(recording.parts, { type: recording.recorder.mimeType || 'audio/webm' }))
      recording.recorder.stop()
    })
  }

  function monitor() {
    const v = voiceMode
    if (!v) return
    const level = micLevel(v)
    if (v.phase === 'listening' && v.recording) {
      // Adaptive threshold: speech is a few times louder than the room.
      if (level > Math.max(0.012, v.noise * 3)) {
        v.speechMs += TICK_MS
        v.silenceMs = 0
        if (v.speechMs >= SPEECH_MIN_MS) v.heard = true
      } else {
        v.silenceMs += TICK_MS
        if (!v.heard) {
          v.speechMs = Math.max(0, v.speechMs - TICK_MS)
          v.noise += (level - v.noise) * 0.05
        }
      }
      const elapsed = Date.now() - v.turnStart
      if (v.heard && (v.silenceMs >= END_OF_SPEECH_MS || elapsed >= MAX_TURN_MS)) {
        endUtterance(v)
      } else if (!v.heard && elapsed >= IDLE_RESTART_MS) {
        finishRecording(v)
        startRecording(v)
      }
    } else if (v.phase === 'speaking') {
      // A much higher bar than listening, so Luna's own voice doesn't interrupt her.
      v.loudMs = level > Math.max(0.05, v.noise * 8) ? v.loudMs + TICK_MS : 0
      if (v.loudMs >= BARGE_IN_MS) bargeIn(v)
    }
  }

  async function endUtterance(v) {
    setPhase(v, 'thinking')
    const blob = await finishRecording(v)
    if (voiceMode !== v) return
    let text = ''
    try {
      if (blob && blob.size >= 2000) text = await transcribeBlob(blob)
    } catch (error) {
      if (voiceMode !== v) return
      exitVoiceMode()
      notice(describeError(error))
      console.error('Voice mode transcription failed', error)
      return
    }
    if (voiceMode !== v) return
    if (!text) {
      listen(v)
      return
    }
    try { v.opts?.onHeard?.(text) } catch { /* ignore */ }
    reply(v, text)
  }

  // ── Replying ──
  async function reply(v, text) {
    const turn = ++v.turn
    await v.pendingReply              // a reply the user talked over may still be streaming
    if (voiceMode !== v || v.turn !== turn) return
    if (!window.lunaChat || window.lunaChat.isBusy()) {
      listen(v)
      return
    }
    let files = []
    if (v.opts?.beforeSend) {
      // Voice-only mode: "scan this …" takes a photo first, and it goes with the message.
      let prepared = null
      try { prepared = await v.opts.beforeSend(text) } catch (error) { console.error('Voice-only step failed', error) }
      if (voiceMode !== v || v.turn !== turn) return
      if (prepared === null) {
        listen(v)
        return
      }
      text = prepared.text ?? text
      files = prepared.files || []
    }
    v.replyDone = false
    v.synthChain = Promise.resolve()
    const pending = window.lunaChat.send(text, {
      files,
      onPart: part => {
        if (voiceMode !== v || v.turn !== turn) return
        try { v.opts?.onReplyPart?.(part) } catch { /* ignore */ }
        enqueueSpeech(v, turn, part)
      },
    })
    v.pendingReply = pending.then(() => {}, () => {})
    await v.pendingReply              // errors are shown in the reply bubble
    if (voiceMode !== v || v.turn !== turn) return
    v.replyDone = true
    if (!v.playing) listen(v)
  }

  // Markdown → plain sentences worth saying out loud.
  function speakable(markdown) {
    return String(markdown)
      .replace(/<!--[\s\S]*?-->/g, ' ')
      .replace(/```[\s\S]*?(```|$)/g, ' ')
      .replace(/\[[A-Z_]+:[^\]]*\]/g, ' ')
      .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
      .replace(/https?:\/\/\S+/g, ' ')
      .replace(/`([^`]*)`/g, '$1')
      .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+[.)])\s+/gm, '')
      .replace(/[*_~|#]+/g, '')
      .replace(/([^.!?:;,\s])[ \t]*\n+/g, '$1. ')   // headings and list items get a pause
      .replace(/\s+/g, ' ')
      .trim()
  }

  function speechChunks(text) {
    const sentences = text.match(/[^.!?]+(?:[.!?]+["')\]]*|$)\s*/g) || []
    const chunks = []
    let current = ''
    for (const sentence of sentences) {
      if (current && (current + sentence).length > SPEAK_CHUNK_CHARS) {
        chunks.push(current.trim())
        current = ''
      }
      current += sentence
    }
    if (current.trim()) chunks.push(current.trim())
    return chunks.map(chunk => chunk.slice(0, 2000))
  }

  async function synthesize(text) {
    const response = await fetch(`${API}/api/voice/speak`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.error || `Speech failed (${response.status})`)
    }
    return response.blob()
  }

  function enqueueSpeech(v, turn, part) {
    for (const chunk of speechChunks(speakable(part))) {
      // Synthesize in order, one at a time, while earlier chunks play.
      const audio = v.synthChain.then(() => synthesize(chunk)).catch(error => {
        if (voiceMode === v && v.turn === turn) {
          if (v.opts?.onSpeechError) v.opts.onSpeechError(error)   // voice-only: keep going, show the text
          else {
            exitVoiceMode()
            notice(describeError(error))
          }
        }
        console.error('Voice mode speech failed', error)
        return null
      })
      v.synthChain = audio
      v.queue.push(audio)
    }
    if (!v.playing) speakQueue(v, turn)
  }

  async function speakQueue(v, turn) {
    v.playing = true
    while (voiceMode === v && v.turn === turn && v.queue.length) {
      const blob = await v.queue.shift()
      if (voiceMode !== v || v.turn !== turn) return
      if (!blob) continue
      if (v.phase !== 'speaking') setPhase(v, 'speaking')
      await play(v, blob)
    }
    if (voiceMode !== v || v.turn !== turn) return
    v.playing = false
    if (v.replyDone) listen(v)
    else setPhase(v, 'thinking')     // more of the reply is still streaming in
  }

  function play(v, blob) {
    return new Promise(resolve => {
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      let source = null
      let tap = null
      const done = () => {
        if (v.current?.audio !== audio) return
        v.current = null
        audio.pause()
        source?.disconnect()
        tap?.disconnect()
        if (outputAnalyser === tap) outputAnalyser = null
        URL.revokeObjectURL(url)
        resolve()
      }
      v.current = { audio, done }
      audio.onended = done
      audio.onerror = done
      if (audioCtx?.state === 'running') {
        try {
          source = audioCtx.createMediaElementSource(audio)
          tap = audioCtx.createAnalyser()
          tap.fftSize = 1024
          tap.smoothingTimeConstant = 0.55
          source.connect(tap)
          tap.connect(audioCtx.destination)
          outputAnalyser = tap
        } catch {
          source = tap = null      // plain playback still works
        }
      }
      audio.play().catch(done)
    })
  }

  function stopPlayback(v) {
    v.queue = []
    v.playing = false
    v.current?.done()
  }

  function bargeIn(v) {
    v.turn++                          // ignore the rest of the interrupted reply
    v.loudMs = 0
    stopPlayback(v)
    listen(v)
  }

  // For voice-only mode (voice-only.js): the same conversation engine, its own screen.
  window.lunaVoice = {
    start: opts => enterVoiceMode(opts),
    stop: () => exitVoiceMode(),
    active: () => Boolean(voiceMode),
    phase: () => voiceMode?.phase || '',
  }

  voiceBtn?.addEventListener('click', () => {
    if (voiceMode) exitVoiceMode()
    else enterVoiceMode()
  })
  window.addEventListener('keydown', event => {
    if (event.key === 'Escape' && voiceMode) {
      event.preventDefault()
      exitVoiceMode()
    }
  })
})()

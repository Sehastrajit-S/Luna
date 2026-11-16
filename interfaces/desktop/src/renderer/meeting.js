/**
 * Meeting mode: one orb. Tap to record, tap again to stop; Luna transcribes the
 * recording and writes minutes (server/services/meetings). The recording is
 * uploaded in numbered 5-second chunks while it runs, so a dropped connection
 * or closed tab costs seconds, not the meeting.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const root = document.getElementById('meeting')
  const orb = document.getElementById('meeting-orb')
  const timeEl = document.getElementById('meeting-time')
  const statusEl = document.getElementById('meeting-status')
  const viewBtn = document.getElementById('meeting-view')
  const sheet = document.getElementById('meeting-sheet')
  const minutesEl = document.getElementById('meeting-minutes')
  const transcriptEl = document.getElementById('meeting-transcript')
  const savedEl = document.getElementById('meeting-saved')
  if (!root || !orb) return

  const ACTIVE_KEY = 'luna_meeting_processing'
  const CHUNK_MS = 5000

  let state = 'idle'            // idle | starting | recording | stopping | processing | done | error
  let meeting = null            // server view of the current meeting
  let recorder = null
  let stream = null
  let audio = null              // { ctx, analyser, data, raf }
  let wakeLock = null
  let startedAt = 0
  let clock = 0
  let pollTimer = 0
  let seq = 0
  const queue = []
  let uploading = null

  // ── UI ──────────────────────────────────────────────────────────────────────
  const LABELS = {
    idle: 'Start recording the meeting', starting: 'Starting', recording: 'Stop and write minutes',
    stopping: 'Saving', processing: 'Writing minutes', done: 'Record a new meeting', error: 'Retry',
  }

  function setState(next, status) {
    state = next
    root.dataset.state = next
    statusEl.textContent = status
    orb.setAttribute('aria-label', LABELS[next] || 'Meeting')
    orb.disabled = next === 'starting' || next === 'stopping' || next === 'processing'
    viewBtn.hidden = next !== 'done'
  }

  function mmss(ms) {
    const s = Math.floor(ms / 1000)
    const h = Math.floor(s / 3600)
    const pad = n => String(n).padStart(2, '0')
    return h ? `${h}:${pad(Math.floor(s % 3600 / 60))}:${pad(s % 60)}` : `${pad(Math.floor(s / 60))}:${pad(s % 60)}`
  }

  function setProgress(value) {
    root.style.setProperty('--progress', String(Math.max(0, Math.min(1, value || 0))))
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, options)
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = data.detail
      throw new Error(typeof detail === 'string' ? detail : detail?.message || `Luna's server returned ${response.status}`)
    }
    return data
  }

  // ── Microphone level → orb glow ────────────────────────────────────────────
  function startMeter() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      ctx.createMediaStreamSource(stream).connect(analyser)
      audio = { ctx, analyser, data: new Uint8Array(analyser.fftSize), level: 0, raf: 0 }
      const frame = () => {
        analyser.getByteTimeDomainData(audio.data)
        let sum = 0
        for (const v of audio.data) sum += ((v - 128) / 128) ** 2
        const rms = Math.sqrt(sum / audio.data.length)
        audio.level = audio.level * 0.75 + Math.min(1, rms * 4) * 0.25
        root.style.setProperty('--level', audio.level.toFixed(3))
        audio.raf = requestAnimationFrame(frame)
      }
      frame()
    } catch { /* no meter, recording still works */ }
  }

  function stopMeter() {
    if (!audio) return
    cancelAnimationFrame(audio.raf)
    audio.ctx.close().catch(() => {})
    audio = null
    root.style.setProperty('--level', '0')
  }

  async function keepAwake(on) {
    try {
      if (on && 'wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen')
      else if (!on && wakeLock) { await wakeLock.release(); wakeLock = null }
    } catch { /* not supported or denied: fine */ }
  }

  // ── Upload queue: chunks in order, retried, never skipped ─────────────────
  function pump() {
    if (uploading) return uploading
    uploading = (async () => {
      while (queue.length) {
        const chunk = queue[0]
        let attempt = 0
        for (;;) {
          try {
            await api(`/api/meetings/${encodeURIComponent(meeting.id)}/audio?seq=${chunk.seq}`, {
              method: 'PUT', headers: { 'Content-Type': 'application/octet-stream' }, body: chunk.blob,
            })
            break
          } catch (error) {
            attempt += 1
            if (attempt >= 6) throw error
            await new Promise(r => setTimeout(r, Math.min(8000, 500 * 2 ** attempt)))
          }
        }
        queue.shift()
      }
    })().finally(() => { uploading = null })
    return uploading
  }

  // ── Recording ──────────────────────────────────────────────────────────────
  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setState('idle', 'This browser can’t record here. Use the desktop app, or open Luna over https.')
      return
    }
    setState('starting', 'Starting…')
    timeEl.textContent = ''
    setProgress(0)
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
    } catch {
      setState('idle', 'Microphone access was blocked. Allow it, then tap the orb again.')
      return
    }
    try {
      meeting = await api('/api/meetings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      })
    } catch (error) {
      stream.getTracks().forEach(t => t.stop())
      setState('idle', `Couldn’t start the meeting: ${error.message}`)
      return
    }
    seq = 0
    queue.length = 0
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    recorder.ondataavailable = event => {
      if (!event.data?.size) return
      queue.push({ seq: seq++, blob: event.data })
      pump().catch(() => { /* retried on stop */ })
    }
    recorder.start(CHUNK_MS)
    startedAt = Date.now()
    timeEl.textContent = '00:00'
    clock = setInterval(() => { timeEl.textContent = mmss(Date.now() - startedAt) }, 500)
    startMeter()
    keepAwake(true)
    setState('recording', 'Recording. Tap the orb to stop and write the minutes.')
  }

  async function stopRecording() {
    setState('stopping', 'Saving the recording…')
    clearInterval(clock)
    await new Promise(resolve => {
      if (!recorder || recorder.state === 'inactive') return resolve()
      recorder.addEventListener('stop', resolve, { once: true })
      recorder.stop()                         // fires a final dataavailable first
    })
    stream?.getTracks().forEach(t => t.stop())
    stopMeter()
    keepAwake(false)
    await finishUpload()
  }

  async function finishUpload() {
    setState('stopping', 'Saving the recording…')
    try {
      while (queue.length || uploading) await pump()
    } catch {
      setState('error', 'Part of the recording didn’t upload. Check the connection, then tap the orb to retry.')
      return
    }
    try {
      meeting = await api(`/api/meetings/${encodeURIComponent(meeting.id)}/finish`, { method: 'POST' })
    } catch (error) {
      setState('error', `${error.message} Tap the orb to try again.`)
      return
    }
    try { localStorage.setItem(ACTIVE_KEY, meeting.id) } catch { /* fine */ }
    follow()
  }

  // ── Processing ─────────────────────────────────────────────────────────────
  function follow() {
    clearTimeout(pollTimer)
    show(meeting)
    if (meeting.status === 'processing') pollTimer = setTimeout(refresh, 2000)
  }

  async function refresh() {
    try {
      meeting = await api(`/api/meetings/${encodeURIComponent(meeting.id)}`)
    } catch (error) {
      setState('processing', `Waiting for Luna… (${error.message})`)
      pollTimer = setTimeout(refresh, 4000)
      return
    }
    follow()
  }

  function show(m) {
    if (m.duration_s) timeEl.textContent = mmss(m.duration_s * 1000)
    if (m.status === 'processing') {
      const pct = Math.round((m.progress || 0) * 100)
      setProgress(m.progress)
      setState('processing', m.stage === 'writing_minutes' ? `Writing the minutes… ${pct}%` : `Transcribing… ${pct}%`)
    } else if (m.status === 'done') {
      setProgress(1)
      try { localStorage.removeItem(ACTIVE_KEY) } catch { /* fine */ }
      setState('done', 'Minutes ready. Tap the orb to record another meeting.')
      renderMinutes(m)
    } else if (m.status === 'error' || m.status === 'interrupted') {
      setProgress(0)
      setState('error', `${m.error || 'Something went wrong.'} Tap the orb to retry.`)
    }
  }

  function renderMinutes(m) {
    const md = text => (typeof window.renderMarkdown === 'function' ? window.renderMarkdown(text || '') : '')
    minutesEl.innerHTML = md(m.minutes)
    transcriptEl.innerHTML = md(m.transcript)
    savedEl.textContent = `Saved in Library → Created by Luna → ${m.folder}`
  }

  function openSheet() {
    if (!meeting?.minutes) return
    sheet.hidden = false
    document.getElementById('meeting-sheet-close')?.focus()
  }

  function closeSheet() {
    sheet.hidden = true
    viewBtn.focus()
  }

  // ── Wiring ─────────────────────────────────────────────────────────────────
  orb.addEventListener('click', () => {
    if (state === 'recording') stopRecording()
    else if (state === 'error' && meeting && (queue.length || meeting.status !== 'recording')) {
      if (queue.length) finishUpload()
      else {
        setState('processing', 'Retrying…')
        api(`/api/meetings/${encodeURIComponent(meeting.id)}/finish`, { method: 'POST' })
          .then(m => { meeting = m; follow() })
          .catch(error => setState('error', `${error.message} Tap the orb to try again.`))
      }
    } else if (state === 'idle' || state === 'done' || state === 'error') startRecording()
  })
  viewBtn.addEventListener('click', openSheet)
  document.getElementById('meeting-sheet-close')?.addEventListener('click', closeSheet)
  sheet.addEventListener('click', event => { if (event.target === sheet) closeSheet() })
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !sheet.hidden) closeSheet() })
  document.getElementById('meeting-copy')?.addEventListener('click', async event => {
    const button = event.currentTarget
    try {
      if (window.electronAPI?.copyText) await window.electronAPI.copyText(meeting.minutes)
      else await navigator.clipboard.writeText(meeting.minutes)
      button.textContent = 'Copied'
    } catch {
      button.textContent = 'Copy failed'
    }
    setTimeout(() => { button.textContent = 'Copy' }, 1600)
  })

  window.addEventListener('beforeunload', event => {
    if (state === 'recording' || state === 'stopping') {
      event.preventDefault()
      event.returnValue = ''
    }
  })

  async function resume() {
    let id = null
    try { id = localStorage.getItem(ACTIVE_KEY) } catch { /* fine */ }
    if (!id || state !== 'idle') return
    try {
      meeting = await api(`/api/meetings/${encodeURIComponent(id)}`)
      follow()
    } catch {
      try { localStorage.removeItem(ACTIVE_KEY) } catch { /* fine */ }
    }
  }

  window.lunaOpenMeeting = () => {
    if (typeof showView === 'function') showView(document.getElementById('view-meeting'))
    resume()
  }
})()

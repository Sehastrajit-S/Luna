/**
 * Voice-only mode (Apps → Voice): a full-screen, hands-free conversation.
 * The same engine as the composer's voice mode (voice-input.js: listening,
 * end of speech, spoken replies, barge-in), shown big, plus one thing it adds:
 *
 *   "scan this …"  → the camera opens (back camera on a phone, webcam on a PC),
 *                    the photo is taken once the picture holds still, and goes
 *                    with the request: "…and find prices at stores",
 *                    "…QR and fill the form", "…what does it say".
 *
 * Over plain http a phone browser blocks the live camera, so it falls back to
 * the phone's camera app (one tap). Everything also lands in the chat history.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const $ = id => document.getElementById(id)
  const root = $('voice-only')
  if (!root) return

  const orb = $('vo-orb')
  const statusEl = $('vo-status')
  const heardEl = $('vo-heard')
  const replyEl = $('vo-reply')
  const video = $('vo-camera')
  const frame = $('vo-frame')
  const countEl = $('vo-count')
  const shotBtn = $('vo-shot')
  const photoLabel = $('vo-photo-label')
  const photoInput = $('vo-photo')
  const SCAN_RE = /\bscan(?:ned|ning)?\b/i
  const STEADY_FRAMES = 6          // ~1.2 s of a still picture
  const MIN_SCAN_MS = 1500         // time to bring the thing into view
  const MAX_SCAN_MS = 12000        // then take it anyway

  let open = false
  let camera = null                // MediaStream while scanning
  let scan = null                  // { resolve, timer } while a scan is waiting for a photo
  let reply = ''

  const LABELS = { listening: 'Listening…', thinking: 'Thinking…', speaking: 'Speaking', scanning: 'Scanning — hold it steady' }

  function setPhase(phase) {
    root.dataset.phase = phase
    statusEl.textContent = LABELS[phase] || ''
  }

  // ── Speaking a short prompt during a scan (the engine isn't talking then) ──
  async function say(text) {
    try {
      const response = await fetch(`${API}/api/voice/speak`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
      })
      if (!response.ok) return
      const audio = new Audio(URL.createObjectURL(await response.blob()))
      await audio.play().catch(() => {})
    } catch { /* a silent prompt is fine */ }
  }

  // ── Camera ──
  function liveCameraPossible() {
    return Boolean(navigator.mediaDevices?.getUserMedia) && (window.isSecureContext || location.hostname === 'localhost')
  }

  async function startCamera() {
    camera = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
    })
    video.srcObject = camera
    video.hidden = false
    frame.hidden = false
    await video.play().catch(() => {})
  }

  function stopCamera() {
    camera?.getTracks().forEach(track => track.stop())
    camera = null
    video.srcObject = null
    video.hidden = true
    frame.hidden = true
    shotBtn.hidden = true
    photoLabel.hidden = true
    countEl.textContent = ''
  }

  function grabFrame() {
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92))
  }

  // Wait until the picture holds still (the item is in view and steady), then take it.
  function autoCapture() {
    return new Promise(resolve => {
      const probe = document.createElement('canvas')
      probe.width = 64
      probe.height = 48
      const ctx = probe.getContext('2d', { willReadFrequently: true })
      let previous = null
      let still = 0
      const started = Date.now()
      const tick = async () => {
        if (!scan || !camera) return resolve(null)
        const elapsed = Date.now() - started
        if (video.videoWidth) {
          ctx.drawImage(video, 0, 0, 64, 48)
          const pixels = ctx.getImageData(0, 0, 64, 48).data
          // Detail: a blank frame (camera still starting, lens covered) is "still" too, so it must not count.
          let sum = 0, sumSq = 0
          for (let i = 0; i < pixels.length; i += 4) { sum += pixels[i + 1]; sumSq += pixels[i + 1] * pixels[i + 1] }
          const n = 64 * 48
          const detailed = Math.sqrt(Math.max(0, sumSq / n - (sum / n) ** 2)) > 14
          if (previous) {
            let diff = 0
            for (let i = 0; i < pixels.length; i += 4) diff += Math.abs(pixels[i + 1] - previous[i + 1])
            still = detailed && diff / n < 4 ? still + 1 : 0
          }
          previous = pixels
          const ready = elapsed > MIN_SCAN_MS && still >= STEADY_FRAMES
          countEl.textContent = !detailed ? 'Point the camera at it…' : elapsed > MIN_SCAN_MS ? (still ? 'Hold…' : 'Steady…') : ''
          if (ready || elapsed > MAX_SCAN_MS) return resolve(await grabFrame())
        }
        scan.timer = setTimeout(tick, 200)
      }
      tick()
    })
  }

  function photoFromCameraApp() {
    // Plain http on a phone: the browser won't stream the camera, but the camera app works.
    photoLabel.hidden = false
    return new Promise(resolve => {
      photoInput.value = ''
      photoInput.onchange = () => resolve(photoInput.files?.[0] || null)
      scan.timer = setTimeout(() => resolve(null), 60000)
    })
  }

  async function upload(blob, request) {
    const form = new FormData()
    form.append('file', blob, `scan-${Date.now()}.jpg`)
    form.append('for_request', request)   // lets the server skip the slow photo description when it reads the scan itself
    if (typeof activeConversationId === 'number') form.append('conversation_id', String(activeConversationId))
    const response = await fetch(`${API}/api/files`, { method: 'POST', body: form })
    const data = await response.json().catch(() => null)
    if (!response.ok || !data?.id || data.status === 'error') throw new Error(data?.error || data?.detail || 'Upload failed')
    return data
  }

  async function takeScan() {
    setPhase('scanning')
    let blob = null
    scan = { timer: 0 }
    try {
      if (liveCameraPossible()) {
        try {
          await startCamera()
          shotBtn.hidden = false
          say('Hold it steady.')
          blob = await Promise.race([autoCapture(), new Promise(resolve => { scan.manual = resolve })])
        } catch (error) {
          console.warn('Live camera unavailable, using the camera app', error)
          stopCamera()
          say('Tap take photo.')
          blob = await photoFromCameraApp()
        }
      } else {
        say('Tap take photo.')
        blob = await photoFromCameraApp()
      }
    } finally {
      clearTimeout(scan?.timer)
      scan = null
      stopCamera()
    }
    return blob
  }

  shotBtn.addEventListener('click', async () => {
    if (scan?.manual && camera) scan.manual(await grabFrame())
  })

  // ── Engine hooks ──
  async function beforeSend(text) {
    if (!SCAN_RE.test(text)) return { text }
    const blob = await takeScan()
    if (!open) return null
    if (!blob) {
      replyEl.textContent = 'No photo taken, so I skipped that.'
      say('No photo, so I skipped that.')
      return null
    }
    setPhase('thinking')
    statusEl.textContent = 'Reading the photo…'
    try {
      const file = await upload(blob, text)
      return { text, files: [file] }
    } catch (error) {
      replyEl.textContent = `Couldn't send the photo: ${error.message}`
      say("I couldn't send the photo.")
      return null
    }
  }

  function plain(markdown) {
    return String(markdown).replace(/<!--[\s\S]*?-->/g, '').replace(/[*_#`>]+/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').trim()
  }

  async function openVoiceOnly() {
    if (open) return
    if (!window.lunaVoice) return
    open = true
    root.hidden = false
    document.body.classList.add('voice-only-open')
    heardEl.textContent = ''
    replyEl.textContent = ''
    setPhase('thinking')
    statusEl.textContent = 'Starting the microphone…'
    const started = await window.lunaVoice.start({
      onPhase: phase => { if (!scan) setPhase(phase) },
      onHeard: text => {
        heardEl.textContent = text
        reply = ''
        replyEl.textContent = ''
      },
      onReplyPart: part => {
        reply += (reply ? '\n\n' : '') + part
        replyEl.textContent = plain(reply)
        replyEl.scrollTop = replyEl.scrollHeight
      },
      beforeSend,
      onSpeechError: () => {
        if (!root.querySelector('.vo-mute-note')) {
          const note = document.createElement('p')
          note.className = 'vo-hint vo-mute-note'
          note.textContent = 'Luna can’t speak right now (check Settings → Voice), so replies show as text. Keep talking.'
          replyEl.after(note)
        }
      },
      onExit: () => closeVoiceOnly(true),
    })
    if (!started) {
      statusEl.textContent = 'Couldn’t start the microphone. Allow microphone access and try again.'
      root.dataset.phase = 'error'
      open = false
    }
  }

  function closeVoiceOnly(fromEngine = false) {
    if (scan?.manual) scan.manual(null)
    stopCamera()
    if (!fromEngine && window.lunaVoice?.active()) window.lunaVoice.stop()
    open = false
    root.hidden = true
    root.querySelector('.vo-mute-note')?.remove()
    document.body.classList.remove('voice-only-open')
  }

  $('vo-close').addEventListener('click', () => closeVoiceOnly())
  window.lunaOpenVoiceOnly = openVoiceOnly
})()

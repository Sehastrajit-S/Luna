/**
 * Barcode scanner: scan a product (UPC/EAN), see what it is, compare its price
 * at Walmart, Costco, Target, Sam's Club and Safeway.
 *
 * Three ways in, best first:
 *  1. Live camera, when the page may use it (desktop app, localhost, https):
 *     frames are read by the browser's BarcodeDetector where it supports
 *     EAN/UPC (Android, macOS), otherwise sent to Luna's server to decode.
 *  2. "Take a photo": the phone's camera app, then the server decodes the
 *     photo. Works over plain http (e.g. Tailscale), where live camera is blocked.
 *  3. Typing the number under the barcode.
 * The product name (editable) goes to chat with the Store prices skill.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const sheet = document.getElementById('scan-sheet')
  if (!sheet) return

  const $ = id => document.getElementById(id)
  const steps = sheet.querySelectorAll('.scan-step')
  const viewfinder = $('scan-viewfinder')
  const video = $('scan-video')
  const status = $('scan-status')
  const photoInput = $('scan-photo')
  const photoLabel = $('scan-photo-label')
  const codeInput = $('scan-code')
  const query = $('scan-query')

  const FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e']
  const FRAME_MS = 650           // server decode cadence while the camera is live
  let stream = null
  let timer = 0
  let session = 0                // bumps on close/rescan so stale results are ignored
  let busy = false
  let returnFocus = null

  function setStatus(text, tone = '') {
    status.textContent = text
    status.className = `scan-status${tone ? ' is-' + tone : ''}`
  }

  function showStep(name) {
    steps.forEach(step => { step.hidden = step.dataset.step !== name })
  }

  async function errorMessage(response, fallback) {
    const data = await response.json().catch(() => ({}))
    const detail = data.detail
    return { kind: detail?.kind || '', message: detail?.message || (typeof detail === 'string' ? detail : fallback) }
  }

  // ── Camera ────────────────────────────────────────────────────────────────
  function stopCamera() {
    clearTimeout(timer)
    timer = 0
    stream?.getTracks().forEach(track => track.stop())
    stream = null
    video.srcObject = null
    viewfinder.hidden = true
  }

  async function nativeDetector() {
    if (!('BarcodeDetector' in window)) return null
    try {
      const supported = await window.BarcodeDetector.getSupportedFormats()
      const formats = FORMATS.filter(f => supported.includes(f))
      return formats.length ? new window.BarcodeDetector({ formats }) : null
    } catch {
      return null
    }
  }

  // The whole frame as a JPEG for the server. (Cropping to the guide box made
  // OpenCV miss barcodes it reads fine in the full frame.)
  const canvas = document.createElement('canvas')
  function frameBlob() {
    const w = video.videoWidth
    const h = video.videoHeight
    if (!w || !h) return Promise.resolve(null)
    const scale = Math.min(1, 1280 / Math.max(w, h))
    canvas.width = Math.round(w * scale)
    canvas.height = Math.round(h * scale)
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85))
  }

  async function serverDecode(blob) {
    const form = new FormData()
    form.append('image', blob, 'barcode.jpg')
    const response = await fetch(`${API}/api/shopping/barcode/decode`, { method: 'POST', body: form })
    if (response.ok) return (await response.json()).code
    const error = await errorMessage(response, 'Couldn’t read that barcode.')
    if (error.kind === 'no_barcode') return null
    throw new Error(error.message)
  }

  async function startCamera(id) {
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) return false
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      })
    } catch (error) {
      console.warn('Camera unavailable', error)
      return false
    }
    if (id !== session) { stopCamera(); return false }
    video.srcObject = stream
    viewfinder.hidden = false
    await video.play().catch(() => {})
    const detector = await nativeDetector()
    setStatus('Point the camera at the barcode.')

    const tick = async () => {
      if (id !== session || !stream) return
      try {
        let code = null
        if (detector) {
          const found = await detector.detect(video)
          code = found.find(b => /^\d{8,14}$/.test(b.rawValue))?.rawValue || null
        } else {
          const blob = await frameBlob()
          code = blob ? await serverDecode(blob) : null
        }
        if (code && id === session) {
          navigator.vibrate?.(40)
          stopCamera()
          return lookUp(code)
        }
      } catch (error) {
        console.warn('Scan frame failed', error)
      }
      if (id === session && stream) timer = setTimeout(tick, detector ? 150 : FRAME_MS)
    }
    timer = setTimeout(tick, 400)
    return true
  }

  // ── Photo and typed code ─────────────────────────────────────────────────────
  photoInput.addEventListener('change', async () => {
    const file = photoInput.files?.[0]
    photoInput.value = ''
    if (!file || busy) return
    const id = session
    busy = true
    photoLabel.textContent = 'Reading the barcode…'
    setStatus('')
    try {
      const code = await serverDecode(file)
      if (id !== session) return
      if (!code) {
        setStatus('No barcode found. Fill the photo with the barcode, keep it sharp and well lit, and try again.', 'error')
        return
      }
      stopCamera()
      await lookUp(code)
    } catch (error) {
      if (id === session) setStatus(error.message || 'Couldn’t read that photo.', 'error')
    } finally {
      busy = false
      photoLabel.textContent = stream ? 'Or take a photo instead' : 'Take a photo of the barcode'
    }
  })

  // GTIN mod-10 check digit (EAN-8, UPC-A, EAN-13), same rule as the server.
  function validCode(code) {
    if (!/^(\d{8}|\d{12,14})$/.test(code)) return false
    const digits = [...code].map(Number)
    const check = digits.pop()
    const sum = digits.reverse().reduce((total, d, i) => total + d * (i % 2 === 0 ? 3 : 1), 0)
    return (10 - (sum % 10)) % 10 === check
  }

  $('scan-manual').addEventListener('submit', event => {
    event.preventDefault()
    const code = codeInput.value.replace(/[\s-]/g, '')
    if (!/^(\d{8}|\d{12,14})$/.test(code)) {
      setStatus('Type the 8, 12 or 13 digits under the barcode.', 'error')
      return
    }
    if (!validCode(code)) {
      setStatus('That number doesn’t check out. A digit may be mistyped: compare it with the barcode.', 'error')
      codeInput.focus()
      return
    }
    stopCamera()
    lookUp(code)
  })

  // ── Product ──────────────────────────────────────────────────────────────────
  async function lookUp(code) {
    const id = session
    setStatus(`Found ${code}. Looking up the product…`)
    let product = null
    let problem = null
    try {
      const response = await fetch(`${API}/api/shopping/barcode/${encodeURIComponent(code)}`)
      if (response.ok) product = await response.json()
      else problem = await errorMessage(response, 'Couldn’t look up this product.')
    } catch {
      problem = { kind: 'offline', message: 'Couldn’t reach Luna’s server.' }
    }
    if (id !== session) return
    if (problem?.kind === 'invalid_code') {
      await startScan()
      setStatus(problem.message, 'error')
      return
    }
    showProduct(code, product, problem)
  }

  function showProduct(code, product, problem) {
    const img = $('scan-product-img')
    img.hidden = !product?.image
    if (product?.image) img.src = product.image
    else img.removeAttribute('src')
    $('scan-product-title').textContent = product ? product.title : 'Product not identified'
    $('scan-product-meta').textContent = [product?.brand, product?.size, `Barcode ${code}`].filter(Boolean).join(' · ')
    $('scan-product-note').textContent = product
      ? `From ${product.source}. Edit the name below if it’s not quite right.`
      : (problem?.message || 'This barcode isn’t in the free product databases. Type the product name to compare prices.')
    $('scan-product-note').className = `scan-note${product ? '' : ' is-error'}`
    query.value = product ? product.name : ''
    showStep('product')
    if (product) $('scan-compare').querySelector('.is-primary').focus()
    else query.focus()
  }

  $('scan-compare').addEventListener('submit', event => {
    event.preventDefault()
    const name = query.value.trim()
    if (!name) return query.focus()
    close()
    window.lunaAskInNewChat?.(name, { skill: 'store-prices' })
  })

  $('scan-again').addEventListener('click', () => startScan())

  // ── Open / close ─────────────────────────────────────────────────────────────
  async function startScan() {
    const id = ++session
    stopCamera()
    codeInput.value = ''
    showStep('scan')
    setStatus('')
    const live = await startCamera(id)
    if (id !== session) return
    photoLabel.textContent = live ? 'Or take a photo instead' : 'Take a photo of the barcode'
    $('scan-photo-btn').classList.toggle('is-primary', !live)
    if (!live) {
      setStatus(window.isSecureContext
        ? 'Take a photo of the barcode, or type its number.'
        : 'Live scanning needs a secure (https) connection here, so take a photo instead.')
    }
  }

  function open() {
    returnFocus = document.activeElement
    sheet.hidden = false
    $('scan-close').focus()
    startScan()
  }

  function close() {
    if (sheet.hidden) return
    session++
    stopCamera()
    sheet.hidden = true
    if (returnFocus && document.contains(returnFocus)) returnFocus.focus()
  }

  $('scan-close').addEventListener('click', close)
  sheet.addEventListener('click', event => { if (event.target === sheet) close() })
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !sheet.hidden) close() })
  // Never keep the camera on in a background tab. Taking a photo on a phone
  // also hides the page (the camera app opens), so pause rather than close.
  document.addEventListener('visibilitychange', () => {
    if (sheet.hidden) return
    if (document.hidden) {
      stopCamera()
    } else if (!busy && !sheet.querySelector('[data-step="scan"]').hidden && !stream) {
      startCamera(session)
    }
  })

  window.lunaOpenScanner = open
})()

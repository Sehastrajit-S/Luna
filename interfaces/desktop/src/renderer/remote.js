/**
 * Remote control app (sidebar → Apps → Remote control): a chat with your
 * devices. Pick one or more devices from the dropdown at the top, type a task,
 * and each device's own Luna does it and answers in its own bubble
 * (GET/POST /api/remote/devices…). A device's "are you sure?" questions show as
 * Allow / Deny in its bubble. Follow-ups continue the same conversation on each
 * device until "New session".
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const $ = id => document.getElementById(id)
  const root = $('view-remote')
  if (!root) return

  const SELECTED_KEY = 'luna.remote.selected'
  const list = $('rc-devices')
  const notice = $('rc-notice')
  const menu = $('rc-menu')
  const pickerBtn = $('rc-picker-btn')
  const pickerLabel = $('rc-picker-label')
  const pickerIcon = $('rc-picker-icon')
  const form = $('rc-form')
  const input = $('rc-input')
  const send = $('rc-send')
  const thread = $('rc-runs')
  const empty = $('rc-empty')
  const refreshBtn = $('rc-refresh')

  let devices = []
  let selected = new Set(readSelected())
  const conversations = new Map()   // device id → conversation id on that device, for follow-ups
  let loading = null

  function readSelected() {
    try { return JSON.parse(localStorage.getItem(SELECTED_KEY) || '["self"]') } catch { return ['self'] }
  }
  function saveSelected() {
    try { localStorage.setItem(SELECTED_KEY, JSON.stringify([...selected])) } catch { /* per-viewer nicety only */ }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text != null) node.textContent = text
    return node
  }

  const timeNow = () => new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })

  async function errorMessage(response) {
    const body = await response.json().catch(() => ({}))
    const detail = body.detail
    if (detail?.message) return detail.message
    if (Array.isArray(detail)) return 'That task can’t be sent (check its length).'
    return `Something went wrong (${response.status}).`
  }

  // ── Devices ───────────────────────────────────────────────────────────────

  const OS_ICON = {
    phone: '<rect x="7" y="3" width="10" height="18" rx="2.2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M11 18h2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    laptop: '<rect x="4.5" y="5" width="15" height="10" rx="1.6" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M2.5 18.5h19" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    server: '<rect x="4" y="4" width="16" height="7" rx="1.6" stroke="currentColor" stroke-width="1.8" fill="none"/><rect x="4" y="13" width="16" height="7" rx="1.6" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M7.5 7.5h.01M7.5 16.5h.01" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',
    many: '<rect x="3" y="4.5" width="13" height="9.5" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M7 18h5M9.5 14v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><rect x="17.5" y="8" width="4" height="11" rx="1.3" stroke="currentColor" stroke-width="1.6" fill="none"/>',
  }
  function iconFor(os, size = 18) {
    const kind = os === 'many' ? 'many' : /ios|android/i.test(os) ? 'phone' : /linux/i.test(os) ? 'server' : 'laptop'
    return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">${OS_ICON[kind]}</svg>`
  }

  function statusText(d) {
    if (d.is_self) return 'This computer'
    if (d.controllable) return 'Ready'
    if (d.luna) return 'Doesn’t trust this account'
    return /ios|android/i.test(d.os) ? 'Phone · can’t run Luna tasks' : 'Luna isn’t running'
  }

  const targets = () => devices.filter(d => d.controllable && selected.has(d.id))

  function renderPicker() {
    const chosen = targets()
    pickerLabel.textContent = !chosen.length ? 'Pick a device' : chosen.length === 1 ? chosen[0].name : `${chosen.length} devices`
    pickerIcon.innerHTML = iconFor(chosen.length > 1 ? 'many' : chosen[0]?.os || 'windows', 18)
    pickerBtn.classList.toggle('is-empty', !chosen.length)
    input.placeholder = !chosen.length ? 'Pick a device first'
      : chosen.length === 1 ? `Tell ${chosen[0].name} what to do…` : `Tell ${chosen.length} devices what to do…`
    updateSend()
  }

  function renderDevices() {
    list.replaceChildren(...devices.map(d => {
      const option = el('button', 'rc-device')
      option.type = 'button'
      option.setAttribute('role', 'option')
      option.disabled = !d.controllable
      option.setAttribute('aria-selected', String(selected.has(d.id)))
      option.title = d.controllable ? (d.host || d.name) : d.reason
      const icon = el('span', 'rc-device-icon')
      icon.innerHTML = iconFor(d.os, 18)
      const text = el('span', 'rc-device-text')
      text.append(el('span', 'rc-device-name', d.name), el('span', 'rc-device-status', statusText(d)))
      const check = el('span', 'rc-check')
      check.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M6 12.5l4 4 8-9" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      option.append(icon, text, check)
      option.addEventListener('click', () => {
        if (selected.has(d.id)) selected.delete(d.id)
        else selected.add(d.id)
        saveSelected()
        option.setAttribute('aria-selected', String(selected.has(d.id)))
        renderPicker()
      })
      return option
    }))
    renderPicker()
  }

  function loadDevices(refresh = false) {
    if (loading) return loading
    refreshBtn.disabled = true
    refreshBtn.querySelector('span').textContent = 'Looking…'
    if (!devices.length) list.replaceChildren(el('p', 'rc-menu-empty', 'Looking for your devices…'))
    loading = (async () => {
      try {
        const response = await fetch(`${API}/api/remote/devices${refresh ? '?refresh=1' : ''}`)
        if (!response.ok) throw new Error(await errorMessage(response))
        const body = await response.json()
        devices = body.devices || []
        // Drop selections for devices that went away or can't take tasks any more.
        const usable = new Set(devices.filter(d => d.controllable).map(d => d.id))
        selected = new Set([...selected].filter(id => usable.has(id)))
        if (!selected.size && usable.has('self')) selected.add('self')
        saveSelected()
        const others = devices.filter(d => !d.is_self)
        notice.hidden = !body.tailscale && others.some(d => d.controllable)
        if (body.tailscale) notice.textContent = body.tailscale
        else if (!others.length) notice.textContent = 'No other devices are online on your tailnet.'
        else {
          notice.replaceChildren('To add a computer, start Luna on it with ',
            el('code', '', 'luna serve --tailscale'), ', signed in to Tailscale as you.')
        }
        renderDevices()
      } catch (error) {
        list.replaceChildren(el('p', 'rc-menu-empty is-error', error.message || 'Couldn’t load devices.'))
        renderPicker()
      } finally {
        loading = null
        refreshBtn.disabled = false
        refreshBtn.querySelector('span').textContent = 'Refresh devices'
      }
    })()
    return loading
  }

  function setMenu(open) {
    menu.hidden = !open
    pickerBtn.setAttribute('aria-expanded', String(open))
    if (open) loadDevices(false)
  }
  pickerBtn.addEventListener('click', () => setMenu(menu.hidden))
  document.addEventListener('click', event => {
    if (!menu.hidden && !event.target.closest('.rc-picker')) setMenu(false)
  })
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !menu.hidden) { setMenu(false); pickerBtn.focus() }
  })

  // ── Conversation ──────────────────────────────────────────────────────────

  function updateSend() {
    send.disabled = !targets().length || !input.value.trim()
  }

  function scrollToEnd() {
    const nearBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 160
    if (nearBottom) thread.scrollTop = thread.scrollHeight
  }

  function addUserMessage(message) {
    const row = el('div', 'msg-row msg-row-user')
    const bubble = el('div', 'bubble bubble-user')
    bubble.append(el('p', '', message))
    row.append(bubble)
    thread.append(row, el('p', 'msg-time msg-time-user rc-time-user', timeNow()))
  }

  function addDeviceBubble(device) {
    const row = el('div', 'msg-row msg-row-luna rc-msg')
    const avatar = el('span', 'avatar-luna rc-avatar')
    avatar.innerHTML = iconFor(device.os, 15)
    const bubble = el('div', 'bubble bubble-luna rc-bubble')
    const head = el('div', 'rc-bubble-head')
    const stop = el('button', 'rc-stop', 'Stop')
    stop.type = 'button'
    stop.addEventListener('click', () => row._abort?.abort())
    head.append(el('span', 'rc-bubble-name', device.name), el('span', 'rc-status'), el('span', 'rc-progress'), stop)
    const reply = el('div', 'md rc-reply')
    reply.hidden = true
    const err = el('p', 'rc-error')
    err.hidden = true
    const time = el('span', 'msg-time rc-time')
    bubble.append(head, reply, err, time)
    row.append(avatar, bubble)
    row._text = ''
    row._device = device
    thread.append(row)
    setStatus(row, 'working', 'Working')
    return row
  }

  function setStatus(row, state, label) {
    row.dataset.state = state
    row.querySelector('.rc-status').textContent = label
    row.querySelector('.rc-stop').hidden = state !== 'working' && state !== 'asking'
    if (state === 'done' || state === 'failed') row.querySelector('.rc-time').textContent = timeNow()
  }

  function setProgress(row, text) {
    row.querySelector('.rc-progress').textContent = text ? `· ${text}` : ''
  }

  function renderReply(row) {
    if (row._renderQueued) return
    row._renderQueued = true
    requestAnimationFrame(() => {
      row._renderQueued = false
      const reply = row.querySelector('.rc-reply')
      // Choice buttons the device attached (<!--luna-suggest:[{label, message}]-->), e.g. "which profile?".
      let text = row._text
      let choices = []
      const marker = text.match(SUGGEST_RE)
      if (marker) {
        try { choices = JSON.parse(marker[1]) } catch { choices = [] }
        text = text.replace(SUGGEST_RE, '')
      }
      text = text.trim()
      reply.hidden = !text
      if (typeof window.renderMarkdown === 'function') reply.innerHTML = window.renderMarkdown(text)
      else reply.textContent = text
      renderChoices(row, choices)
      scrollToEnd()
    })
  }

  const SUGGEST_RE = /<!--luna-suggest:([\s\S]*?)-->/

  // Answer buttons under a device's question; tapping one sends its message to that same device.
  function renderChoices(row, choices) {
    row.querySelector('.rc-choices')?.remove()
    const valid = (Array.isArray(choices) ? choices : [])
      .filter(c => c && typeof c.label === 'string' && typeof c.message === 'string').slice(0, 8)
    if (!valid.length) return
    const box = el('div', 'rc-choices')
    for (const choice of valid) {
      const button = el('button', 'rc-choice', choice.label)
      button.type = 'button'
      button.addEventListener('click', () => {
        box.querySelectorAll('button').forEach(b => { b.disabled = true })
        button.classList.add('is-picked')
        startTask(choice.message, [row._device])
      })
      box.append(button)
    }
    row.querySelector('.rc-error').before(box)
  }

  function askConfirmation(row, device, event) {
    const box = el('div', 'rc-confirm')
    box.dataset.confirmId = String(event.confirm_id || '')
    box.append(el('p', 'rc-confirm-text', event.message || `${device.name} wants to use ${event.tool}.`))
    const buttons = el('div', 'rc-confirm-actions')
    const allow = el('button', 'rc-confirm-btn is-primary', 'Allow')
    const deny = el('button', 'rc-confirm-btn', 'Deny')
    allow.type = deny.type = 'button'
    const answer = async approved => {
      allow.disabled = deny.disabled = true
      try {
        const response = await fetch(`${API}/api/remote/devices/${encodeURIComponent(device.id)}/confirm/${encodeURIComponent(event.confirm_id)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approved }),
        })
        if (!response.ok) throw new Error(await errorMessage(response))
        box.replaceChildren(el('p', 'rc-confirm-text is-answered', approved ? '✓ You allowed this.' : '✕ You said no.'))
        setStatus(row, 'working', 'Working')
      } catch (error) {
        box.replaceChildren(el('p', 'rc-confirm-text is-error', error.message))
      }
    }
    allow.addEventListener('click', () => answer(true))
    deny.addEventListener('click', () => answer(false))
    buttons.append(allow, deny)
    box.append(buttons)
    row.querySelector('.rc-reply').before(box)   // the question came first
    setStatus(row, 'asking', 'Needs your OK')
    scrollToEnd()
  }

  function handleEvent(row, device, event) {
    switch (event.type) {
      case 'meta':
        if (event.conversation_id) conversations.set(device.id, event.conversation_id)
        break
      case 'message_part': {
        // The device streams one paragraph per part without separators (same as the chat view).
        const part = event.content || ''
        const needsBreak = row._text && part && !/\n\s*$/.test(row._text) && !/^\s*\n/.test(part)
        row._text += needsBreak ? `\n\n${part}` : part
        renderReply(row)
        break
      }
      case 'plan':
        setProgress(row, `${event.total} steps`)
        break
      case 'plan_progress':
        setProgress(row, `step ${event.step} of ${event.total}`)
        break
      case 'plan_done':
        setProgress(row, '')
        break
      case 'coding_tool_call':
        setProgress(row, `using ${String(event.tool || 'a tool').replace(/_/g, ' ')}`)
        break
      case 'confirmation_required':
        askConfirmation(row, device, event)
        break
      case 'confirmation_resolved': {
        // Unanswered here: it timed out (or was answered on the device itself).
        const box = row.querySelector(`.rc-confirm[data-confirm-id="${CSS.escape(String(event.confirm_id || ''))}"]`)
        if (box && box.querySelector('button:not(:disabled)')) {
          box.replaceChildren(el('p', 'rc-confirm-text is-error',
            event.approved ? '✓ Allowed on the device.' : 'No answer in time, so it wasn’t done. Ask again when you’re ready.'))
          setStatus(row, 'working', 'Working')
        }
        break
      }
      case 'error': {
        row._error = event.message || 'Something went wrong.'
        if (event.kind) setStatus(row, 'failed', 'Failed')   // relay errors end the task
        const err = row.querySelector('.rc-error')
        err.textContent = row._error
        err.hidden = false
        scrollToEnd()
        break
      }
      case 'done': {
        if (event.conversation_id) conversations.set(device.id, event.conversation_id)
        setProgress(row, '')
        const failed = row._error && !row._text.trim()
        setStatus(row, failed ? 'failed' : 'done', failed ? 'Failed' : 'Done')
        break
      }
      default:
        break
    }
  }

  async function runOn(device, message, row) {
    const controller = new AbortController()
    row._abort = controller
    try {
      const response = await fetch(`${API}/api/remote/devices/${encodeURIComponent(device.id)}/task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, conversation_id: conversations.get(device.id) || null }),
        signal: controller.signal,
      })
      if (!response.ok) throw new Error(await errorMessage(response))
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let cut
        while ((cut = buffer.indexOf('\n\n')) >= 0) {
          const chunk = buffer.slice(0, cut)
          buffer = buffer.slice(cut + 2)
          for (const line of chunk.split('\n')) {
            if (!line.startsWith('data:')) continue
            try { handleEvent(row, device, JSON.parse(line.slice(5).trim())) } catch { /* skip a bad line */ }
          }
        }
      }
      if (row.dataset.state === 'working' || row.dataset.state === 'asking') setStatus(row, 'failed', 'Stopped')
    } catch (error) {
      if (error.name === 'AbortError') {
        setStatus(row, 'failed', 'Stopped')
        return
      }
      handleEvent(row, device, { type: 'error', kind: 'request', message: error.message || 'Couldn’t send the task.' })
    }
  }

  function startTask(message, only = null) {
    const chosen = only || targets()
    if (!chosen.length || !message) return
    empty.classList.add('is-hidden')
    addUserMessage(message)
    const rows = chosen.map(device => [device, addDeviceBubble(device)])
    thread.scrollTop = thread.scrollHeight
    rows.forEach(([device, row]) => runOn(device, message, row))
  }

  // ── Wiring ────────────────────────────────────────────────────────────────

  form.addEventListener('submit', event => {
    event.preventDefault()
    const message = input.value.trim()
    if (!message) return
    if (!targets().length) { setMenu(true); return }
    startTask(message)
    input.value = ''
    updateSend()
  })
  input.addEventListener('input', updateSend)
  $('rc-suggestions').addEventListener('click', event => {
    const chip = event.target.closest('.rc-suggestion')
    if (!chip) return
    input.value = chip.textContent
    if (targets().length) form.requestSubmit()
    else { updateSend(); setMenu(true) }
  })
  refreshBtn.addEventListener('click', () => loadDevices(true))
  $('rc-new-session').addEventListener('click', () => {
    conversations.clear()
    thread.querySelectorAll('.msg-row, .msg-time').forEach(node => node.remove())
    empty.classList.remove('is-hidden')
    input.focus()
  })

  window.loadRemoteView = () => {
    loadDevices(false).then(() => input.focus())
  }
})()

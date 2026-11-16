/**
 * Settings view — rendered from the backend's schema (/api/settings), so the
 * desktop app and the web UI share one source of truth. Secrets come back
 * masked and are only sent when you type a new value. Saving needs the local
 * access token, which the main process reads from Luna's data folder.
 */
'use strict'

;(function () {
  const API = window.electronAPI?.apiBase || 'http://127.0.0.1:8899'
  const form = document.getElementById('settings-form')
  const container = document.getElementById('settings-sections')
  const status = document.getElementById('settings-status')
  const saveBtn = document.getElementById('settings-save')
  const resetBtn = document.getElementById('settings-reset')
  if (!form || !container) return

  let fields = []
  let original = {}

  function setStatus(text, tone = '') {
    status.textContent = text
    status.className = `settings-status${tone ? ' is-' + tone : ''}`
  }

  function control(field) {
    if (field.type === 'toggle') {
      const wrap = document.createElement('label')
      wrap.className = 'settings-switch'
      const box = document.createElement('input')
      box.type = 'checkbox'
      box.role = 'switch'
      box.checked = field.value === true || String(field.value).toLowerCase() === 'true'
      box.id = `setting-${field.key}`
      box.dataset.key = field.key
      box.className = 'settings-input'
      box.addEventListener('change', refreshDirty)
      const track = document.createElement('span')
      track.className = 'settings-switch-track'
      track.setAttribute('aria-hidden', 'true')
      wrap.append(box, track)
      return wrap
    }
    let el
    if (field.type === 'select') {
      el = document.createElement('select')
      for (const option of field.options || []) {
        const opt = document.createElement('option')
        opt.value = option
        opt.textContent = option
        el.append(opt)
      }
      el.value = String(field.value ?? '')
    } else {
      el = document.createElement('input')
      el.type = field.type === 'number' ? 'number' : field.type === 'secret' ? 'password' : 'text'
      if (field.type === 'number') {
        if (field.min != null) el.min = field.min
        if (field.max != null) el.max = field.max
        if (field.step != null) el.step = field.step
      }
      if (field.type === 'secret') {
        el.placeholder = field.is_set ? `${field.masked} · leave blank to keep` : 'Not set'
        el.autocomplete = 'new-password'
      } else {
        el.value = String(field.value ?? '')
      }
    }
    el.id = `setting-${field.key}`
    el.dataset.key = field.key
    el.className = 'settings-input'
    el.addEventListener('input', refreshDirty)
    el.addEventListener('change', refreshDirty)
    return el
  }

  function render() {
    const sections = new Map()
    for (const field of fields) {
      if (!sections.has(field.section)) sections.set(field.section, [])
      sections.get(field.section).push(field)
    }
    const nodes = []
    for (const [name, items] of sections) {
      const section = document.createElement('section')
      section.className = 'settings-section'
      const heading = document.createElement('h2')
      heading.textContent = name
      section.append(heading)
      for (const field of items) {
        const row = document.createElement('div')
        row.className = 'settings-row'
        row.dataset.key = field.key
        const text = document.createElement('div')
        text.className = 'settings-text'
        const label = document.createElement('label')
        label.htmlFor = `setting-${field.key}`
        label.textContent = field.label
        text.append(label)
        if (field.help || field.restart) {
          const help = document.createElement('p')
          help.className = 'settings-help'
          help.textContent = [field.help, field.restart ? 'Takes effect after restarting Luna.' : ''].filter(Boolean).join(' ')
          text.append(help)
        }
        if (field.type === 'secret') {
          const badge = document.createElement('span')
          badge.className = `settings-badge${field.is_set ? ' is-set' : ''}`
          badge.textContent = field.is_set ? 'Set' : 'Not set'
          label.append(badge)
        }
        row.append(text, control(field))
        section.append(row)
      }
      nodes.push(section)
    }
    container.replaceChildren(...nodes)
    original = currentValues()
    refreshDirty()
  }

  function currentValues() {
    const values = {}
    container.querySelectorAll('.settings-input').forEach(el => {
      values[el.dataset.key] = el.type === 'checkbox' ? String(el.checked) : el.value
    })
    return values
  }

  function changes() {
    const now = currentValues()
    const out = {}
    for (const field of fields) {
      const value = now[field.key]
      if (field.type === 'secret') {
        if (value.trim()) out[field.key] = value.trim()
      } else if (value !== original[field.key]) {
        out[field.key] = value
      }
    }
    return out
  }

  function refreshDirty() {
    const dirty = changes()
    container.querySelectorAll('.settings-row').forEach(row => row.classList.toggle('is-dirty', row.dataset.key in dirty))
    const count = Object.keys(dirty).length
    saveBtn.disabled = count === 0
    resetBtn.disabled = count === 0
    if (count) setStatus(`${count} unsaved change${count === 1 ? '' : 's'}`)
    else if (!status.classList.contains('is-ok')) setStatus('')
  }

  async function load() {
    setStatus('')
    try {
      const response = await fetch(`${API}/api/settings`)
      if (!response.ok) throw new Error(`Settings returned ${response.status}`)
      fields = (await response.json()).fields || []
      render()
      // Let other parts of the UI (e.g. the personality panel) react to saved settings.
      window.dispatchEvent(new CustomEvent('luna:settings', {
        detail: Object.fromEntries(fields.map(field => [field.key, field.value])),
      }))
    } catch (error) {
      container.replaceChildren(Object.assign(document.createElement('p'), {
        className: 'settings-loading', textContent: 'Couldn’t load settings — is Luna’s backend running?',
      }))
      console.error('Could not load settings', error)
    }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault()
    const payload = changes()
    if (!Object.keys(payload).length) return
    saveBtn.disabled = true
    setStatus('Saving…')
    try {
      const put = token => fetch(`${API}/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Luna-Token': token },
        body: JSON.stringify(payload),
      })
      let response = await put((await window.electronAPI?.getLocalToken?.()) || '')
      // In a browser the token comes from the user (see web-shim.js); ask once and retry.
      if (response.status === 403 && window.electronAPI?.requestLocalToken) {
        const token = await window.electronAPI.requestLocalToken()
        if (token) response = await put(token)
      }
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || `Save failed (${response.status})`)
      await load()
      const restart = data.restart_required?.length ? ' Restart Luna for the Whisper model change.' : ''
      setStatus(`Saved.${restart}`, 'ok')
      setTimeout(() => { if (status.classList.contains('is-ok')) setStatus('') }, 5000)
    } catch (error) {
      setStatus(error.message, 'error')
      saveBtn.disabled = false
    }
  })

  resetBtn.addEventListener('click', () => { render(); setStatus('') })

  window.loadSettingsView = load
})()

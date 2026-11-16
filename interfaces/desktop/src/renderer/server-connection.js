/**
 * Settings → Server (desktop app only): run Luna's server on this computer, or
 * connect to one shared over Tailscale. Handled by the main process rather
 * than /api/settings so it still works when the remote server is down.
 */
'use strict'

;(function () {
  const host = window.electronAPI
  const section = document.getElementById('server-connection')
  if (!section || !host?.isElectron || !host.getServerConfig) return

  const mode = document.getElementById('server-mode')
  const url = document.getElementById('server-url')
  const token = document.getElementById('server-token')
  const badge = document.getElementById('server-mode-badge')
  const status = document.getElementById('server-status')
  const testBtn = document.getElementById('server-test')
  const saveBtn = document.getElementById('server-save')
  let saved = { mode: 'local', url: '', hasToken: false }

  function setStatus(text, tone = '') {
    status.textContent = text
    status.className = `settings-status${tone ? ' is-' + tone : ''}`
  }

  function isDirty() {
    if (mode.value !== saved.mode) return true
    if (mode.value === 'local') return false
    return url.value.trim().replace(/\/+$/, '') !== saved.url || Boolean(token.value.trim())
  }

  function refresh() {
    const remote = mode.value === 'remote'
    section.classList.toggle('is-local', !remote)
    testBtn.hidden = !remote
    saveBtn.disabled = !isDirty()
    token.placeholder = remote && saved.hasToken && url.value.trim().replace(/\/+$/, '') === saved.url
      ? 'Saved · leave blank to keep'
      : 'Paste the token'
  }

  async function load() {
    try {
      saved = await host.getServerConfig()
    } catch {
      saved = { mode: host.serverMode || 'local', url: '', hasToken: false }
    }
    mode.value = saved.mode
    url.value = saved.url || ''
    token.value = ''
    badge.textContent = saved.mode === 'remote' ? 'Remote' : 'Local'
    badge.classList.toggle('is-set', saved.mode === 'remote')
    section.hidden = false
    refresh()
  }

  testBtn.addEventListener('click', async () => {
    testBtn.disabled = true
    setStatus('Testing…')
    try {
      // A blank token field means "the saved one", which only the main process has.
      const typed = token.value.trim()
      const result = typed || !saved.hasToken
        ? await host.testServer(url.value, typed)
        : { ok: null, message: 'Paste the token to test it, or save to keep the current one.' }
      setStatus(result.message, result.ok === true ? 'ok' : result.ok === false ? 'error' : '')
    } catch (error) {
      setStatus(error.message || String(error), 'error')
    } finally {
      testBtn.disabled = false
    }
  })

  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true
    setStatus('Saving…')
    const result = await host.saveServer({ mode: mode.value, url: url.value, token: token.value })
    if (result?.ok) setStatus('Saved. Restarting Luna…', 'ok')
    else {
      setStatus(result?.message || 'Could not save.', 'error')
      refresh()
    }
  })

  for (const el of [mode, url, token]) {
    el.addEventListener('input', () => { setStatus(''); refresh() })
    el.addEventListener('change', refresh)
  }

  load()
})()

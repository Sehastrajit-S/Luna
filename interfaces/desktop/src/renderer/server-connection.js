/**
 * Settings → Server (desktop app only): run Luna's server on this computer, or
 * use one shared over Tailscale. Choosing Remote searches the tailnet for Luna
 * servers; your own devices are trusted by Tailscale identity, so connecting
 * is a click with nothing to paste. Handled by the main process rather than
 * /api/settings so it still works when the remote server is down.
 */
'use strict'

;(function () {
  const host = window.electronAPI
  const section = document.getElementById('server-connection')
  if (!section || !host?.isElectron || !host.getServerConfig) return

  const mode = document.getElementById('server-mode')
  const url = document.getElementById('server-url')
  const token = document.getElementById('server-token')
  const tokenRow = section.querySelector('.server-token-row')
  const badge = document.getElementById('server-mode-badge')
  const status = document.getElementById('server-status')
  const testBtn = document.getElementById('server-test')
  const saveBtn = document.getElementById('server-save')
  const foundStatus = document.getElementById('server-found-status')
  const foundList = document.getElementById('server-found-list')
  const rescanBtn = document.getElementById('server-rescan')

  let saved = { mode: 'local', url: '', hasToken: false }
  let found = []
  let searched = false

  const clean = value => String(value || '').trim().replace(/\/+$/, '')

  function setStatus(text, tone = '') {
    status.textContent = text
    status.className = `settings-status${tone ? ' is-' + tone : ''}`
  }

  function isDirty() {
    if (mode.value !== saved.mode) return mode.value === 'local' || Boolean(clean(url.value))
    if (mode.value === 'local') return false
    return clean(url.value) !== saved.url || Boolean(token.value.trim())
  }

  function selectedServer() {
    return found.find(s => s.url === clean(url.value))
  }

  function refresh() {
    const remote = mode.value === 'remote'
    section.classList.toggle('is-local', !remote)
    testBtn.hidden = !remote
    saveBtn.disabled = !isDirty()

    // The token is only for servers that don't trust this Tailscale account.
    const server = selectedServer()
    const sameAsSaved = clean(url.value) === saved.url
    tokenRow.hidden = !remote || (server ? server.authorized : !(sameAsSaved && saved.hasToken) && !token.value && !clean(url.value))
    token.placeholder = sameAsSaved && saved.hasToken ? 'Saved · leave blank to keep' : 'Paste the token'

    foundList.querySelectorAll('.server-option').forEach(el => el.classList.toggle('is-selected', el.dataset.url === clean(url.value)))
  }

  function option(server) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'server-option'
    btn.dataset.url = server.url
    btn.setAttribute('role', 'listitem')

    const text = document.createElement('span')
    const name = document.createElement('span')
    name.className = 'server-option-name'
    name.textContent = server.isSelf ? `${server.name} (this computer)` : server.name
    const hostLine = document.createElement('span')
    hostLine.className = 'server-option-host'
    hostLine.textContent = server.url
    text.append(name, hostLine)

    const tag = document.createElement('span')
    tag.className = `settings-badge ${server.authorized ? 'is-set' : 'is-warn'}`
    tag.textContent = server.authorized ? 'Trusted' : 'Needs token'

    btn.append(text, tag)
    btn.addEventListener('click', () => choose(server))
    return btn
  }

  function choose(server) {
    url.value = server.url
    if (server.authorized) token.value = ''
    setStatus(server.authorized
      ? `${server.name} trusts your Tailscale account. Save and restart to connect.`
      : `${server.name} needs its access token.`, server.authorized ? 'ok' : '')
    refresh()
    if (!server.authorized) token.focus()
  }

  async function search() {
    rescanBtn.disabled = true
    foundStatus.textContent = 'Looking for Luna on your tailnet…'
    foundList.replaceChildren()
    let result
    try {
      result = await host.discoverServers()
    } catch (error) {
      result = { error: error.message || String(error), servers: [] }
    }
    searched = true
    rescanBtn.disabled = false
    found = result.servers || []

    if (result.error) {
      foundStatus.textContent = result.error
    } else if (!found.length) {
      foundStatus.textContent = 'No shared Luna found. On the computer running Luna, run `npm run serve:tailscale`, then search again.'
    } else {
      foundStatus.textContent = found.length === 1 ? 'Found 1 Luna server on your tailnet:' : `Found ${found.length} Luna servers on your tailnet:`
      foundList.replaceChildren(...found.map(option))
      // Nothing chosen yet and exactly one trusted server elsewhere: pick it.
      const trusted = found.filter(s => s.authorized && !s.isSelf)
      if (!clean(url.value) && trusted.length === 1) choose(trusted[0])
    }
    refresh()
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
    if (saved.mode === 'remote') search()
  }

  mode.addEventListener('change', () => {
    setStatus('')
    refresh()
    if (mode.value === 'remote' && !searched) search()
  })

  rescanBtn.addEventListener('click', search)

  testBtn.addEventListener('click', async () => {
    testBtn.disabled = true
    setStatus('Testing…')
    try {
      const result = await host.testServer(url.value, token.value.trim())
      setStatus(result.message, result.ok ? 'ok' : 'error')
      if (!result.ok && /token/i.test(result.message)) { tokenRow.hidden = false }
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

  for (const el of [url, token]) {
    el.addEventListener('input', () => { setStatus(''); refresh() })
  }

  load()
})()

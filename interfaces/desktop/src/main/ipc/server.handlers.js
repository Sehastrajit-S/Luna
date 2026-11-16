'use strict'

const fs = require('fs')
const path = require('path')
const { ipcMain, app } = require('electron')
const IPC = require('../../shared/ipc-channels')
const connectionStore = require('../services/connection-store')
const logger = require('../services/logger')

const TEST_TIMEOUT_MS = 8000

function readLocalToken(envPath) {
  try {
    return fs.readFileSync(path.join(path.dirname(envPath), 'data', 'local_api_token'), 'utf8').trim()
  } catch {
    return '' // the local server writes it on first start
  }
}

/** The token the renderer should send: the remote one, or this machine's. */
function currentToken(envPath) {
  const config = connectionStore.load()
  return config.mode === 'remote' ? config.token : readLocalToken(envPath)
}

async function probe(url, token) {
  const base = connectionStore.normaliseUrl(url)
  const problem = connectionStore.validate({ mode: 'remote', url: base, token: String(token || '').trim() })
  if (problem) return { ok: false, message: problem }

  const get = (route, headers = {}) => fetch(`${base}${route}`, { headers, signal: AbortSignal.timeout(TEST_TIMEOUT_MS) })
  try {
    const health = await get('/api/system/health')
    if (!health.ok) return { ok: false, message: `Server answered ${health.status}. Is that a Luna server?` }
  } catch (error) {
    const reason = error?.name === 'TimeoutError' ? 'timed out' : error?.cause?.code || error?.message || 'unreachable'
    return { ok: false, message: `Can't reach ${base} (${reason}). Check the URL and that this computer is on the same tailnet.` }
  }
  // Health is public; settings needs the token, so it proves the token works.
  try {
    const authed = await get('/api/settings', { 'X-Luna-Token': String(token).trim() })
    if (authed.status === 401 || authed.status === 403) return { ok: false, message: 'Server reached, but it rejected the access token.' }
    if (!authed.ok) return { ok: false, message: `Server reached, but settings returned ${authed.status}.` }
  } catch (error) {
    return { ok: false, message: `Server reached, but the token check failed: ${error?.message || error}` }
  }
  return { ok: true, message: 'Connected. The token works.' }
}

function registerServerHandlers({ envPath }) {
  // Synchronous so the preload can hand the renderer its API base before any script runs.
  ipcMain.on(IPC.server.connection, event => {
    const config = connectionStore.load()
    event.returnValue = {
      mode: config.mode,
      apiBase: connectionStore.apiBase(config),
      token: currentToken(envPath),
    }
  })

  ipcMain.handle(IPC.server.getConfig, () => {
    const config = connectionStore.load()
    return { mode: config.mode, url: config.url, hasToken: Boolean(config.token) }
  })

  ipcMain.handle(IPC.server.test, (_event, { url, token } = {}) => probe(url, token))

  // Switching servers restarts the app: the local server is started (or not)
  // at launch, and every window's API base is fixed when it loads.
  ipcMain.handle(IPC.server.save, (_event, input = {}) => {
    const previous = connectionStore.load()
    const next = {
      mode: input.mode,
      url: input.url,
      // Leaving the token blank keeps the saved one for the same server.
      token: String(input.token || '').trim()
        || (previous.mode === 'remote' && previous.url === connectionStore.normaliseUrl(input.url) ? previous.token : ''),
    }
    try {
      const saved = connectionStore.save(next)
      logger.info(`Server connection set to ${saved.mode}${saved.mode === 'remote' ? ` (${saved.url})` : ''}; restarting`)
      setTimeout(() => { app.relaunch(); app.quit() }, 300)
      return { ok: true }
    } catch (error) {
      return { ok: false, message: error.message }
    }
  })
}

module.exports = { registerServerHandlers, currentToken, readLocalToken }

/**
 * Where the desktop app's Luna server lives.
 *
 *   local   start Luna's server on this computer (default)
 *   remote  connect to a Luna server elsewhere, e.g. shared with
 *           `luna serve --tailscale` at https://<pc>.<tailnet>.ts.net:8899
 *
 * Saved in userData/connection.json, not in the server's .env, so it can be
 * changed while the remote server is unreachable.
 */
'use strict'

const fs = require('fs')
const path = require('path')
const { app } = require('electron')

const LOCAL_API_BASE = 'http://127.0.0.1:8899'
const DEFAULTS = Object.freeze({ mode: 'local', url: '', token: '' })

function filePath() {
  return path.join(app.getPath('userData'), 'connection.json')
}

function normaliseUrl(raw) {
  let url = String(raw || '').trim().replace(/\/+$/, '')
  if (url && !/^https?:\/\//i.test(url)) url = `https://${url}`
  return url
}

/** Returns an error message, or '' when the config is usable. */
function validate(config) {
  if (config.mode === 'local') return ''
  if (config.mode !== 'remote') return 'Choose local or remote.'
  let parsed
  try {
    parsed = new URL(config.url)
  } catch {
    return 'Enter the server URL, e.g. https://my-pc.tailnet.ts.net:8899'
  }
  if (!/^https?:$/.test(parsed.protocol)) return 'The server URL must start with https:// or http://'
  if (!config.token) return 'Paste the access token printed by `luna serve --tailscale`.'
  return ''
}

function load() {
  try {
    const saved = JSON.parse(fs.readFileSync(filePath(), 'utf8'))
    const config = {
      mode: saved.mode === 'remote' ? 'remote' : 'local',
      url: normaliseUrl(saved.url),
      token: String(saved.token || '').trim(),
    }
    // A half-filled remote config would leave the app with no server at all.
    return validate(config) ? { ...DEFAULTS } : config
  } catch {
    return { ...DEFAULTS }
  }
}

function save(input) {
  const config = {
    mode: input?.mode === 'remote' ? 'remote' : 'local',
    url: normaliseUrl(input?.url),
    token: String(input?.token || '').trim(),
  }
  const problem = validate(config)
  if (problem) throw new Error(problem)
  fs.mkdirSync(path.dirname(filePath()), { recursive: true })
  fs.writeFileSync(filePath(), JSON.stringify(config, null, 2), { encoding: 'utf8', mode: 0o600 })
  return config
}

function apiBase(config = load()) {
  return config.mode === 'remote' ? config.url : LOCAL_API_BASE
}

module.exports = { load, save, validate, normaliseUrl, apiBase, LOCAL_API_BASE }

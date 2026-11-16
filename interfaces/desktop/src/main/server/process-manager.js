/**
 * Owns the lifecycle of the backend subprocess: spawn it, watch its health,
 * restart it with backoff if it dies, and make sure it's actually gone when
 * the app quits. Nothing else in the main process should call `spawn`
 * directly on the backend binary — go through this module so there's one
 * place that knows the process's real state.
 */
'use strict'

const fs = require('fs')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')
const net = require('net')
const logger = require('../services/logger')

const HOST = '127.0.0.1'
const PORT = 8899
const HEALTH_URL = `http://${HOST}:${PORT}/api/system/health`
const HEALTH_INTERVAL_MS = 10_000
const STARTUP_GRACE_MS = 60_000
const MAX_HEALTH_FAILURES = 3
const MAX_RESTARTS = 5
const RESTART_DELAY_MS = [1000, 2000, 4000, 8000, 16000]

let child = null
let spawnOpts = null
let spawnedAt = 0
let restarts = 0
let healthFailures = 0
let healthTimer = null
let intentionalShutdown = false

// /health does real work (~2-3s), so give it room before calling it a failure.
function probeHealth(timeout = 10_000) {
  return new Promise(resolve => {
    const req = http.get(HEALTH_URL, { timeout }, res => {
      res.resume()
      resolve(res.statusCode === 200)
    })
    req.on('timeout', () => req.destroy())
    req.on('error', () => resolve(false))
  })
}

function portInUse() {
  return new Promise(resolve => {
    const sock = net.connect({ host: HOST, port: PORT })
    sock.setTimeout(1000)
    sock.once('connect', () => { sock.destroy(); resolve(true) })
    sock.once('timeout', () => { sock.destroy(); resolve(false) })
    sock.once('error', () => resolve(false))
  })
}

// Prefer the repo's virtualenv so `npm start` works from any shell, not only
// one where the venv happens to be activated.
function resolvePython(cwd) {
  const venvPython = process.platform === 'win32'
    ? path.join(cwd, '.venv', 'Scripts', 'python.exe')
    : path.join(cwd, '.venv', 'bin', 'python')
  if (fs.existsSync(venvPython)) return venvPython
  return process.platform === 'win32' ? 'python' : 'python3'
}

async function healthCheck() {
  if (intentionalShutdown || !child) return
  if (Date.now() - spawnedAt < STARTUP_GRACE_MS) return
  if (await probeHealth()) {
    healthFailures = 0
    restarts = 0
    return
  }
  healthFailures += 1
  logger.warn(`Backend health check failed (${healthFailures}/${MAX_HEALTH_FAILURES})`)
  if (healthFailures >= MAX_HEALTH_FAILURES && child) {
    logger.warn('Backend unresponsive — killing so it restarts')
    // The 'exit' handler schedules the restart.
    try { child.kill() } catch { /* already gone */ }
  }
}

function launch() {
  const { cwd, pythonBin, scriptPath, env } = spawnOpts
  logger.info(`Starting backend: ${pythonBin} ${scriptPath}`)
  spawnedAt = Date.now()
  healthFailures = 0
  child = spawn(pythonBin, [scriptPath], {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, ...env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
    windowsHide: true,
  })

  child.stdout.on('data', d => logger.info(`[backend] ${d.toString().trim()}`))
  child.stderr.on('data', d => logger.info(`[backend] ${d.toString().trim()}`))

  child.on('error', err => {
    logger.error(`Backend failed to start (${pythonBin}): ${err.message}`)
  })

  child.on('exit', code => {
    child = null
    if (intentionalShutdown) return
    logger.error(`Backend exited unexpectedly (code ${code})`)
    restart()
  })

  if (!healthTimer) {
    healthTimer = setInterval(healthCheck, HEALTH_INTERVAL_MS)
  }
}

async function spawnBackend({ cwd, pythonBin, scriptPath, env = {} }) {
  intentionalShutdown = false
  spawnOpts = { cwd, pythonBin: pythonBin || resolvePython(cwd), scriptPath, env }

  // A backend started elsewhere (`luna backend`, `npm run web`) already owns
  // the port; a second one would just fail to bind and crash-loop.
  if (await portInUse()) {
    logger.info(`Port ${PORT} already in use — assuming a Luna backend is running and reusing it`)
    return
  }
  launch()
}

function restart() {
  if (intentionalShutdown || !spawnOpts) return
  if (restarts >= MAX_RESTARTS) {
    logger.error(`Backend crashed ${MAX_RESTARTS} times — giving up on auto-restart.`)
    return
  }
  const delay = RESTART_DELAY_MS[Math.min(restarts, RESTART_DELAY_MS.length - 1)]
  restarts += 1
  setTimeout(() => {
    if (!intentionalShutdown && !child) launch()
  }, delay)
}

function shutdown() {
  intentionalShutdown = true
  if (healthTimer) clearInterval(healthTimer)
  healthTimer = null
  if (child) {
    const pid = child.pid
    // On Windows child.kill() only ends python.exe, not anything it spawned
    // (uvicorn workers, MCP servers) — take down the whole tree.
    if (process.platform === 'win32' && pid) {
      try { spawn('taskkill', ['/pid', String(pid), '/T', '/F'], { windowsHide: true }) } catch { /* ignore */ }
    } else {
      try { child.kill() } catch { /* already gone */ }
    }
    child = null
  }
}

function isRunning() {
  return child !== null
}

module.exports = { spawnBackend, shutdown, isRunning, portInUse }

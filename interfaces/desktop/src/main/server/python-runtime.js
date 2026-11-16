/**
 * Gives the installed app a working Python for the server, with no setup by the user.
 *
 * Installed builds ship `uv` (resources/uv/<platform>-<arch>/uv). On first launch
 * it downloads a private Python and installs server/requirements.txt into
 * userData/python. A stamp file records the requirements hash, so later
 * launches skip straight to starting the server, and an app update that changes
 * the requirements reinstalls only what changed.
 *
 * Running from source keeps the old behavior: the repo's .venv, else system Python.
 */
'use strict'

const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const { spawn } = require('child_process')
const { app } = require('electron')
const logger = require('../services/logger')

const PYTHON_VERSION = '3.12'
const IS_WIN = process.platform === 'win32'

function sourcePython(root) {
  const venvPython = IS_WIN
    ? path.join(root, '.venv', 'Scripts', 'python.exe')
    : path.join(root, '.venv', 'bin', 'python')
  if (fs.existsSync(venvPython)) return venvPython
  return IS_WIN ? 'python' : 'python3'
}

function uvBinary() {
  const dir = `${process.platform}-${process.arch}`
  const bin = path.join(process.resourcesPath, 'uv', dir, IS_WIN ? 'uv.exe' : 'uv')
  return fs.existsSync(bin) ? bin : null
}

function paths() {
  const base = app.getPath('userData')
  const venv = path.join(base, 'python')
  return {
    venv,
    python: IS_WIN ? path.join(venv, 'Scripts', 'python.exe') : path.join(venv, 'bin', 'python'),
    stamp: path.join(venv, '.luna-stamp.json'),
    uvEnv: {
      UV_PYTHON_INSTALL_DIR: path.join(base, 'uv-python'),
      UV_CACHE_DIR: path.join(base, 'uv-cache'),
      UV_NO_CONFIG: '1',
      UV_PYTHON_PREFERENCE: 'only-managed',
    },
  }
}

function requirementsHash(requirements) {
  return crypto.createHash('sha256').update(fs.readFileSync(requirements)).digest('hex').slice(0, 16)
}

function readStamp(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) } catch { return null }
}

/** Run uv, streaming each output line to onLine. Resolves on exit code 0. */
function runUv(uv, args, env, onLine) {
  return new Promise((resolve, reject) => {
    logger.info(`uv ${args.join(' ')}`)
    const proc = spawn(uv, args, { env: { ...process.env, ...env }, windowsHide: true })
    let tail = ''
    const handle = chunk => {
      for (const line of chunk.toString().split(/\r?\n|\r/)) {
        const text = line.trim()
        if (!text) continue
        tail = text
        logger.info(`[uv] ${text}`)
        onLine(text)
      }
    }
    proc.stdout.on('data', handle)
    proc.stderr.on('data', handle)
    proc.on('error', reject)
    proc.on('exit', code => (code === 0 ? resolve() : reject(new Error(tail || `uv exited with code ${code}`))))
  })
}

/**
 * Returns the Python executable the server should use.
 * onProgress({ step, total, title, detail }) is called while installing; it never
 * fires when everything is already in place.
 */
async function ensurePython({ root, requirements, onProgress = () => {} }) {
  if (!app.isPackaged) return sourcePython(root)

  const uv = uvBinary()
  if (!uv) {
    logger.warn('uv is not bundled with this build; falling back to the system Python')
    return sourcePython(root)
  }

  const p = paths()
  const hash = requirementsHash(requirements)
  const stamp = readStamp(p.stamp)
  if (stamp && stamp.requirements === hash && fs.existsSync(p.python)) return p.python

  const total = 2
  if (!fs.existsSync(p.python)) {
    onProgress({ step: 1, total, title: 'Downloading Python', detail: 'One-time setup. This takes a minute.' })
    await runUv(uv, ['venv', '--python', PYTHON_VERSION, '--seed', p.venv], p.uvEnv,
      line => onProgress({ step: 1, total, title: 'Downloading Python', detail: line }))
  }

  onProgress({ step: 2, total, title: 'Installing Luna', detail: 'Downloading the AI and speech libraries.' })
  await runUv(uv, ['pip', 'install', '--python', p.python, '-r', requirements], p.uvEnv,
    line => onProgress({ step: 2, total, title: 'Installing Luna', detail: line }))

  fs.writeFileSync(p.stamp, JSON.stringify({ requirements: hash, app: app.getVersion(), at: new Date().toISOString() }))
  return p.python
}

module.exports = { ensurePython }

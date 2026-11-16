/**
 * Main-process logger — console in dev, console + rotating-by-restart file
 * in production. Deliberately tiny: this is the one thing that must never
 * throw, since a logger that crashes takes the crash report with it.
 */
'use strict'

const fs = require('fs')
const path = require('path')
const { app } = require('electron')

const LOG_DIR = path.join(app.getPath('userData'), 'logs')
const LOG_FILE = path.join(LOG_DIR, 'desktop.log')

let ready = false
function ensureLogDir() {
  if (ready) return
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true })
    ready = true
  } catch {
    // If we can't create the log dir, fall back to console-only silently —
    // logging must never be the reason the app fails to start.
  }
}

function write(level, message) {
  const line = `[${new Date().toISOString()}] [${level}] ${message}`
  console.log(line)
  if (!ready) ensureLogDir()
  try {
    fs.appendFileSync(LOG_FILE, line + '\n')
  } catch {
    // Disk full, permissions issue, etc. — console output above already
    // happened, so nothing is silently lost from the user's perspective.
  }
}

module.exports = {
  info: msg => write('INFO', msg),
  warn: msg => write('WARN', msg),
  error: msg => write('ERROR', msg),
  LOG_FILE,
}

/**
 * Small frameless window shown during the one-time Python setup on first launch.
 * Created lazily, so launches that need no setup never see it. It has no preload:
 * the main process pushes progress with executeJavaScript, and the Retry link
 * navigates to luna-setup://retry, which the main process intercepts.
 */
'use strict'

const path = require('path')
const { BrowserWindow } = require('electron')

let win = null
let pending = null
let onRetry = null

function ensureWindow() {
  if (win && !win.isDestroyed()) return win
  win = new BrowserWindow({
    width: 460,
    height: 380,
    frame: false,
    resizable: false,
    show: false,
    backgroundColor: '#09090f',
    title: 'Setting up Luna',
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  })
  win.webContents.on('will-navigate', (event, url) => {
    event.preventDefault()
    if (url.startsWith('luna-setup://retry') && onRetry) onRetry()
  })
  win.once('ready-to-show', () => win.show())
  win.webContents.once('did-finish-load', () => {
    if (pending) push(pending)
  })
  win.loadFile(path.join(__dirname, '..', '..', 'setup', 'setup.html'))
  return win
}

function push(state) {
  pending = state
  if (!win || win.isDestroyed() || win.webContents.isLoading()) return
  win.webContents.executeJavaScript(`window.lunaSetup && window.lunaSetup(${JSON.stringify(state)})`).catch(() => {})
}

function showProgress(state) {
  ensureWindow()
  push({ ...state, error: false })
}

function showError(message, retry) {
  onRetry = retry
  ensureWindow()
  push({ error: true, title: "Luna couldn't finish setting up", detail: message })
}

function close() {
  if (win && !win.isDestroyed()) win.close()
  win = null
  pending = null
}

module.exports = { showProgress, showError, close }

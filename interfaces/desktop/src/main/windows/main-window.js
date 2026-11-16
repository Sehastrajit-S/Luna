'use strict'

const path = require('path')
const { BrowserWindow, shell } = require('electron')

function createMainWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    backgroundColor: '#09090f',
    webPreferences: {
      preload: path.join(__dirname, '..', '..', 'preload', 'main-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  win.once('ready-to-show', () => win.show())

  // Links in chat replies belong in the system browser; the app window must
  // never navigate away from its own UI or spawn child windows.
  const openExternally = url => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url)
  }
  win.webContents.setWindowOpenHandler(({ url }) => {
    openExternally(url)
    return { action: 'deny' }
  })
  win.webContents.on('will-navigate', (event, url) => {
    if (url.startsWith('file://')) return
    event.preventDefault()
    openExternally(url)
  })

  win.on('maximize', () => win.webContents.send('window:maximized', true))
  win.on('unmaximize', () => win.webContents.send('window:maximized', false))
  win.on('enter-full-screen', () => win.webContents.send('window:fullscreen-changed', true))
  win.on('leave-full-screen', () => win.webContents.send('window:fullscreen-changed', false))

  // Static UI scaffold for now (no chat/backend wiring yet) — swap this for
  // the real interfaces/web/dist build once this shell is ready to go live.
  win.loadFile(path.join(__dirname, '..', '..', 'renderer', 'index.html'))

  return win
}

module.exports = { createMainWindow }

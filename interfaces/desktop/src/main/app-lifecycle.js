/**
 * Electron app-level lifecycle events, kept separate from index.js so the
 * entry point reads as "wire the pieces together" rather than being where
 * event-handling logic itself lives.
 */
'use strict'

const { app, BrowserWindow } = require('electron')
const backend = require('./backend/process-manager')
const trayService = require('./services/tray-service')
const windowRegistry = require('./windows/window-registry')
const { createMainWindow } = require('./windows/main-window')
const logger = require('./services/logger')

function enforceSingleInstance() {
  const gotLock = app.requestSingleInstanceLock()
  if (!gotLock) {
    app.quit()
    return false
  }
  app.on('second-instance', () => {
    const win = windowRegistry.get('main')
    if (win) {
      if (win.isMinimized()) win.restore()
      win.show()
      win.focus()
    }
  })
  return true
}

function wireLifecycle() {
  app.on('window-all-closed', () => {
    // Windows/Linux: quit when the last window closes. macOS keeps the app
    // (and tray) alive with no windows open, per platform convention.
    if (process.platform !== 'darwin') app.quit()
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      const win = createMainWindow()
      windowRegistry.register('main', win)
    }
  })

  app.on('before-quit', () => {
    logger.info('App quitting — shutting down backend and tray')
    backend.shutdown()
    trayService.destroyTray()
  })
}

module.exports = { enforceSingleInstance, wireLifecycle }

/**
 * Main-process entry point.
 *
 * This file should only ever WIRE modules together — window creation, IPC
 * handling, backend lifecycle, and the updater all live in their own files.
 * If you're tempted to add real logic here, it almost certainly belongs in
 * one of ./windows, ./ipc, ./services, or ./backend instead.
 */
'use strict'

const path = require('path')
const { app } = require('electron')

// Running from the repo: keep Chromium caches and logs in the repo's data/
// folder instead of %APPDATA%. Must run before anything reads userData
// (the logger resolves its directory at require time).
if (!app.isPackaged) {
  app.setPath('userData', path.join(__dirname, '..', '..', '..', 'data', 'desktop-app'))
}

const logger = require('./services/logger')
const { enforceSingleInstance, wireLifecycle } = require('./app-lifecycle')
const backend = require('./backend/process-manager')
const windowRegistry = require('./windows/window-registry')
const { createMainWindow } = require('./windows/main-window')
const IPC = require('../shared/ipc-channels')
const { registerAllHandlers } = require('./ipc')
const { buildAppMenu } = require('./menu')
const trayService = require('./services/tray-service')
const updaterService = require('./services/updater-service')

const ROOT = path.join(__dirname, '..', '..', '..')
const ENV_PATH = path.join(ROOT, '.env')

if (!enforceSingleInstance()) {
  // Another instance already owns the lock — this process exits immediately
  // (enforceSingleInstance already called app.quit()).
} else {
  app.whenReady().then(() => {
    logger.info('App ready — starting backend and creating main window')

    backend.spawnBackend({
      cwd: ROOT,
      scriptPath: path.join(ROOT, 'backend', 'server.py'),
    })

    const mainWindow = createMainWindow()
    windowRegistry.register('main', mainWindow)

    // Settings live inside the main window (backend-driven /api/settings).
    const openSettings = () => {
      const win = windowRegistry.get('main')
      if (!win) return
      if (win.isMinimized()) win.restore()
      win.show()
      win.focus()
      win.webContents.send(IPC.system.showSettings)
    }

    registerAllHandlers({
      getMainWindow: () => windowRegistry.get('main'),
      envPath: ENV_PATH,
      openSettings,
    })

    buildAppMenu({ openSettings })
    trayService.createTray(() => windowRegistry.get('main'))
    updaterService.init(mainWindow)

    wireLifecycle()
  })
}

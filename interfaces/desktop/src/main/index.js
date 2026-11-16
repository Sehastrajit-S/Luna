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
  app.setPath('userData', path.join(__dirname, '..', '..', '..', '..', 'data', 'desktop-app'))
}

const logger = require('./services/logger')
const { enforceSingleInstance, wireLifecycle } = require('./app-lifecycle')
const backend = require('./server/process-manager')
const windowRegistry = require('./windows/window-registry')
const { createMainWindow } = require('./windows/main-window')
const IPC = require('../shared/ipc-channels')
const { registerAllHandlers } = require('./ipc')
const { buildAppMenu } = require('./menu')
const trayService = require('./services/tray-service')
const updaterService = require('./services/updater-service')
const connectionStore = require('./services/connection-store')

const { ensurePython } = require('./server/python-runtime')
const { resolveDataPaths } = require('./server/data-paths')
const setupWindow = require('./windows/setup-window')

// From source: the repo root (interfaces/desktop/src/main → 4 levels up).
// Installed: electron-builder copies server/ into the resources folder.
const ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..', '..', '..', '..')
const { dataDir: DATA_DIR, envFile: ENV_PATH } = resolveDataPaths(ROOT)

/**
 * Get a Python with Luna's packages (installing it on first launch), then start
 * the local server. Resolves once the server process is launched; on failure the
 * setup window shows the error with a Retry button, and this resolves after a retry works.
 */
function startLocalServer() {
  return new Promise(resolve => {
    const attempt = async () => {
      try {
        // A server started elsewhere (`npm run web`, Docker) already owns the port: reuse it.
        if (await backend.portInUse()) {
          logger.info('Port 8899 is in use; reusing the Luna server that is already running')
        } else {
          const pythonBin = await ensurePython({
            root: ROOT,
            requirements: path.join(ROOT, 'server', 'requirements.txt'),
            onProgress: state => setupWindow.showProgress(state),
          })
          await backend.spawnBackend({
            cwd: ROOT,
            pythonBin,
            scriptPath: path.join(ROOT, 'server', 'server.py'),
            env: { LUNA_DATA_DIR: DATA_DIR, LUNA_ENV_FILE: ENV_PATH },
          })
        }
        resolve()
      } catch (error) {
        logger.error(`Local server setup failed: ${error.message}`)
        setupWindow.showError(
          `${error.message}\n\nCheck your internet connection for the one-time download, then try again.`,
          attempt,
        )
      }
    }
    attempt()
  })
}

if (!enforceSingleInstance()) {
  // Another instance already owns the lock — this process exits immediately
  // (enforceSingleInstance already called app.quit()).
} else {
  app.whenReady().then(async () => {
    const connection = connectionStore.load()
    if (connection.mode === 'remote') {
      logger.info(`App ready — using remote server ${connection.url}`)
    } else {
      logger.info('App ready — starting local server and creating main window')
      await startLocalServer()
    }

    const mainWindow = createMainWindow()
    windowRegistry.register('main', mainWindow)
    // Close the first-run setup window only once the main window exists, so the
    // app never has zero windows (which would quit it).
    mainWindow.once('ready-to-show', () => setupWindow.close())

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
      dataDir: DATA_DIR,
      openSettings,
    })

    buildAppMenu({ openSettings })
    trayService.createTray(() => windowRegistry.get('main'))
    updaterService.init(mainWindow)

    wireLifecycle()
  })
}

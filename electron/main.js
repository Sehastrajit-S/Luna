'use strict'

const {
  app, BrowserWindow, ipcMain, screen, clipboard,
  Notification, Tray, Menu, nativeImage, shell, globalShortcut, session,
} = require('electron')
const { spawn } = require('child_process')
const path    = require('path')
const http    = require('http')
const fs      = require('fs')
const {
  envPath,
  envForBackend,
  needsFirstRunConfig,
  openSettingsWindow,
  waitForSettingsClosed,
  readEnv,
  writeEnv,
} = require('./settings')
let autoUpdater = null
try {
  autoUpdater = require('electron-updater').autoUpdater
} catch {}

const isDev = !app.isPackaged
const ROOT  = isDev ? path.join(__dirname, '..') : process.resourcesPath
const isE2ESmoke = process.argv.includes('--e2e-smoke')
if (isE2ESmoke) {
  app.setPath('userData', path.join(ROOT, 'data', 'electron-e2e-user-data'))
}
const USER_DATA = app.getPath('userData')
const startHidden = process.argv.includes('--hidden')

let mainWindow     = null
let tray           = null
let backendProcess = null
let isQuitting     = false
let awayWindows    = []
let _backendRestarts = 0
let _healthTimer     = null

// ── Single instance ────────────────────────────────────────────────────────────
if (!app.requestSingleInstanceLock()) {
  app.quit()
  process.exit(0)
}
app.on('second-instance', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.show()
    mainWindow.focus()
  }
})

// ── Backend process manager ────────────────────────────────────────────────────
const BACKEND_URL   = 'http://127.0.0.1:8899'
const PID_FILE      = path.join(USER_DATA, 'data', 'backend.pid')
const ENV_FILE      = envPath(app, ROOT, isDev)
const DATA_DIR      = isDev ? path.join(ROOT, 'data') : path.join(USER_DATA, 'data')
const LOG_DIR       = path.join(USER_DATA, 'logs')
const MAX_RESTARTS  = 5
const RESTART_DELAY = [1000, 2000, 4000, 8000, 16000]  // exponential backoff
const HEALTH_INTERVAL = 10_000  // check every 10 s
fs.mkdirSync(DATA_DIR, { recursive: true })
fs.mkdirSync(LOG_DIR, { recursive: true })

function logLine(line) {
  const text = `[${new Date().toISOString()}] ${line}\n`
  try { fs.appendFileSync(path.join(LOG_DIR, 'luna.log'), text) } catch {}
  console.log(line)
}

function backendLogLine(line) {
  const text = `[${new Date().toISOString()}] ${line}\n`
  try { fs.appendFileSync(path.join(LOG_DIR, 'backend.log'), text) } catch {}
}

function healthCheck() {
  return new Promise(resolve => {
    const req = http.get(`${BACKEND_URL}/api/system/health`, res => {
      res.resume()
      resolve(res.statusCode < 500)
    })
    req.setTimeout(1500, () => { req.destroy(); resolve(false) })
    req.on('error', () => resolve(false))
    req.end()
  })
}

function waitForBackend(maxMs = 30_000) {
  return new Promise(resolve => {
    const start = Date.now()
    const ping = () => {
      const req = http.get(`${BACKEND_URL}/api/system/health`, res => {
        res.resume()
        if (res.statusCode < 500) { resolve(true); return }
        retry()
      })
      req.on('error', retry)
      req.end()
    }
    const retry = () => {
      if (Date.now() - start >= maxMs) { resolve(false); return }
      setTimeout(ping, 400)
    }
    ping()
  })
}

function _execAsync(cmd) {
  const { exec } = require('child_process')
  return new Promise(resolve => exec(cmd, () => resolve()))
}

function _isPidAlive(pid) {
  const { execSync } = require('child_process')
  try {
    if (process.platform === 'win32') {
      const out = execSync(`tasklist /FI "PID eq ${pid}" /NH 2>nul`, { encoding: 'utf8' })
      return out.includes(String(pid))
    } else {
      execSync(`kill -0 ${pid}`)
      return true
    }
  } catch {
    return false
  }
}

async function killStaleBackend() {
  // 1. PID file (most targeted — kills exactly our previous process)
  if (fs.existsSync(PID_FILE)) {
    const raw = fs.readFileSync(PID_FILE, 'utf8').trim()
    const pid = parseInt(raw, 10)
    if (pid > 0 && _isPidAlive(pid)) {
      console.log(`[Luna] Stopping stale backend (PID ${pid})`)
      if (process.platform === 'win32') {
        await _execAsync(`taskkill /F /PID ${pid}`)
      } else {
        try { process.kill(pid, 'SIGTERM') } catch {}
        await new Promise(r => setTimeout(r, 2000))
        if (_isPidAlive(pid)) { try { process.kill(pid, 'SIGKILL') } catch {} }
      }
    }
    try { fs.unlinkSync(PID_FILE) } catch {}
    await new Promise(r => setTimeout(r, 300))
  }

  // 2. Port scan fallback — catches crashes where PID file wasn't written
  if (process.platform === 'win32') {
    const { exec } = require('child_process')
    await new Promise(resolve => {
      exec('netstat -ano | findstr :8899', (err, stdout) => {
        if (err || !stdout) { resolve(); return }
        const pids = new Set()
        for (const line of stdout.trim().split('\n')) {
          const parts = line.trim().split(/\s+/)
          const pid = parts[parts.length - 1]
          if (/^\d+$/.test(pid) && pid !== '0') pids.add(pid)
        }
        if (!pids.size) { resolve(); return }
        let done = 0
        for (const pid of pids) {
          exec(`taskkill /F /PID ${pid}`, () => { if (++done === pids.size) setTimeout(resolve, 300) })
        }
      })
    })
  }
}

function spawnBackend() {
  const packagedBackend = process.platform === 'win32'
    ? path.join(ROOT, 'backend-bin', 'luna-backend.exe')
    : path.join(ROOT, 'backend-bin', 'luna-backend')
  const script = path.join(ROOT, 'backend', 'server.py')
  const usePackagedBackend = !isDev && fs.existsSync(packagedBackend)
  const python = process.platform === 'win32' ? 'python' : 'python3'
  const runtimeEnv = envForBackend(ENV_FILE)

  const proc = spawn(usePackagedBackend ? packagedBackend : python, usePackagedBackend ? [] : [script], {
    cwd: ROOT,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      ...runtimeEnv,
      LUNA_ENV_FILE: ENV_FILE,
      LUNA_DATA_DIR: DATA_DIR,
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
    },
    windowsHide: true,
  })

  proc.stdout.on('data', d => {
    const text = String(d)
    backendLogLine(text.trimEnd())
    process.stdout.write('[api] ' + text)
  })
  proc.stderr.on('data', d => {
    const text = String(d)
    backendLogLine(text.trimEnd())
    process.stderr.write('[api] ' + text)
  })

  proc.on('exit', (code, signal) => {
    if (isQuitting) return
    const delay = RESTART_DELAY[Math.min(_backendRestarts, RESTART_DELAY.length - 1)]
    _backendRestarts++
    if (_backendRestarts > MAX_RESTARTS) {
      logLine(`[Luna] Backend crashed ${_backendRestarts} times - giving up`)
      return
    }
    logLine(`[Luna] Backend exited (code=${code} signal=${signal}) - restarting in ${delay}ms (attempt ${_backendRestarts}/${MAX_RESTARTS})`)
    setTimeout(() => {
      backendProcess = spawnBackend()
    }, delay)
  })

  return proc
}

async function startBackend() {
  await killStaleBackend()
  _backendRestarts = 0
  backendProcess = spawnBackend()
}

function startHealthMonitor() {
  if (_healthTimer) clearInterval(_healthTimer)
  _healthTimer = setInterval(async () => {
    if (isQuitting || !backendProcess) return
    const ok = await healthCheck()
    if (!ok) {
      logLine('[Luna] Health check failed - backend may be unresponsive')
      // The exit handler on spawnBackend will auto-restart on crash.
      // If the process is hung (not exited), nudge it.
      if (backendProcess && !backendProcess.killed) {
        if (process.platform === 'win32') {
          _execAsync(`taskkill /F /PID ${backendProcess.pid}`)
        } else {
          try { backendProcess.kill('SIGKILL') } catch {}
        }
      }
    }
  }, HEALTH_INTERVAL)
}

// ── Window ─────────────────────────────────────────────────────────────────────
function loadBackendErrorWindow(reason = 'Backend did not start') {
  if (!mainWindow || mainWindow.isDestroyed()) return
  const logPath = path.join(LOG_DIR, 'backend.log')
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    *{box-sizing:border-box} body{margin:0;background:#09090f;color:#eef2ff;font-family:Segoe UI,Arial,sans-serif}
    .wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:32px}
    .panel{width:min(680px,100%);border:1px solid #303049;background:#12121c;border-radius:10px;padding:28px}
    h1{font-size:22px;margin:0 0 10px} p{color:#a1a1aa;line-height:1.5}
    code{display:block;background:#09090f;border:1px solid #27273a;border-radius:8px;padding:12px;color:#c4b5fd;word-break:break-all}
  </style></head><body><div class="wrap"><div class="panel">
    <h1>Luna could not start the local backend</h1>
    <p>${reason}</p>
    <p>Check the backend log here:</p>
    <code>${logPath}</code>
    <p>For this installer build, Python and Luna's backend Python dependencies must be installed on this PC.</p>
  </div></div></body></html>`
  mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`)
  if (!startHidden) mainWindow.show()
}

async function createWindow() {
  const iconPath = path.join(__dirname, 'assets', 'icon.png')

  mainWindow = new BrowserWindow({
    width: 1100,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#09090f',
    frame: false,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: false,      // allow YouTube iframes + cross-origin requests
      allowRunningInsecureContent: false,
    },
  })

  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    logLine(`[renderer:${level}] ${message} (${sourceId}:${line})`)
  })
  mainWindow.webContents.on('did-fail-load', (_event, code, description, url) => {
    logLine(`[renderer] did-fail-load ${code} ${description} ${url}`)
  })
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    logLine(`[renderer] process gone ${JSON.stringify(details)}`)
  })

  mainWindow.on('maximize',   () => mainWindow.webContents.send('window:maximized', true))
  mainWindow.on('unmaximize', () => mainWindow.webContents.send('window:maximized', false))

  console.log('[Luna] Waiting for backend...')
  const ready = await waitForBackend(90_000)
  if (!ready) {
    logLine('[Luna] Backend failed to start within 90s')
    loadBackendErrorWindow('The local API did not become ready within 90 seconds.')
    return
  }
  console.log('[Luna] Backend ready.')
  startHealthMonitor()

  if (isDev) {
    await mainWindow.loadURL('http://localhost:5173')
  } else {
    await mainWindow.loadFile(path.join(ROOT, 'frontend', 'dist', 'index.html'))
  }

  if (!startHidden) {
    mainWindow.show()
  }

  if (isE2ESmoke) {
    logLine('[Luna] E2E smoke startup complete')
    setTimeout(() => {
      isQuitting = true
      app.quit()
    }, 1000)
  }

  mainWindow.on('close', e => {
    if (!isQuitting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })
}

// ── Tray ───────────────────────────────────────────────────────────────────────
function createTray() {
  const trayIconPath = path.join(__dirname, 'assets', 'tray.png')
  const trayIcon = fs.existsSync(trayIconPath)
    ? nativeImage.createFromPath(trayIconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty()

  tray = new Tray(trayIcon)
  tray.setToolTip('Luna')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open Luna',  click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { label: 'Settings',   click: () => openSettingsWindow({ BrowserWindow, ipcMain, app, root: ROOT, isDev, parent: mainWindow, mode: 'settings' }) },
    { label: 'Check for Updates', click: () => checkForUpdates() },
    { type: 'separator' },
    { label: 'Quit Luna',  click: () => { isQuitting = true; app.quit() } },
  ]))
  tray.on('click', () => { mainWindow?.show(); mainWindow?.focus() })
}

function showMainWindow() {
  if (!mainWindow) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
}

// ── IPC ────────────────────────────────────────────────────────────────────────
function setupAutoUpdater() {
  if (isDev || !autoUpdater) return
  const updateYml = path.join(process.resourcesPath, 'app-update.yml')
  if (!fs.existsSync(updateYml)) return  // zip/portable build — no updater
  autoUpdater.autoDownload = true
  autoUpdater.on('checking-for-update', () => logLine('[update] checking for update'))
  autoUpdater.on('update-available', info => {
    logLine(`[update] available ${info?.version || ''}`)
    mainWindow?.webContents.send('update:status', { status: 'available', version: info?.version || '' })
  })
  autoUpdater.on('update-not-available', () => {
    logLine('[update] not available')
    mainWindow?.webContents.send('update:status', { status: 'not-available' })
  })
  autoUpdater.on('error', error => {
    logLine(`[update] error ${error?.message || error}`)
    mainWindow?.webContents.send('update:status', { status: 'error', message: String(error?.message || error) })
  })
  autoUpdater.on('update-downloaded', info => {
    logLine(`[update] downloaded ${info?.version || ''}`)
    mainWindow?.webContents.send('update:status', { status: 'downloaded', version: info?.version || '' })
    if (Notification.isSupported()) {
      new Notification({
        title: 'Luna update ready',
        body: 'Restart Luna to install the update.',
      }).show()
    }
  })
}

function checkForUpdates() {
  if (isDev || !autoUpdater) {
    return Promise.resolve({ ok: false, reason: 'updates unavailable in development' })
  }
  const updateYml = path.join(process.resourcesPath, 'app-update.yml')
  if (!fs.existsSync(updateYml)) {
    return Promise.resolve({ ok: false, reason: 'no update config (portable build)' })
  }
  return autoUpdater.checkForUpdatesAndNotify()
    .then(() => ({ ok: true }))
    .catch(error => ({ ok: false, error: String(error?.message || error) }))
}

function installDownloadedUpdate() {
  if (!autoUpdater) return
  isQuitting = true
  autoUpdater.quitAndInstall(false, true)
}

function registerIPC() {
  ipcMain.handle('window:minimize',     () => mainWindow?.minimize())
  ipcMain.handle('window:maximize',     () => {
    mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize()
  })
  ipcMain.handle('window:fullscreen',   () => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    const next = !mainWindow.isFullScreen()
    mainWindow.setFullScreen(next)
    mainWindow.webContents.send('window:fullscreen-changed', next)
  })
  ipcMain.handle('window:is-fullscreen', () => mainWindow?.isFullScreen() ?? false)
  ipcMain.handle('window:close',        () => { if (!isQuitting) mainWindow?.hide() })
  ipcMain.handle('app:quit',            () => { isQuitting = true; app.quit() })
  ipcMain.handle('window:is-maximized', () => mainWindow?.isMaximized() ?? false)
  ipcMain.handle('clipboard:write', (_, text) => { clipboard.writeText(String(text)) })
  ipcMain.handle('settings:open', () => {
    openSettingsWindow({ BrowserWindow, ipcMain, app, root: ROOT, isDev, parent: mainWindow, mode: 'settings' })
  })
  ipcMain.handle('env:get', () => {
    try { return { ok: true, config: readEnv(ENV_FILE) } }
    catch (e) { return { ok: false, error: String(e) } }
  })
  ipcMain.handle('env:save', (_, config) => {
    try {
      writeEnv(ENV_FILE, config || {})
      // Tell the running backend to reload its settings from the updated .env
      const reloadReq = http.request('http://127.0.0.1:8899/api/system/config/reload', { method: 'POST' }, res => res.resume())
      reloadReq.on('error', () => {})
      reloadReq.end()
      return { ok: true }
    } catch (e) { return { ok: false, error: String(e) } }
  })
  ipcMain.handle('update:check', () => checkForUpdates())
  ipcMain.handle('update:install', () => installDownloadedUpdate())

  ipcMain.handle('away:enter', () => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    // F11-style fullscreen on main window
    mainWindow.setFullScreen(true)
    mainWindow.webContents.send('window:fullscreen-changed', true)

    // Create a dark clock overlay on every other display
    const displays = screen.getAllDisplays()
    const mainBounds = mainWindow.getBounds()
    for (const display of displays) {
      const { x, y, width, height } = display.bounds
      // Skip the display the main window is on
      if (x === mainBounds.x || (x <= mainBounds.x && x + width > mainBounds.x)) continue
      const overlayHtml = `<!DOCTYPE html><html><head><style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{background:#02020a;display:flex;flex-direction:column;align-items:center;
          justify-content:center;height:100vh;font-family:monospace;color:rgba(255,255,255,0.78)}
        #clock{font-size:12vw;font-weight:100;letter-spacing:-0.03em;line-height:1}
        #sec{font-size:0.42em;color:rgba(255,255,255,0.3)}
        #date{font-size:11px;letter-spacing:0.22em;text-transform:uppercase;
          color:rgba(255,255,255,0.22);margin-top:20px}
      </style></head><body>
        <div id="clock"><span id="hm">--:--</span><span id="sec">:--</span></div>
        <div id="date"></div>
        <script>
          function tick(){
            const n=new Date()
            const pad=v=>String(v).padStart(2,'0')
            document.getElementById('hm').textContent=pad(n.getHours())+':'+pad(n.getMinutes())
            document.getElementById('sec').textContent=':'+pad(n.getSeconds())
            document.getElementById('date').textContent=n.toLocaleDateString('en-US',
              {weekday:'long',month:'long',day:'numeric'})
          }
          tick(); setInterval(tick,1000)
        </script>
      </body></html>`
      const win = new BrowserWindow({
        x, y, width, height,
        frame: false, transparent: false, alwaysOnTop: true,
        skipTaskbar: true, focusable: false,
        webPreferences: { nodeIntegration: false, contextIsolation: true },
      })
      win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(overlayHtml)}`)
      win.setFullScreen(true)
      awayWindows.push(win)
    }
  })

  ipcMain.handle('away:exit', () => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    mainWindow.setFullScreen(false)
    mainWindow.webContents.send('window:fullscreen-changed', false)
    for (const win of awayWindows) {
      if (!win.isDestroyed()) win.close()
    }
    awayWindows = []
  })

  ipcMain.handle('notify', (_, { title, body }) => {
    if (Notification.isSupported()) new Notification({ title, body }).show()
  })

  ipcMain.handle('open-url', (_, url) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url)
  })

  ipcMain.handle('location:get', () => {
    return fetch('https://ipapi.co/json/')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        const lat = Number(data?.latitude)
        const lon = Number(data?.longitude)
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
          return { lat: null, lon: null, accuracy: null }
        }
        return { lat, lon, accuracy: null }
      })
      .catch(() => ({ lat: null, lon: null, accuracy: null }))
  })

  // Spotify OAuth — opens a popup, intercepts the redirect, forwards code to backend
  ipcMain.handle('spotify:open-auth', async (_, authUrl) => {
    return new Promise(resolve => {
      const win = new BrowserWindow({
        width: 480, height: 680,
        title: 'Connect Spotify',
        parent: mainWindow,
        webPreferences: { nodeIntegration: false, contextIsolation: true },
      })
      win.setMenuBarVisibility(false)
      win.loadURL(authUrl)

      const intercept = (event, url) => {
        if (!url.includes('/api/spotify/callback')) return
        event.preventDefault()
        try {
          const code = new URL(url).searchParams.get('code')
          if (code) {
            http.get(
              `http://127.0.0.1:8899/api/spotify/callback?code=${encodeURIComponent(code)}`,
              res => { res.resume(); mainWindow?.webContents.send('spotify:connected') }
            ).on('error', err => console.error('[Luna] Spotify callback error:', err))
          }
        } catch (e) { console.error('[Luna] Spotify intercept error:', e) }
        win.close()
        resolve(null)
      }

      win.webContents.on('will-redirect', intercept)
      win.webContents.on('will-navigate', intercept)
      win.on('closed', () => resolve(null))
    })
  })
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  const _ALLOWED_PERMISSIONS = new Set(['geolocation', 'media'])
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    callback(_ALLOWED_PERMISSIONS.has(permission))
  })
  session.defaultSession.setPermissionCheckHandler((_webContents, permission) => {
    return _ALLOWED_PERMISSIONS.has(permission)
  })
  // Spoof as Chrome so YouTube embedded player works (Electron UA triggers Error 153)
  session.defaultSession.setUserAgent(
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
  )

  if (!isDev) {
    app.setLoginItemSettings({
      openAtLogin: true,
      path: process.execPath,
      args: ['--hidden'],
    })
  }
  registerIPC()
  setupAutoUpdater()
  if (needsFirstRunConfig(ENV_FILE)) {
    const setupWin = openSettingsWindow({ BrowserWindow, ipcMain, app, root: ROOT, isDev, mode: 'first-run' })
    await waitForSettingsClosed(setupWin)
    if (needsFirstRunConfig(ENV_FILE)) {
      app.quit()
      return
    }
  }
  await startBackend()
  createWindow()
  createTray()
  globalShortcut.register('Control+Alt+L', showMainWindow)
  if (!isDev) setTimeout(() => checkForUpdates(), 15_000)
})

app.on('activate', () => { mainWindow?.show(); mainWindow?.focus() })
app.on('window-all-closed', () => { /* stay alive in tray */ })

app.on('before-quit', () => {
  isQuitting = true
  globalShortcut.unregisterAll()
  if (_healthTimer) { clearInterval(_healthTimer); _healthTimer = null }
  if (backendProcess && !backendProcess.killed) {
    if (process.platform === 'win32') {
      _execAsync(`taskkill /F /PID ${backendProcess.pid}`)
    } else {
      backendProcess.kill('SIGTERM')
    }
    backendProcess = null
  }
  try { if (fs.existsSync(PID_FILE)) fs.unlinkSync(PID_FILE) } catch {}
})

/**
 * Preload for the main application window. Runs in an isolated context with
 * Node access but no direct access to the renderer's `window` — only what's
 * explicitly exposed via contextBridge crosses that boundary. Never expose
 * `ipcRenderer` itself; expose named functions that invoke specific channels.
 */
'use strict'

const { contextBridge, ipcRenderer } = require('electron')

// Sandboxed preloads can only require('electron') — requiring
// ../shared/ipc-channels threw, so the whole bridge (window controls, opening
// links) silently never loaded. The names are copied from that file;
// tests/tools/test_desktop_ipc.py fails if they drift apart.
const IPC = {
  window: {
    minimize: 'window:minimize',
    maximize: 'window:maximize',
    close: 'window:close',
    isMaximized: 'window:is-maximized',
    toggleFullscreen: 'window:fullscreen',
    isFullscreen: 'window:is-fullscreen',
    maximizedChanged: 'window:maximized',
    fullscreenChanged: 'window:fullscreen-changed',
  },
  updater: {
    check: 'update:check',
    install: 'update:install',
    status: 'update:status',
  },
  system: {
    notify: 'system:notify',
    openUrl: 'system:open-url',
    copyText: 'system:clipboard-write',
    openSettings: 'system:open-settings',
    localToken: 'system:local-token',
    showSettings: 'system:show-settings',
    quit: 'system:quit',
  },
  server: {
    connection: 'server:connection',
    getConfig: 'server:get-config',
    test: 'server:test',
    save: 'server:save',
  },
}

// Local server or a remote one (Settings → Server). Fetched synchronously so
// every renderer script sees the right API base from its first line.
let connection = {}
try { connection = ipcRenderer.sendSync(IPC.server.connection) || {} } catch { /* fall back to local */ }

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  apiBase: connection.apiBase || 'http://127.0.0.1:8899',
  apiToken: connection.token || '',
  serverMode: connection.mode === 'remote' ? 'remote' : 'local',
  getServerConfig: () => ipcRenderer.invoke(IPC.server.getConfig),
  testServer: (url, token) => ipcRenderer.invoke(IPC.server.test, { url, token }),
  saveServer: config => ipcRenderer.invoke(IPC.server.save, config),

  // Window controls
  minimize: () => ipcRenderer.invoke(IPC.window.minimize),
  maximize: () => ipcRenderer.invoke(IPC.window.maximize),
  close: () => ipcRenderer.invoke(IPC.window.close),
  isMaximized: () => ipcRenderer.invoke(IPC.window.isMaximized),
  toggleFullscreen: () => ipcRenderer.invoke(IPC.window.toggleFullscreen),
  isFullscreen: () => ipcRenderer.invoke(IPC.window.isFullscreen),
  onMaximizeChange: cb => {
    const handler = (_event, val) => cb(val)
    ipcRenderer.on(IPC.window.maximizedChanged, handler)
    return () => ipcRenderer.removeListener(IPC.window.maximizedChanged, handler)
  },
  onFullscreenChange: cb => {
    const handler = (_event, val) => cb(val)
    ipcRenderer.on(IPC.window.fullscreenChanged, handler)
    return () => ipcRenderer.removeListener(IPC.window.fullscreenChanged, handler)
  },

  // System
  notify: (title, body) => ipcRenderer.invoke(IPC.system.notify, { title, body }),
  openUrl: url => ipcRenderer.invoke(IPC.system.openUrl, url),
  copyText: text => ipcRenderer.invoke(IPC.system.copyText, text),
  openSettings: () => ipcRenderer.invoke(IPC.system.openSettings),
  getLocalToken: () => ipcRenderer.invoke(IPC.system.localToken),
  onShowSettings: cb => {
    const handler = () => cb()
    ipcRenderer.on(IPC.system.showSettings, handler)
    return () => ipcRenderer.removeListener(IPC.system.showSettings, handler)
  },
  quit: () => ipcRenderer.invoke(IPC.system.quit),

  // Updater
  checkForUpdates: () => ipcRenderer.invoke(IPC.updater.check),
  installUpdate: () => ipcRenderer.invoke(IPC.updater.install),
  onUpdateStatus: cb => {
    const handler = (_event, status) => cb(status)
    ipcRenderer.on(IPC.updater.status, handler)
    return () => ipcRenderer.removeListener(IPC.updater.status, handler)
  },
})

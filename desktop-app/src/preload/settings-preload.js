/**
 * Preload for the settings window — a deliberately smaller API surface than
 * main-preload.js. The settings window only ever needs env read/write; it
 * has no business calling window controls or the updater, so those
 * channels simply aren't exposed here even though the main process
 * registers them globally.
 */
'use strict'

const { contextBridge, ipcRenderer } = require('electron')

// Sandboxed preloads can only require('electron'); names copied from
// ../shared/ipc-channels.js (kept in sync by utilities/tests/tools/test_desktop_ipc.py).
const IPC = {
  env: {
    get: 'env:get',
    save: 'env:save',
  },
}

contextBridge.exposeInMainWorld('settingsAPI', {
  getEnvConfig: () => ipcRenderer.invoke(IPC.env.get),
  saveEnvConfig: config => ipcRenderer.invoke(IPC.env.save, config),
})

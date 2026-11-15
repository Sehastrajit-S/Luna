'use strict'

const { ipcMain } = require('electron')
const IPC = require('../../shared/ipc-channels')
const envStore = require('../services/env-store')

function registerEnvHandlers(envPath) {
  ipcMain.handle(IPC.env.get, () => {
    try {
      return { ok: true, config: envStore.readEnv(envPath) }
    } catch (e) {
      return { ok: false, error: String(e.message || e) }
    }
  })

  ipcMain.handle(IPC.env.save, (_event, next) => {
    try {
      const config = envStore.writeEnv(envPath, next || {})
      return { ok: true, config }
    } catch (e) {
      return { ok: false, error: String(e.message || e) }
    }
  })
}

module.exports = { registerEnvHandlers }

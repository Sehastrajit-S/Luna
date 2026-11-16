'use strict'

const { ipcMain } = require('electron')
const IPC = require('../../shared/ipc-channels')
const updaterService = require('../services/updater-service')

function registerUpdaterHandlers() {
  ipcMain.handle(IPC.updater.check, () => updaterService.checkForUpdates())
  ipcMain.handle(IPC.updater.install, () => updaterService.installDownloadedUpdate())
}

module.exports = { registerUpdaterHandlers }

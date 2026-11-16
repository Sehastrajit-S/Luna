/**
 * Wraps electron-updater. Every consumer goes through this module instead
 * of importing autoUpdater directly, so status events always reach every
 * open window the same way.
 */
'use strict'

const { autoUpdater } = require('electron-updater')
const logger = require('./logger')

let mainWindow = null
let checked = false

function broadcast(channel, status) {
  const IPC = require('../../shared/ipc-channels')
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(IPC.updater.status, status)
  }
}

function init(win) {
  mainWindow = win
  autoUpdater.autoDownload = false

  autoUpdater.on('update-available', info => broadcast('status', { state: 'available', version: info.version }))
  autoUpdater.on('update-not-available', () => broadcast('status', { state: 'none' }))
  autoUpdater.on('download-progress', p => broadcast('status', { state: 'downloading', percent: p.percent }))
  autoUpdater.on('update-downloaded', () => broadcast('status', { state: 'ready' }))
  autoUpdater.on('error', err => {
    logger.error(`Updater error: ${err.message}`)
    broadcast('status', { state: 'error', message: err.message })
  })
}

async function checkForUpdates() {
  checked = true
  try {
    const result = await autoUpdater.checkForUpdates()
    return { ok: true, version: result?.updateInfo?.version ?? null }
  } catch (e) {
    return { ok: false, error: e.message }
  }
}

async function installDownloadedUpdate() {
  if (!checked) return { ok: false, error: 'No update has been checked for yet.' }
  autoUpdater.quitAndInstall()
  return { ok: true }
}

module.exports = { init, checkForUpdates, installDownloadedUpdate }

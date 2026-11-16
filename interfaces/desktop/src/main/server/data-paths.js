/**
 * Where the local server keeps its data and settings.
 *
 * From source: the repo's data/ folder and .env, as before.
 * Installed: the user's app-data folder (userData/server-data and userData/luna.env),
 * so app updates, which replace the install folder, never touch chats, memory or settings.
 * Builds up to 0.2.0 kept them inside the install folder; the first launch of a
 * newer version moves them over.
 */
'use strict'

const fs = require('fs')
const path = require('path')
const { app } = require('electron')
const logger = require('../services/logger')

function resolveDataPaths(root) {
  if (!app.isPackaged) {
    return { dataDir: path.join(root, 'data'), envFile: path.join(root, '.env') }
  }
  const base = app.getPath('userData')
  const dataDir = path.join(base, 'server-data')
  const envFile = path.join(base, 'luna.env')
  migrateLegacy(root, dataDir, envFile)
  fs.mkdirSync(dataDir, { recursive: true })
  return { dataDir, envFile }
}

function migrateLegacy(root, dataDir, envFile) {
  const oldData = path.join(root, 'data')
  const oldEnv = path.join(root, '.env')
  try {
    if (!fs.existsSync(dataDir) && fs.existsSync(oldData)) {
      fs.cpSync(oldData, dataDir, { recursive: true })
      logger.info(`Moved server data from ${oldData} to ${dataDir}`)
    }
    if (!fs.existsSync(envFile) && fs.existsSync(oldEnv)) {
      fs.copyFileSync(oldEnv, envFile)
      logger.info(`Moved settings from ${oldEnv} to ${envFile}`)
    }
  } catch (error) {
    logger.error(`Could not move data from the install folder: ${error.message}`)
  }
}

module.exports = { resolveDataPaths }

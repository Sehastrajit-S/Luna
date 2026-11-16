/**
 * Registers every IPC handler module in one place. Main-process entry code
 * calls registerAllHandlers(deps) exactly once at startup — nothing else
 * should call ipcMain.handle directly outside the handler modules below.
 */
'use strict'

const { registerWindowHandlers } = require('./window.handlers')
const { registerEnvHandlers } = require('./env.handlers')
const { registerUpdaterHandlers } = require('./updater.handlers')
const { registerSystemHandlers } = require('./system.handlers')
const { registerServerHandlers, setServerDataDir } = require('./server.handlers')

function registerAllHandlers({ getMainWindow, envPath, dataDir, openSettings }) {
  if (dataDir) setServerDataDir(dataDir)
  registerWindowHandlers(getMainWindow)
  registerEnvHandlers(envPath)
  registerUpdaterHandlers()
  registerSystemHandlers({ openSettings, envPath })
  registerServerHandlers({ envPath })
}

module.exports = { registerAllHandlers }

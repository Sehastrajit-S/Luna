'use strict'

const { ipcMain } = require('electron')
const IPC = require('../../shared/ipc-channels')

function registerWindowHandlers(getMainWindow) {
  ipcMain.handle(IPC.window.minimize, () => getMainWindow()?.minimize())
  ipcMain.handle(IPC.window.maximize, () => {
    const win = getMainWindow()
    if (!win) return
    win.isMaximized() ? win.unmaximize() : win.maximize()
  })
  ipcMain.handle(IPC.window.close, () => getMainWindow()?.hide())
  ipcMain.handle(IPC.window.isMaximized, () => getMainWindow()?.isMaximized() ?? false)
  ipcMain.handle(IPC.window.toggleFullscreen, () => {
    const win = getMainWindow()
    if (!win) return
    const next = !win.isFullScreen()
    win.setFullScreen(next)
    win.webContents.send(IPC.window.fullscreenChanged, next)
  })
  ipcMain.handle(IPC.window.isFullscreen, () => getMainWindow()?.isFullScreen() ?? false)
}

module.exports = { registerWindowHandlers }

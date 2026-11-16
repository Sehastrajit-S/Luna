'use strict'

const { ipcMain, Notification, shell, clipboard, app } = require('electron')
const IPC = require('../../shared/ipc-channels')
const { currentToken } = require('./server.handlers')

function registerSystemHandlers({ openSettings, envPath }) {
  // The local server writes data/local_api_token next to .env; handing it to
  // our own renderer lets the settings page save, while web pages that can
  // reach localhost still can't (they can't read this file). When connected
  // to a remote server this is that server's token instead.
  ipcMain.handle(IPC.system.localToken, () => currentToken(envPath))

  ipcMain.handle(IPC.system.notify, (_event, { title, body }) => {
    new Notification({ title, body }).show()
  })

  ipcMain.handle(IPC.system.openUrl, (_event, url) => {
    // Only ever hand the OS-level opener a URL, never a raw shell command —
    // shell.openExternal on user- or renderer-controlled strings that
    // *aren't* URLs is a classic sandbox-escape vector.
    if (typeof url === 'string' && /^https?:\/\//i.test(url)) {
      shell.openExternal(url)
    }
  })

  ipcMain.handle(IPC.system.copyText, (_event, text) => {
    clipboard.writeText(String(text ?? ''))
  })

  ipcMain.handle(IPC.system.openSettings, () => openSettings())

  ipcMain.handle(IPC.system.quit, () => app.quit())
}

module.exports = { registerSystemHandlers }

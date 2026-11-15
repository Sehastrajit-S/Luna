'use strict'

const { ipcMain, Notification, shell, clipboard, app } = require('electron')
const IPC = require('../../shared/ipc-channels')

function registerSystemHandlers({ openSettings, envPath }) {
  // The backend writes data/local_api_token next to .env; handing it to our
  // own renderer lets the settings page save, while web pages that can reach
  // localhost still can't (they can't read this file).
  ipcMain.handle(IPC.system.localToken, () => {
    try {
      const tokenPath = require('path').join(require('path').dirname(envPath), 'data', 'local_api_token')
      return require('fs').readFileSync(tokenPath, 'utf8').trim()
    } catch {
      return ''
    }
  })

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

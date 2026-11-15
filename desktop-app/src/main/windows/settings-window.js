'use strict'

const path = require('path')
const { BrowserWindow } = require('electron')

function createSettingsWindow(parent) {
  const win = new BrowserWindow({
    width: 720,
    height: 640,
    parent,
    modal: false,
    resizable: true,
    backgroundColor: '#0d0d16',
    webPreferences: {
      preload: path.join(__dirname, '..', '..', 'preload', 'settings-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  win.setMenuBarVisibility(false)
  win.loadFile(path.join(__dirname, '..', '..', '..', 'resources', 'settings.html'))

  return win
}

module.exports = { createSettingsWindow }

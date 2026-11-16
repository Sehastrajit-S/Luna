/**
 * System tray icon + context menu. Kept separate from window creation so
 * the tray survives independently of whichever windows are open/closed.
 */
'use strict'

const fs = require('fs')
const path = require('path')
const { Tray, Menu, app } = require('electron')
const logger = require('./logger')

let tray = null

function createTray(getMainWindow) {
  const iconPath = path.join(__dirname, '..', '..', '..', 'resources', 'tray-icon.png')

  // A missing or unreadable icon must never take the whole app down with it —
  // this exact failure (UnhandledPromiseRejectionWarning from new Tray())
  // happened here before the icon asset existed.
  if (!fs.existsSync(iconPath)) {
    logger.warn(`Tray icon not found at ${iconPath} — skipping tray creation.`)
    return null
  }

  try {
    tray = new Tray(iconPath)
  } catch (e) {
    logger.error(`Failed to create tray: ${e.message}`)
    return null
  }
  tray.setToolTip('L.U.N.A.')

  tray.setContextMenu(Menu.buildFromTemplate([
    {
      label: 'Show Luna',
      click: () => {
        const win = getMainWindow()
        if (!win) return
        win.show()
        win.focus()
      },
    },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]))

  tray.on('click', () => {
    const win = getMainWindow()
    if (!win) return
    win.isVisible() ? win.hide() : win.show()
  })

  return tray
}

function destroyTray() {
  if (tray && !tray.isDestroyed()) tray.destroy()
  tray = null
}

module.exports = { createTray, destroyTray }

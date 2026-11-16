/**
 * Tracks every open BrowserWindow by name so the rest of the app can ask
 * "is the settings window already open?" instead of each module keeping
 * its own singleton variable (which is how you end up with two settings
 * windows fighting over the same IPC channel).
 */
'use strict'

const windows = new Map()

function register(name, win) {
  windows.set(name, win)
  win.on('closed', () => {
    if (windows.get(name) === win) windows.delete(name)
  })
}

function get(name) {
  const win = windows.get(name)
  return win && !win.isDestroyed() ? win : null
}

function focusOrCreate(name, createFn) {
  const existing = get(name)
  if (existing) {
    existing.focus()
    return existing
  }
  const win = createFn()
  register(name, win)
  return win
}

module.exports = { register, get, focusOrCreate }

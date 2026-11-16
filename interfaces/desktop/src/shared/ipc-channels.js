/**
 * Single source of truth for every IPC channel name.
 *
 * Both the main process (ipc/*.handlers.js) and the preload scripts import
 * from here instead of typing raw string literals — a typo in a channel
 * name becomes a missing-export error at require-time instead of a silent
 * "nothing happens when the button is clicked" bug at runtime.
 */
'use strict'

module.exports = Object.freeze({
  window: {
    minimize: 'window:minimize',
    maximize: 'window:maximize',
    close: 'window:close',
    isMaximized: 'window:is-maximized',
    toggleFullscreen: 'window:fullscreen',
    isFullscreen: 'window:is-fullscreen',
    maximizedChanged: 'window:maximized',
    fullscreenChanged: 'window:fullscreen-changed',
  },
  env: {
    get: 'env:get',
    save: 'env:save',
  },
  updater: {
    check: 'update:check',
    install: 'update:install',
    status: 'update:status',
  },
  system: {
    notify: 'system:notify',
    openUrl: 'system:open-url',
    copyText: 'system:clipboard-write',
    openSettings: 'system:open-settings',
    localToken: 'system:local-token',
    showSettings: 'system:show-settings',
    quit: 'system:quit',
  },
  server: {
    connection: 'server:connection',
    getConfig: 'server:get-config',
    test: 'server:test',
    save: 'server:save',
  },
})

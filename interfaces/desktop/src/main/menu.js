'use strict'

const { Menu, app } = require('electron')

function buildAppMenu({ openSettings }) {
  const template = [
    {
      label: app.name,
      submenu: [
        { label: 'Settings...', click: () => openSettings() },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    { role: 'editMenu' },
    { role: 'viewMenu' },
    { role: 'windowMenu' },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

module.exports = { buildAppMenu }

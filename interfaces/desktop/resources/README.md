# resources/

Static assets electron-builder packages alongside the app:

- `icon.ico` — Windows app icon
- `tray-icon.png` — system tray icon (loaded by `tray-service.js`)
- `settings.html` — the settings window's static page (loaded by `settings-window.js`)

None of these are code — nothing in `src/` should ever `require()` a file
from this directory, only reference its path.

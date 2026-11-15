# Luna Desktop — reference architecture

A clean, modular reference layout for the Electron shell. This is a
**scaffold, not a replacement** — the real, currently-shipping app still
lives in `../electron/` (a flat `main.js` + `settings.js` + `preload.js`).
Nothing here is wired into the build; it exists so the app can be migrated
into this shape incrementally, on purpose, rather than all at once.

## Why restructure at all

The current `electron/main.js` mixes five unrelated concerns in one file:
window creation, IPC handling, backend process supervision, the updater,
and the tray. Any change risks breaking an unrelated feature, and finding
"where does X happen" means reading the whole file. Splitting by
responsibility means a change to, say, the updater touches exactly one file
that has nothing else in it.

## Directory layout

```
desktop-app/
├── package.json
├── build/
│   └── electron-builder.yml        # packaging config, kept out of package.json
├── resources/                      # icons, tray image, settings.html (static, no code)
└── src/
    ├── main/                       # Node.js context — full OS access
    │   ├── index.js                # entry point: WIRES modules together, contains no logic itself
    │   ├── app-lifecycle.js        # single-instance lock, window-all-closed, before-quit
    │   ├── menu.js                 # application menu bar
    │   ├── backend/
    │   │   └── process-manager.js  # spawn/health-check/restart the Python backend
    │   ├── windows/
    │   │   ├── window-registry.js  # tracks open windows by name (no duplicate windows)
    │   │   ├── main-window.js
    │   │   └── settings-window.js
    │   ├── ipc/
    │   │   ├── index.js            # registers every handler module, once
    │   │   ├── window.handlers.js
    │   │   ├── env.handlers.js
    │   │   ├── updater.handlers.js
    │   │   └── system.handlers.js
    │   └── services/
    │       ├── env-store.js        # .env read/write — merges into existing lines, see note below
    │       ├── updater-service.js  # electron-updater wrapper
    │       ├── tray-service.js
    │       └── logger.js
    ├── preload/                    # one preload per window, each its own minimal API surface
    │   ├── main-preload.js
    │   └── settings-preload.js
    └── shared/
        └── ipc-channels.js         # single source of truth for every channel name
```

## Rules this layout is built to enforce

- **`main/index.js` never contains logic** — only requires + wires. If you're
  about to add an `ipcMain.handle(...)` or a `new BrowserWindow(...)` there,
  it belongs in `ipc/` or `windows/` instead.
- **Channel names are never string literals at the call site.** Both main and
  preload import them from `shared/ipc-channels.js`. A typo becomes an
  import error, not a silently-dead button.
- **Each preload exposes only what that window needs.** The settings window
  gets `settingsAPI` with exactly two methods — it has no business calling
  window controls or the updater, so those aren't on its bridge at all, even
  though the main process registers them globally.
- **One process-manager owns the backend subprocess.** Nothing else calls
  `spawn()` on it directly, so there's exactly one place that knows whether
  it's actually running, and exactly one restart/backoff policy.

## A lesson encoded into `services/env-store.js`

The real `electron/settings.js` had a production bug worth not repeating:
`writeEnv()` regenerated the *entire* `.env` file from a hardcoded template
on every save. Any key the template didn't know about — including every
setting added after that template was last updated — got silently deleted
the next time anyone saved anything, from any window. `env-store.js` here
merges into the existing file's lines instead, touching only keys in an
explicit `WRITABLE_KEYS` allowlist and leaving everything else exactly as
it was. Extend the allowlist when you add a setting; nothing gets wiped out
if you forget.

## Migrating a piece of the real app here

1. Pick one concern (e.g. the updater).
2. Move its logic into the matching `services/` + `ipc/*.handlers.js` pair.
3. Point `electron/main.js` at the new module instead of its inline code.
4. Repeat, one concern at a time — never a big-bang rewrite of the working app.

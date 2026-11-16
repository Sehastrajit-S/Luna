# Luna interfaces

Every way to use Luna. Each folder is a client of the Luna server in [`../server`](../server) and talks to it over HTTP, so none of them contain server logic.

| Folder | Platform | Type |
|---|---|---|
| [`web/`](web/) | Browser | React + Vite app |
| [`mobile/`](mobile/) | Android, iOS | Capacitor shell around the `web/` build |
| [`desktop/`](desktop/) | Windows | Electron app; starts a local server by default |
| [`cli/`](cli/) | Terminal | `luna` command |
| [`vscode/`](vscode/) | VS Code | Extension (TypeScript) |
| [`office/`](office/) | Microsoft 365 | Office Add-in (manifest + task pane), served by the server at `/addin/office` |
| [`google-workspace/`](google-workspace/) | Google Workspace | Apps Script add-on |

## Building

From the repo root:

```bash
npm run build           # web
npm run build:mobile    # web + Capacitor sync (then open android/ or ios/ in Android Studio / Xcode)
npm run build:desktop   # web + Windows installer in dist/desktop/
```

The Google Workspace add-on runs on Google's servers, so it needs a server URL reachable from the public internet. The other interfaces run on your device and can use a local or private-network URL.

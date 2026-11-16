# Luna AI — VS Code Extension

Chat with Luna, explain and fix code, and run web searches directly from VS Code.

## Requirements

Luna backend must be running (port 8899 by default).  
Start it with the Luna desktop app or: `python server/server.py`

## Install (Manual)

Copy the extension folder to VS Code's extensions directory:

```
xcopy /E /I "e:\Luna\vscode-extension" "%USERPROFILE%\.vscode\extensions\luna-ai-0.0.1"
```

Then **Restart VS Code**.

## Install (Development / F5)

1. Open `e:\Luna\vscode-extension` in VS Code
2. Press **F5** → opens an Extension Development Host window with Luna loaded

## Features

| Feature | How to use |
|---------|-----------|
| **Chat panel** | Click the ◆ icon in the Activity Bar |
| **Explain code** | Select code → Right-click → *Explain This Code* |
| **Fix code** | Select code → Right-click → *Fix This Code* |
| **Ask about selection** | Select code → Right-click → *Ask Luna About This* |
| **Open chat** | `Ctrl+Shift+L` |
| **Ask about selection** | `Ctrl+Shift+A` |
| **New conversation** | Click **＋** in the panel header |
| **Insert code** | Click **Insert** on any code block Luna returns |
| **Copy code** | Click **Copy** on any code block |

## Settings

`File → Preferences → Settings → search "Luna"`

| Setting | Default | Description |
|---------|---------|-------------|
| `luna.backendUrl` | `http://localhost:8899` | URL of the Luna backend |

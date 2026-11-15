# VS Code

The repository includes shared VS Code configuration in `.vscode/`.

Committed workspace files:

- `extensions.json`: recommended extensions for Python, TypeScript, Tailwind, ESLint, and formatting.
- `settings.json`: repo-local editor and analysis defaults.
- `tasks.json`: common L.U.N.A. CLI tasks.
- `launch.json`: backend and CLI debug configurations.

Local/private VS Code files remain ignored by `.gitignore`.

## Useful Tasks

Open the command palette and run `Tasks: Run Task`:

- `LUNA: Dev`
- `LUNA: Dev LAN`
- `LUNA: Web`
- `LUNA: Web LAN`
- `LUNA: Backend`
- `LUNA: Frontend`
- `LUNA: Electron`
- `LUNA: Check`
- `LUNA: Processes`
- `LUNA: Build`

## Debugging

Open the Run and Debug panel:

- `LUNA: Backend`: runs `backend/server.py` under the Python debugger.
- `LUNA: CLI Processes`: debugs process registry listing.
- `LUNA: CLI Doctor`: debugs CLI environment checks.

For full desktop development, use the `LUNA: Dev` task. For browser-only development or testing from another device, use `LUNA: Web` or `LUNA: Web LAN`.

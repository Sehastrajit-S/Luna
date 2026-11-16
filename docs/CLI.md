# CLI

L.U.N.A. includes a small Node-based CLI for common contributor workflows.

Install the CLI globally on macOS, Windows, or Linux:

```powershell
npm i -g luna-workspace
```

Shortest first run without a permanent install:

```powershell
npx luna-workspace setup
```

If the npm package is not published yet, install directly from GitHub:

```powershell
npm i -g github:Sehastrajit-S/Luna
```

Run it from the repo root:

```powershell
npm run luna -- <command>
```

After installing the package globally or linking it locally, the `luna` binary is also available:

```powershell
npm link
luna doctor
```

You can also run the wrapper command:

```powershell
npm run luna -- cli:install
```

## Commands

- `help`: show command help.
- `install:command`: print the one-line global CLI installer.
- `doctor`: check Node, npm, and Python availability.
- `dev`: start Vite and Electron together.
- `dev:lan`: start development mode with Vite exposed on the LAN.
- `web`: start the FastAPI backend and browser UI without Electron.
- `web:lan`: start the backend and expose the browser UI on the LAN for phones, tablets, and other computers.
- `backend`: start only the FastAPI backend.
- `frontend`: start only the Vite frontend.
- `electron`: start only the Electron shell.
- `build`: build the frontend.
- `dist`: build the frontend and Windows Electron package.
- `check`: run lightweight backend syntax checks.
- `processes`: print registered backend processes as JSON.
- `health`: check if the running backend is healthy.
- `status`: show backend, model, app, and permission status.
- `model [provider] [model]`: list or switch the active model provider.
- `connect_app [app]`: show connector status and setup hints.
- `apps`: alias for `connect_app`.
- `bugfix "<bug>"`: run the enterprise bugfix workflow from the CLI.
- `update`: pull latest Luna code, refresh dependencies, and run smoke checks.
- `self:update`: alias for `update`.
- `cli:install`: link the `luna` command globally with `npm link`.
- `clean`: remove local runtime/build artifacts ignored by git.

The CLI intentionally wraps existing npm and Python entrypoints. Feature-specific commands should stay thin and delegate to the owning process, service, or package script.

## Chat

`luna chat` uses the same `/api/chat/stream` path as the web and Electron UI. Terminal chat supports normal conversation plus tool execution, web research, workspace file creation, installed skills, agent tasks, Google/Microsoft workspace tools, plans, proactive messages, and backend command events.

```powershell
luna chat
luna chat "research the SEC and show references"
luna chat --yes "create the requested workspace file"
luna chat --no "try the task but deny any risky confirmation"
```

Inside chat:

- `/new`: start a fresh conversation.
- `/status`: show backend, model, and connector status.
- `/model`: list configured model providers.
- `/model <provider> [model]`: switch the active provider and optionally update its model.
- `/connect_app`: show configured app connectors.
- `/connect_app <google|github|slack|jira>`: show setup or OAuth instructions for one app.
- `/apps`: alias for `/connect_app`.
- `/skills`: list installed skills.
- `/permissions`: show risky or non-default tool permissions.
- `/crew <task>`: run a multi-agent crew from chat.
- `/bugfix <bug description>`: run the enterprise bugfix workflow.
- `/update`: pull latest Luna code and refresh dependencies.
- `/help`: show terminal chat commands.
- `/exit` or `/quit`: leave chat.

Update flags:

- `--force`: continue even when tracked files have local changes.
- `--skip-install`: pull code without running `npm install`.
- `--skip-check`: skip `npm run test:smoke`.
- `--link`: rerun `npm link` after updating.

When a tool requires confirmation, the CLI prompts for approval. Use `--yes` to auto-approve confirmations for a one-shot or session, and `--no` to auto-deny them.

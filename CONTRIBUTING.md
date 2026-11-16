# Contributing to L.U.N.A.

Thanks for your interest in Luna. Read this before you start.

---

## Attribution requirement

Luna is MIT-licensed. MIT lets you use, fork, and redistribute freely — but **attribution is required**:

- **Keep the copyright notice** in any source file you copy.
- **Credit Luna visibly** if your project is built on or derived from Luna code:
  - In your README: `Built with [L.U.N.A.](https://github.com/Sehastrajit-S/Luna)`
  - In any public UI or about page that ships Luna-derived code
- **Do not remove** the `L.U.N.A.` name, the copyright header, or the `LICENSE` file when distributing.

---

## Development setup

```bash
git clone https://github.com/Sehastrajit-S/Luna.git && cd Luna && npm install && npm run luna -- setup
```

The setup wizard installs Node and Python dependencies, configures your LLM provider, and pulls Ollama models. Then start the app:

```bash
npm run luna -- dev       # Electron + Vite + FastAPI
npm run luna -- web       # FastAPI + browser UI only
```

---

## Ways to contribute

### Add a skill (no code required)

Skills are plain-text files. Anyone can write one.

1. Copy `server/skills/_template/` to a new folder: `server/skills/my-skill/`
2. Edit `skill.json` — set the id, name, description, permissions, and tools
3. Edit `SKILL.md` — write the workflow Luna should follow
4. Test by restarting Luna and sending a matching prompt
5. Open a PR with 2–3 example prompts that trigger the skill

Full guide: [`server/skills/README.md`](server/skills/README.md)

---

### Add a health integration (one file)

Health platforms are auto-discovered. Adding one requires zero changes to the router, sync dispatcher, or frontend.

1. Copy `server/services/health_integrations/_template.py` to `server/services/health_integrations/myplatform.py`
2. Subclass `HealthIntegration` and implement three methods:
   - `manifest` — declare the platform name, auth type, and env var fields
   - `is_configured` — return `True` when credentials are present
   - `sync` — fetch data from the platform API and call `persist(db, points)`
3. For OAuth platforms, also implement `oauth_url` and `exchange_code`
4. Restart Luna — the platform appears in `/api/health/status` and `/api/health/manifests` automatically

The `_template.py` file is fully annotated with inline `# TODO` comments for every step.

---

### Add a platform add-on (Google Workspace, Office, VS Code)

Platform-specific extensions live in `integrations/`:

| Folder | Type | Entry point |
|---|---|---|
| `interfaces/google-workspace/` | Google Apps Script | `Code.gs` |
| `interfaces/office/` | Office Add-in | `manifest.xml` + `taskpane/` |
| `interfaces/vscode/` | VS Code Extension | `src/extension.ts` |

See the README inside each folder for setup and development instructions.

---

## Pull request guidelines

- Read `docs/architecture.svg` or `docs/architecture_ai.svg` before broad structural changes.
- Keep routers thin — logic lives in `server/services/`.
- Background jobs belong in `server/processes/`.
- Split large UI features by folder under `interfaces/web/src/components/`.
- One clear behaviour per PR. Include a description of what changed and how to test it.

---

## Testing

```bash
npm run test:smoke   # backend syntax + CLI entrypoint + tool wiring (run before every PR)
npm run test:tools   # tool-only suite (run when changing tool routing or registry)
npm run build        # frontend type check + bundle (run when changing frontend)
```

Smoke tests are non-destructive — they do not launch apps, type, lock the screen, switch audio devices, or start playback.

---

## Code style

- **Python:** PEP 8. Routers stay thin; logic goes in `server/services/`. No non-ASCII characters in log messages (Windows `cp1252` compatibility).
- **TypeScript:** strict mode is on. Named exports. Components in feature folders under `interfaces/web/src/components/`.
- **Skills:** plain English. Numbered workflow steps. Under ~150 lines per `SKILL.md`.

---

## What not to commit

- `.env`, API keys, tokens, credentials of any kind
- Local databases (`*.db`, `*.sqlite`)
- Chat logs, memory stores, personality state files
- Build artifacts, `node_modules/`, `__pycache__/`
- Personal runtime data from `data/`

---

## Questions

Open a [GitHub Discussion](https://github.com/Sehastrajit-S/Luna/discussions) before writing large changes — alignment first saves everyone time. Issues are for bugs and confirmed feature requests.

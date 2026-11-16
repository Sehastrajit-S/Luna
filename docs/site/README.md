# Luna Docs Site

Next.js documentation website for the L.U.N.A. project.

## Run locally

From the repo root:

```bash
npm run docs
```

Open `http://localhost:3000`.

Or from this folder directly:

```bash
npm install
npm run dev
```

## Build for production

```bash
npm run docs:build
npm run docs:start
```

## Pages

| Route | Contents |
|---|---|
| `/` | Landing page — quick links and project overview |
| `/getting-started` | Setup, local development, and first run |
| `/architecture` | Application architecture, layer boundaries, and data flow |
| `/cli` | Full `luna` CLI command reference |
| `/codebase` | Implementation deep-dive — entrypoints, services, runtime patterns |
| `/contributing` | Contributor guide — skills, health integrations, pull request process |
| `/project-structure` | Repository layout and module ownership |
| `/environment` | All `.env` variables with descriptions and examples |
| `/health` | Health platform setup, device list, metric types, and API reference |

## Theme

Light and dark modes are supported. The toggle is in the top bar; the selected theme is saved in `localStorage` and falls back to the system color scheme on first visit.

# Architecture

L.U.N.A. is split into four top-level work areas. Contributors should keep changes inside one area when possible.

## Backend

Path: `server/`

- `main.py`: FastAPI app setup, middleware, and router registration only.
- `routers/`: HTTP API routes. Routers should stay thin and delegate business logic to services.
- `services/`: feature logic, external providers, local model calls, background work, and integrations.
- `models/`: database models and request/response schemas.

Dashboard provider modules live in `server/services/dashboard/`:

- `news.py`: RSS and TheNewsAPI aggregation.
- `markets.py`: stock and crypto quotes/history.
- `weather.py`: Open-Meteo and wttr.in weather.
- `articles.py`: article fetch and cleanup.
- `common.py`: shared headers and logging helpers.

## Frontend

Path: `interfaces/web/src/`

- `api/`: client wrappers for backend API calls.
- `components/`: UI grouped by feature.
- `hooks/`: reusable React hooks.
- `services/`: browser/device service helpers.
- `store/`: global app state.
- `types/`: shared frontend TypeScript types.

Large frontend features should be split into:

- `FeatureView.tsx` for the screen container.
- `FeaturePanel.tsx` or `FeatureWidget.tsx` for reusable UI pieces.
- `featureTypes.ts` for local types when they are not globally shared.
- `featureApi.ts` when a feature has multiple API calls.

The Luna dashboard follows this pattern:

- `components/Luna/LunaDashboardView.tsx`: dashboard layout and widgets.
- `components/Luna/LunaDashboardToggle.tsx`: title-bar toggle control.
- `components/Luna/lunaDashboardApi.ts`: API URL, auth, and cache helpers.

## Electron

Path: `electron/`

- `main.js`: desktop shell, backend process lifecycle, tray, native IPC.
- `preload.js`: safe renderer bridge. Keep exposed APIs narrow and documented.
- `assets/`: desktop app icons and tray assets.

## Skills

Path: `server/skills/`

Skills are optional extensions. A skill should include a `skill.json` manifest and a focused `SKILL.md`.

## Contribution Boundaries

Prefer small PRs scoped to one feature area:

- Backend provider change: one file under `server/services/dashboard/` plus route tests/docs if needed.
- API shape change: router + frontend API client + affected components.
- UI-only change: affected component folder only.
- Desktop-only change: `electron/` only.
- Model/provider change: `server/services/llm/` and `.env.example`.
- Runtime/background process change: one package under `server/processes/`.

Avoid placing provider logic inside routers or React components. Routers should compose services; components should render state and call API helpers.

See `docs/PROCESSES.md` for the process registry pattern.

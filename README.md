<div align="center">
  <img src="docs/site/public/images/banner.svg" width="100%" alt="L.U.N.A. - Large Unified Nexus Mind AI" />
  <br />

  <p>
    <a href="https://github.com/Sehastrajit-S/Luna/stargazers">
      <img src="https://img.shields.io/github/stars/Sehastrajit-S/Luna?style=for-the-badge&logo=github&color=6d28d9&labelColor=030306" alt="Stars" />
    </a>
    <a href="https://github.com/Sehastrajit-S/Luna/forks">
      <img src="https://img.shields.io/github/forks/Sehastrajit-S/Luna?style=for-the-badge&logo=github&color=7c3aed&labelColor=030306" alt="Forks" />
    </a>
    <a href="https://github.com/Sehastrajit-S/Luna/blob/main/LICENSE">
      <img src="https://img.shields.io/github/license/Sehastrajit-S/Luna?style=for-the-badge&color=8b5cf6&labelColor=030306" alt="License" />
    </a>
    <a href="https://github.com/Sehastrajit-S/Luna/commits/main">
      <img src="https://img.shields.io/github/last-commit/Sehastrajit-S/Luna?style=for-the-badge&color=a78bfa&labelColor=030306" alt="Last Commit" />
    </a>
    <a href="https://github.com/Sehastrajit-S/Luna/issues">
      <img src="https://img.shields.io/github/issues/Sehastrajit-S/Luna?style=for-the-badge&color=c4b5fd&labelColor=030306" alt="Issues" />
    </a>
  </p>

  <p>
    <a href="https://github.com/Sehastrajit-S/Luna">
      <img src="https://img.shields.io/badge/View%20on%20GitHub-%23030306?style=for-the-badge&logo=github&logoColor=white" alt="View on GitHub" />
    </a>
  </p>

  <br />

  <img src="https://img.shields.io/badge/Electron-191970?style=flat-square&logo=electron&logoColor=white" />
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" />
  <img src="https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/TypeScript-007ACC?style=flat-square&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-07405E?style=flat-square&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Three.js-000000?style=flat-square&logo=three.js&logoColor=white" />
</div>

<br />

---

**L.U.N.A. is an open-source AI engine** - a local-first platform you own completely. Drop in any LLM, extend it with skills written in plain text, connect your health devices, automate your desktop, and talk to it with your voice. No subscriptions, no cloud lock-in, no data leaving your machine by default.

It ships as two modes: **Personal** (voice, vision, Spotify, health data, desktop automation) and **Business** (multi-user JWT auth, rate limiting, Telegram/Discord/Slack channels). Switch between them with a single `.env` change.

---

## Get started

```bash
git clone https://github.com/Sehastrajit-S/Luna.git && cd Luna && npm install && npm run luna -- setup
```

The setup wizard picks your variant, configures your LLM provider, installs Python and Node dependencies, and pulls Ollama models. Luna opens on **http://localhost:8899** in about two minutes.

> Need voice, camera, and desktop automation? See [Desktop install](#desktop-install) for the Electron shell.

---

## Table of Contents

- [What it is](#what-it-is)
- [Variants](#variants)
- [Features](#features)
- [Any Model](#any-model)
- [Skills - extend without code](#skills--extend-without-code)
- [Health Platforms](#health-platforms)
- [Desktop install](#desktop-install)
- [Docker](#docker)
- [Stack](#stack)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Device Support](#device-support)
- [Project Layout](#project-layout)
- [Testing](#testing)
- [Contributing](#contributing)
- [Privacy](#privacy)
- [License](#license)

---

## What it is

Luna is the engine underneath. It handles:

- **LLM routing** - one config line switches between 8 providers. Ollama by default, any OpenAI-compatible endpoint, or every major cloud model.
- **Memory** - facts, personality, and conversation summaries persist in local SQLite + ChromaDB. Luna remembers across sessions.
- **Skill system** - extend the engine by dropping a folder into `server/skills/`. No Python, no restarts, no wiring - just a `skill.json` and a plain-text `SKILL.md`. Skills are loaded per-request at runtime.
- **Health data engine** - 7 platforms, 23 metric types, normalized and stored locally. Add a new platform by writing one Python file.
- **Voice + vision pipeline** - wake-word detection, faster-whisper STT, edge-tts TTS, and moondream camera analysis running fully on-device.
- **Tool layer** - web search, page fetch, Spotify, calendar, desktop automation, workspace file ops, 3D scene generation. Every tool goes through an audit log and permission system.
- **Streaming first** - all responses stream over SSE. Commands embedded in the stream trigger widgets, maps, Spotify controls, 3D scenes in the UI.

---

## Variants

| | **Personal** | **Business** |
|---|---|---|
| **Best for** | Individual daily use | Teams and companies |
| **Auth** | None required | Multi-user JWT |
| **Rate limiting** | Off | Sliding-window, configurable |
| **Messaging channels** | - | Telegram, Discord, Slack, webhook |
| **Voice + vision** | ✓ | - |
| **Health platforms** | ✓ | ✓ |
| **Spotify + app launcher** | ✓ | - |
| **Calendar + web search** | ✓ | ✓ |
| **Docker** | `luna docker` | `luna docker:business` |

Switch at any time: change `luna_variant=personal` or `luna_variant=business` in `.env` and restart. No data is lost.

---

## Features

| Capability | Personal | Business |
|---|---|---|
| 🎙 **Voice** - wake-word, push-to-talk, faster-whisper STT, edge-tts / pyttsx3 TTS | ✓ | - |
| 🧠 **Memory** - persistent facts, personality state, conversation summaries (SQLite + ChromaDB) | ✓ | ✓ |
| 👁 **Vision** - screen and camera awareness via moondream, no raw frames stored | ✓ | - |
| ⚡ **Automation** - app launcher, Spotify control, audio device switcher | ✓ | - |
| 📅 **Calendar + Tasks** - create, list, update tasks with proactive reminders | ✓ | ✓ |
| 📊 **Dashboard** - live news, weather, markets, and maps widget layer | ✓ | ✓ |
| 🌐 **Web Tools** - DuckDuckGo search and page fetch | ✓ | ✓ |
| 🧩 **Dynamic Widgets** - steps, timelines, code blocks, 3D scenes (Three.js) | ✓ | ✓ |
| 💓 **Health Platforms** - Fitbit, Google Fit, Oura, Withings, Garmin, Apple Health, Samsung | ✓ | ✓ |
| 🧠 **Skills** - plain-text agent skills, auto-loaded at runtime, no restart needed | ✓ | ✓ |
| ✈️ **Messaging Channels** - Telegram, Discord, Slack, generic webhook | - | ✓ |
| 🔐 **JWT Auth** - multi-user tokens, admin user management API | - | ✓ |
| 🚦 **Rate Limiting** - sliding-window per-IP, configurable burst | - | ✓ |
| 🔒 **Private** - inference runs locally via Ollama by default, zero telemetry | ✓ | ✓ |

---

## Any Model

One line in `.env` switches the provider - no code changes, no restart of anything else.

| Provider | `llm_provider` | Key needed |
|---|---|---|
| **Ollama** (local, default) | `ollama` | None |
| **NVIDIA NIM** | `nvidia-nim` | `nvidia_nim_api_key` |
| **Anthropic Claude** | `anthropic` | `anthropic_api_key` |
| **Google Gemini** | `google` | `google_api_key` |
| **Groq** | `groq` | `groq_api_key` |
| **Cohere** | `cohere` | `cohere_api_key` |
| **Mistral AI** | `mistral` | `mistral_api_key` |
| **OpenAI / OpenRouter / LM Studio / llama.cpp** | `openai-compatible` | `openai_api_key` (optional for local) |

**OpenRouter** - one key, every major model, pay-as-you-go:

```env
llm_provider=openai-compatible
openai_base_url=https://openrouter.ai/api/v1
openai_api_key=sk-or-...
openai_model=anthropic/claude-opus-4
```

---

## Skills - extend without code

Skills teach Luna new behaviors. Drop a folder into `server/skills/` and it's live on the next request - no Python, no restarts, no wiring.

```
server/skills/
└── my-skill/
    ├── skill.json   ← what it does, what tools it can use
    └── SKILL.md     ← instructions Luna follows
```

**Built-in skills:**

| Skill | What it does |
|---|---|
| [`research/`](server/skills/research/) | Web search with source comparison and cited answers |
| [`coding-agent/`](server/skills/coding-agent/) | Write, edit, debug, and run code in the workspace |
| [`desktop-agent/`](server/skills/desktop-agent/) | Multi-step desktop automation with confirmation gates |
| [`dataset-builder/`](server/skills/dataset-builder/) | Fetch or generate datasets from real sources with provenance |
| [`document-drafter/`](server/skills/document-drafter/) | Draft reports, proposals, memos, and policies |
| [`file-builder/`](server/skills/file-builder/) | Create and convert files of any format in the workspace |
| [`job-application-assistant/`](server/skills/job-application-assistant/) | Tailor resumes, draft cover letters, prep for interviews |
| [`resume-checker/`](server/skills/resume-checker/) | Review, score, and rewrite resumes against a job post |
| [`workspace-suite/`](server/skills/workspace-suite/) | Gmail, Calendar, Drive, Outlook, OneDrive, Teams - all in one |

See [`server/skills/README.md`](server/skills/README.md) for a full contributor guide and [`server/skills/_template/`](server/skills/_template/) for a ready-to-copy starter.

---

## Health Platforms

<div align="center">
  <img src="docs/site/public/images/health-platforms.svg" width="100%" alt="Health platform integrations" />
</div>

Luna connects to 7 health platforms and normalizes everything into 23 metric types stored locally in SQLite. Adding a new platform takes one Python file - no changes to the router, sync dispatcher, or frontend.

| Platform | Auth | Key Metrics |
|---|---|---|
| **Fitbit** | OAuth2 | Steps, HR, HRV, sleep stages, SpO2, skin temp, weight, breathing rate |
| **Google Fit** | OAuth2 | Steps, calories, HR, weight, body fat, SpO2, sleep - all Android wearables |
| **Oura Ring** | API token | Sleep stages, HRV, resting HR, readiness score, stress, respiratory rate |
| **Withings** | OAuth2 | Weight, BMI, body fat, blood pressure, HR, sleep |
| **Garmin Connect** | Credentials | VO2 Max, Body Battery, stress, GPS workouts, sleep, SpO2 |
| **Apple Health** | Webhook | All HealthKit metrics via iOS "Health Auto Export" app |
| **Samsung Health** | Webhook | Galaxy Watch metrics via compatible Android exporter |

```bash
# Trigger a sync after configuring credentials in .env
curl -X POST http://localhost:8899/api/health/sync

# Ask Luna
# "How was my sleep last night?"
# "What's my HRV trend this week?"
# "Sync my Fitbit and tell me how my recovery looks"
```

---

## Desktop install

**Prerequisites:** Node.js 18+, Python 3.10+, [Ollama](https://ollama.com/) installed and running.

```bash
git clone https://github.com/Sehastrajit-S/Luna.git && cd Luna && npm install && npm run luna -- setup
```

Then start Luna:

```bash
luna dev        # Electron + Vite + FastAPI (full desktop with voice and vision)
luna web        # FastAPI + browser UI, no Electron
luna backend    # FastAPI only
```

Run `luna doctor` if something doesn't start - it checks Node, Python, Ollama, and Docker in one shot.

**Windows installer:**

```powershell
npm run installer
```

Builds an NSIS Electron installer. On first launch, a setup window lets the user choose Personal or Business, pick their LLM provider, and enter credentials before the backend starts.

---

## Docker

The CLI auto-detects the right compose file from your `.env`:

| Command | When to use |
|---|---|
| `luna docker` | Personal, CPU (default) |
| `luna docker:gpu` | Personal, NVIDIA GPU |
| `luna docker:cloud` | Personal, cloud LLM (no Ollama needed) |
| `luna docker:business` | Business variant |

```bash
# NVIDIA GPU
luna docker:gpu

# Cloud LLM - set llm_provider in .env first
luna docker:cloud

# Business
cp deploy/.env.business.example .env
luna docker:business
```

Upgrading:

```bash
git pull && luna docker
```

Data persists in named Docker volumes (`luna_data`, `ollama_data`).

---

## Stack

### Frontend

| Layer | Tech |
|---|---|
| Shell | Electron |
| UI Framework | React + Vite |
| Language | TypeScript |
| Styling | Tailwind CSS |
| State | Zustand |
| 3D | Three.js |
| Maps | MapLibre GL |

### Backend

| Layer | Tech |
|---|---|
| API | FastAPI + Uvicorn |
| Database | SQLite |
| Vector store | ChromaDB |
| LLM | Ollama, Anthropic, Google, Groq, Cohere, Mistral, or any OpenAI-compatible endpoint |
| STT | faster-whisper |
| TTS | edge-tts / pyttsx3 |
| HTTP | httpx |

### AI Models

| Purpose | Default |
|---|---|
| Chat | `qwen2.5:7b` via Ollama (configurable) |
| Embeddings | `nomic-embed-text` |
| Vision | `moondream` |
| Code | `qwen2.5-coder:7b` (coding-agent skill) |

---

## Architecture

Three layers:

1. **Electron** - starts the desktop shell, launches the FastAPI backend, hosts the React renderer.
2. **React** - renders chat, voice controls, dashboard, maps, dynamic widgets, and 3D scenes.
3. **FastAPI** - owns chat streaming, voice, memory, vision, tool execution, live data, Spotify, scheduling, messaging channels, auth, rate limiting, and all LLM calls.

```
User input (browser · Electron · Telegram · Discord · Slack · webhook)
    │
    ▼
Variant check (personal | business)
    │
    ▼
Context assembly (memory + personality + calendar + vision + conversation)
    │
    ▼
LLM inference  ←── Ollama / NVIDIA NIM / Anthropic / Google / Groq / Cohere / Mistral / OpenAI-compatible
    │
    ▼
Tool execution (web_search · web_fetch · Spotify · calendar · widgets · maps · skills)
    │
    ▼
Memory update  (fact extraction · personality update · conversation compaction)
    │
    ▼
Response streamed to UI  (or plain-text reply to channel)
```

Full diagrams: [architecture.svg](docs/architecture.svg) · [architecture_ai.svg](docs/architecture_ai.svg)

---

## Configuration

Copy `.env.example` to `.env`. Never commit `.env`.

```env
# Variant
luna_variant=personal          # personal | business

# Identity
user_name=friend

# LLM - Ollama (default, runs locally)
llm_provider=ollama
ollama_base_url=http://localhost:11434
ollama_model=qwen2.5:7b

# LLM - Anthropic Claude
# llm_provider=anthropic
# anthropic_api_key=sk-ant-...
# anthropic_model=claude-sonnet-4-5

# LLM - any OpenAI-compatible endpoint
# llm_provider=openai-compatible
# openai_base_url=https://openrouter.ai/api/v1
# openai_api_key=sk-or-...
# openai_model=anthropic/claude-opus-4

# LLM - NVIDIA NIM
# llm_provider=nvidia-nim
# nvidia_nim_api_key=nvapi-...
# nvidia_nim_model=meta/llama-3.1-8b-instruct

# Business - auth and rate limiting
# jwt_secret=change-me
# rate_limit_enabled=true
# rate_limit_per_minute=60

# Messaging channels (business)
# telegram_bot_token=
# discord_bot_token=
# slack_bot_token=

# Workspace integrations
# google_workspace_client_id=
# google_workspace_client_secret=
# google_workspace_refresh_token=
# microsoft_workspace_client_id=
# microsoft_workspace_client_secret=
# microsoft_workspace_tenant_id=common
# microsoft_workspace_refresh_token=

# Optional
the_news_api=
spotify_client_id=
spotify_client_secret=
```

Run `luna setup` at any time to reconfigure interactively.

---

## Device Support

Any device on your LAN can connect:

```env
# .env
host=0.0.0.0
```

```bash
luna web:lan
```

Open `http://YOUR-LAN-IP:5173` on any phone, tablet, or second computer. Voice, camera, and OS-level features depend on browser permissions and are fully supported on the host desktop.

To use Luna from anywhere, share it over Tailscale with `luna serve --tailscale`. In the desktop app on another computer, open Settings → Server and pick **Remote over Tailscale**. See [docs/REMOTE.md](docs/REMOTE.md).

---

## Project Layout

```
Luna/
├── server/              # FastAPI server (Python package `server`)
│   ├── routers/         # Thin HTTP layer - logic lives in services/
│   ├── services/        # LLM, memory, agent loop, tools, connectors (GitHub, Jira, Google, Microsoft)
│   ├── processes/       # Background jobs - memory maintenance, reminders, voice runtime
│   ├── mcp/             # MCP servers for Claude Desktop
│   ├── skills/          # Built-in skills - copy _template/ to create one
│   └── migrations/      # Alembic database migrations
├── interfaces/          # Every client of the server
│   ├── web/             # React + Vite UI
│   ├── mobile/          # Capacitor shell (Android, iOS) around the web build
│   ├── desktop/         # Electron app
│   ├── cli/             # `luna` command
│   └── vscode/ office/ google-workspace/   # Editor and productivity add-ins
├── tests/               # Unit tests (tests/tools) and evals (tests/evals)
├── scripts/             # Build, Docker, icon and screenshot helpers
├── docs/                # Reference docs; docs/site is the documentation website
├── deploy/              # Docker Compose files and variant .env templates
├── data/                # Runtime data (not committed)
└── .env.example
```

---

## Testing

Run the smoke suite before opening a PR:

```bash
npm run test:smoke   # backend syntax + CLI + tool wiring
npm run test:tools   # tool-only suite
npm run build        # frontend type check + bundle
```

Smoke tests are non-destructive - they do not launch apps, type, lock the screen, switch audio devices, or start playback.

---

## Contributing

1. Fork the repo and create a branch from `main`.
2. Make your changes.
3. Run `npm run test:smoke` (backend/CLI changes) or `npm run build` (frontend changes).
4. Open a pull request with a clear description of what changed and why.

**Adding a skill** - the easiest contribution. Copy [`server/skills/_template/`](server/skills/_template/), fill in `skill.json` and `SKILL.md`, and open a PR. No Python knowledge needed. See [`server/skills/README.md`](server/skills/README.md).

**Adding a health integration** - copy [`server/services/health_integrations/_template.py`](server/services/health_integrations/_template.py), subclass `HealthIntegration`, fill in the `manifest` and `sync()` method. Auto-discovered on restart, zero other changes needed. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Privacy

- Chat inference runs through local Ollama - no tokens leave your machine by default.
- Memory, facts, and personality state are stored in local SQLite and ChromaDB.
- Vision summaries are generated locally by moondream; no raw frames are stored or transmitted.
- External APIs (news, weather, markets, Spotify) are only contacted when configured and used.
- Keep `.env`, `data/`, and generated memory stores out of version control.

---

## License

MIT - see [LICENSE](LICENSE).

---

<div align="center">
  <sub>Built by the L.U.N.A. contributors. Open source, always.</sub>
</div>

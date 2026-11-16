<div align="center">
  <img src="docs/site/public/images/banner.svg" width="100%" alt="Luna: your own AI assistant. Runs on your machine, works with any model, follows you everywhere." />

  <h1>Luna: the open-source AI engine you own</h1>

  <h3>A self-hosted AI assistant that runs on your machine, works with any model, and follows you to every device.</h3>

  <p>
    <a href="https://github.com/Sehastrajit-S/Luna/releases/latest"><img src="https://img.shields.io/github/v/release/Sehastrajit-S/Luna?style=flat-square&color=6d28d9&label=release" alt="Latest release" /></a>
    <a href="https://github.com/Sehastrajit-S/Luna/releases"><img src="https://img.shields.io/github/downloads/Sehastrajit-S/Luna/total?style=flat-square&color=7c3aed" alt="Downloads" /></a>
    <a href="https://github.com/Sehastrajit-S/Luna/stargazers"><img src="https://img.shields.io/github/stars/Sehastrajit-S/Luna?style=flat-square&color=8b5cf6" alt="Stars" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/Sehastrajit-S/Luna?style=flat-square&color=a78bfa" alt="MIT license" /></a>
    <a href="https://github.com/Sehastrajit-S/Luna/commits/main"><img src="https://img.shields.io/github/last-commit/Sehastrajit-S/Luna?style=flat-square&color=c4b5fd" alt="Last commit" /></a>
  </p>

  <p>
    <a href="https://github.com/Sehastrajit-S/Luna/releases/latest"><b>Download</b></a> ·
    <a href="https://www.luna-ai-engine.com"><b>Docs</b></a> ·
    <a href="#quick-start"><b>Quick start</b></a> ·
    <a href="#a-quick-tour"><b>Tour</b></a> ·
    <a href="docs/REMOTE.md"><b>Use it anywhere</b></a> ·
    <a href="server/skills/README.md"><b>Write a skill</b></a> ·
    <a href="CONTRIBUTING.md"><b>Contribute</b></a>
  </p>
</div>

<p align="center">
  <img src="docs/media/luna-demo.webp" width="100%" alt="Luna demo: any model, voice and meeting minutes, memory, store prices, every device, and an expanding graph of skills and integrations" />
  <br />
  <sub><a href="docs/media/luna-demo.mp4">▶ Watch with sound</a></sub>
</p>

Luna is an open-source, self-hosted AI assistant and agent engine, a private alternative to hosted chatbots. Chat with it or talk to it, hand it your files, let it take meeting notes, search the web and write documents, and keep everything on hardware you own. It runs local LLMs through Ollama out of the box, or any cloud model you choose: Claude, Gemini, OpenAI, Groq, Mistral and more.

- **Private by default.** Inference runs locally through Ollama. Memory, chats and files stay in your own SQLite database.
- **Any model.** One line in `.env` switches between Ollama, Claude, Gemini, Groq, Mistral, Cohere, NVIDIA NIM or any OpenAI-compatible endpoint.
- **Remembers you.** Facts and preferences carry over between conversations.
- **Works with your files.** Attach PDFs, Word, Excel, slides, images or code. Everything you share, and everything Luna makes, lands in the Library.
- **Extend it in plain text.** A skill is a folder with a short JSON file and a Markdown file. No Python needed.
- **Everywhere you are.** Desktop app, browser and phone. Reach your own Luna from anywhere over Tailscale, with no ports opened to the internet.

## Quick start

**Download the app** from the [latest release](https://github.com/Sehastrajit-S/Luna/releases/latest):

| Platform | File |
|---|---|
| Windows | `Luna-Setup-<version>.exe` |
| macOS | `Luna-<version>-macos-arm64.dmg` (Apple silicon) or `-macos-x64.dmg` (Intel) |
| Linux | `Luna-<version>-linux-x86_64.AppImage` or `-linux-arm64.AppImage` |
| Android | `Luna-<version>-android.apk` |
| iPhone / iPad | Open your Luna in Safari and choose **Add to Home Screen** |

The desktop apps set themselves up on first launch (no Python install needed) and run a local server, or connect to one on another computer.

**One-line install:**

```bash
curl -fsSL https://www.luna-ai-engine.com/install.sh | sh        # macOS / Linux
irm https://www.luna-ai-engine.com/install.ps1 | iex             # Windows (PowerShell)
```

**Docker** (any OS, server and web UI):

```bash
docker run -d --name luna -p 127.0.0.1:8899:8899 -v luna_data:/app/data ghcr.io/sehastrajit-s/luna:latest
```

Open http://localhost:8899, then pick a model in **Settings → AI model** (a local Ollama model or a cloud API key).

**From source** (Node.js 18+, Python 3.10+):

```bash
git clone https://github.com/Sehastrajit-S/Luna.git && cd Luna
npm install
npm run setup             # picks a model, installs dependencies, writes .env
npm run web               # opens Luna at http://localhost:8899
```

**Use it from your phone or another computer:** share it privately over Tailscale with `npm run serve:tailscale`.

The full guide, covering Local and Remote setup, Docker, models and updating, is [docs/SETUP.md](docs/SETUP.md).

## A quick tour

### Chat with your files

Drop in a PDF, spreadsheet or slide deck and ask about it. Luna reads the text, keeps the file with the conversation, and can refer back to it later.

<img src="docs/screenshots/desktop-attachments.png" width="100%" alt="A chat with a PDF and a spreadsheet attached and a five-bullet summary" />

### A personality that learns you

Luna has moods. They shift with the time of day, how you're talking and the tone of your voice, and they change how she replies. Over time she learns your preferred style: how much humor, warmth, depth and detail, how often to ask questions, how formal to be. The sidebar panel shows her current mood, energy and learned style; turn it off in **Settings → Appearance**.

<img src="docs/screenshots/desktop-personality.png" width="100%" alt="Luna's personality panel in the sidebar, enlarged: mood Warm, energy 86%, and learned style bars for humor, warmth, depth, detail, curiosity and formality, shaped by 148 conversations" />

### On your phone

The same Luna in your phone's browser. The layout adapts on its own, and you can add it to your home screen.

<table>
  <tr>
    <td align="center"><img src="docs/screenshots/mobile-chat.png" width="250" alt="Luna chat on a phone" /></td>
    <td align="center"><img src="docs/screenshots/mobile-menu.png" width="250" alt="Luna menu on a phone" /></td>
    <td align="center"><img src="docs/screenshots/mobile-library.png" width="250" alt="Luna library on a phone" /></td>
  </tr>
</table>

### Use it from anywhere

Run Luna on your desktop and use it from your laptop or phone anywhere, privately, over [Tailscale](https://tailscale.com):

```bash
npm run serve:tailscale   # shares https://<your-pc>.<tailnet>.ts.net:8899 with your devices only
```

The desktop app finds shared Luna servers on your tailnet. Devices signed in to your own Tailscale account connect with one click and no token. Anyone else needs the access token. See [docs/REMOTE.md](docs/REMOTE.md).

<img src="docs/screenshots/desktop-server.png" width="100%" alt="Settings showing Luna servers discovered on a Tailscale network" />

### Skills and integrations

Built-in skills for research, coding, documents, datasets, job search and more, plus Google Workspace, Microsoft 365, GitHub and Spotify. Pick one from **+ → Skills** in the message box, or just ask. **+ → Meeting mode** records a meeting, transcribes it on your machine and writes the minutes (summary, decisions, action items), saved to the Library. **Compare store prices** puts one product side by side at Walmart, Costco, Target, Sam's Club and Safeway (needs a free [SerpApi](https://serpapi.com) key).

<img src="docs/screenshots/desktop-capabilities.png" width="100%" alt="Capabilities view listing skills and integrations" />

## Any model

<p>
  <img src="docs/images/logos/ollama.png" width="36" height="36" alt="Ollama" align="center" /> <img src="docs/images/logos/claude.png" width="36" height="36" alt="Claude" align="center" /> <img src="docs/images/logos/gemini.png" width="36" height="36" alt="Gemini" align="center" /> <img src="docs/images/logos/openai.png" width="36" height="36" alt="OpenAI" align="center" /> <img src="docs/images/logos/groq.png" width="36" height="36" alt="Groq" align="center" /> <img src="docs/images/logos/mistral.png" width="36" height="36" alt="Mistral" align="center" /> <img src="docs/images/logos/cohere.png" width="36" height="36" alt="Cohere" align="center" /> <img src="docs/images/logos/nvidia.png" width="36" height="36" alt="NVIDIA NIM" align="center" /> <img src="docs/images/logos/lmstudio.png" width="36" height="36" alt="LM Studio" align="center" /> <img src="docs/images/logos/llamacpp.png" width="36" height="36" alt="llama.cpp" align="center" />
</p>

| Provider | `llm_provider` | Key |
|---|---|---|
| <img src="docs/images/logos/ollama.png" width="20" height="20" alt="Ollama" align="center" /> **Ollama** (local, default) | `ollama` | none |
| <img src="docs/images/logos/claude.png" width="20" height="20" alt="Claude" align="center" /> **Anthropic Claude** | `anthropic` | `anthropic_api_key` |
| <img src="docs/images/logos/gemini.png" width="20" height="20" alt="Gemini" align="center" /> **Google Gemini** | `google` | `google_api_key` |
| <img src="docs/images/logos/groq.png" width="20" height="20" alt="Groq" align="center" /> **Groq** | `groq` | `groq_api_key` |
| <img src="docs/images/logos/mistral.png" width="20" height="20" alt="Mistral" align="center" /> **Mistral AI** | `mistral` | `mistral_api_key` |
| <img src="docs/images/logos/cohere.png" width="20" height="20" alt="Cohere" align="center" /> **Cohere** | `cohere` | `cohere_api_key` |
| <img src="docs/images/logos/nvidia.png" width="20" height="20" alt="NVIDIA" align="center" /> **NVIDIA NIM** | `nvidia-nim` | `nvidia_nim_api_key` |
| <img src="docs/images/logos/openai.png" width="20" height="20" alt="OpenAI" align="center" /> <img src="docs/images/logos/lmstudio.png" width="20" height="20" alt="LM Studio" align="center" /> <img src="docs/images/logos/llamacpp.png" width="20" height="20" alt="llama.cpp" align="center" /> **OpenAI, OpenRouter, LM Studio, llama.cpp** | `openai-compatible` | `openai_api_key` (optional for local) |

You can also list several Ollama servers in priority order with a cloud fallback, and switch models from the model pill in the chat box. Every option is documented in [`.env.example`](.env.example).

## Skills

A skill teaches Luna a new job. Drop a folder into `server/skills/` and it's picked up on the next request:

```
server/skills/my-skill/
├── skill.json   ← name, description, optional /trigger command, which tools it may use
└── SKILL.md     ← the instructions Luna follows
```

Built in: [research](server/skills/research/), [coding agent](server/skills/coding-agent/), [desktop agent](server/skills/desktop-agent/), [dataset builder](server/skills/dataset-builder/), [document drafter](server/skills/document-drafter/), [file builder](server/skills/file-builder/), [resume checker](server/skills/resume-checker/), [job application assistant](server/skills/job-application-assistant/), [workspace suite](server/skills/workspace-suite/), plus search skills for news, papers, products, jobs, local places and tech docs. Start from [`server/skills/_template/`](server/skills/_template/).

## Run it your way

| | Command |
|---|---|
| Browser UI | `npm run web` |
| Desktop app | `npm --prefix interfaces/desktop start` |
| Share over Tailscale | `npm run serve:tailscale` |
| Terminal chat | `npm run chat` |
| Docker with Ollama / GPU / cloud model | `docker compose -f deploy/compose.yml up -d` / add `-f deploy/compose.gpu.yml` / `deploy/compose.cloud.yml` |
| Something broken? | `npm run luna -- doctor` |

Luna also exposes its memory, web, workspace, GitHub, Google and Microsoft tools as [MCP servers](CLAUDE.md#claude-desktop-mcp-setup) for Claude Desktop (`python -m server.mcp.server_memory`, …), plus add-ins for [VS Code](interfaces/vscode/), [Office](interfaces/office/) and [Google Workspace](interfaces/google-workspace/).

<details>
<summary><b>Business mode</b>: multi-user auth, rate limiting, team chat channels</summary>

<br />

Set `luna_variant=business` in `.env` (or start from [`deploy/.env.business.example`](deploy/.env.business.example)) to get multi-user JWT auth, per-user rate limiting, and Telegram, Discord, Slack and webhook channels. Run it with `npm run luna -- docker:business`. Voice and desktop automation stay in personal mode.

</details>

<details>
<summary><b>Health platforms</b>: Fitbit, Oura, Garmin, Apple Health and more</summary>

<br />

<img src="docs/site/public/images/health-platforms.svg" width="100%" alt="Health platform integrations" />

Luna syncs Fitbit, Google Fit, Oura, Withings, Garmin, Apple Health and Samsung Health into 23 normalized metrics stored locally, so you can ask "How was my sleep this week?". Adding a platform is one Python file; see [`server/services/health_integrations/`](server/services/health_integrations/).

</details>

## Project layout

```
server/        FastAPI server: chat pipeline, memory, tools, connectors, skills, MCP servers
interfaces/    every client: web, mobile (Capacitor), desktop (Electron), cli, vscode, office, google-workspace
tests/         unit tests and evals
docs/          reference docs, REMOTE.md, and the docs website (docs/site)
deploy/        Docker Compose files and .env templates
scripts/       build, Docker and screenshot helpers
```

How a message flows through the server is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contributing

Pull requests are welcome. The easiest first contribution is a skill: copy [`server/skills/_template/`](server/skills/_template/) and fill in two files. For code changes:

```bash
npm run test:smoke   # server syntax, CLI and tool tests
npm run build        # web type check and bundle
```

The tests never launch apps, type, lock the screen or play audio. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Privacy

- With Ollama, no prompt or reply leaves your machine.
- Chats, memory and files live in `data/` on the server, in SQLite and ChromaDB.
- External services (web search, news, weather, Spotify, cloud models) are contacted only when you configure and use them.
- Remote access goes over your private Tailscale network, never the open internet.

## License

[MIT](LICENSE)

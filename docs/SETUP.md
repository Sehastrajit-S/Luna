# Setting up Luna

Luna is a **server** (it does the thinking and keeps your chats, memory and files) and **apps** that talk to it: the desktop app, any browser, and the phone app. Set up the server once, on the computer that will run it, then use it from that computer (**Local**) or from your other devices (**Remote**, over Tailscale).

- [1. Pick how to run the server](#1-pick-how-to-run-the-server)
- [2. Choose a model](#2-choose-a-model)
- [3. Use it on this computer (Local)](#3-use-it-on-this-computer-local)
- [4. Use it from your other devices (Remote, over Tailscale)](#4-use-it-from-your-other-devices-remote-over-tailscale)
- [5. Updating](#5-updating)
- [Troubleshooting](#troubleshooting)

## 1. Pick how to run the server

| | Good for | You need |
|---|---|---|
| **A. Docker** | Any OS, nothing else to install, easy upgrades | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on Linux) |
| **B. Windows desktop app** | A Windows PC you use every day, with voice and desktop controls | Windows 10/11, plus Python 3.10+ for the built-in server |
| **C. From source** | Developing Luna, or Linux/macOS without Docker | Node.js 18+ and Python 3.10+ |

### A. Docker

```bash
docker run -d --name luna --restart unless-stopped \
  -p 127.0.0.1:8899:8899 -v luna_data:/app/data \
  ghcr.io/sehastrajit-s/luna:latest
```

Open **http://localhost:8899**. Everything Luna stores lives in the `luna_data` volume, including settings you save in the browser, so upgrading never loses anything.

Prefer Compose, with Ollama included? From a clone of this repo:

```bash
docker compose -f deploy/compose.yml up -d          # Luna + Ollama on CPU
docker compose -f deploy/compose.yml -f deploy/compose.gpu.yml up -d   # with an NVIDIA GPU
docker compose -f deploy/compose.cloud.yml up -d    # Luna only, for a cloud model
```

`-p 127.0.0.1:8899:8899` keeps Luna reachable from this computer only. Don't publish the port on your network; use Tailscale for other devices ([section 4](#4-use-it-from-your-other-devices-remote-over-tailscale)).

### B. Windows desktop app

1. Download `Luna-Setup-<version>.exe` from [Releases](https://github.com/Sehastrajit-S/Luna/releases) and run it.
2. The app starts its own server using the Python on your PC, so install [Python 3.10+](https://www.python.org/downloads/) and Luna's packages once:
   ```powershell
   git clone https://github.com/Sehastrajit-S/Luna.git
   pip install -r Luna\server\requirements.txt
   ```
   No Python? Run the server with Docker (A) instead. When a Luna server is already running on port 8899, the desktop app uses it.

### C. From source

```bash
git clone https://github.com/Sehastrajit-S/Luna.git && cd Luna
npm install
npm run setup     # picks a model, installs Python and Node packages, writes .env
npm run web       # Luna at http://localhost:8899
```

Desktop app from source: `npm --prefix interfaces/desktop start`.

## 2. Choose a model

Open **Settings → AI model** in Luna, or set it in `.env` (start from [`.env.example`](../.env.example)).

- **Ollama (local, free, private):** install [Ollama](https://ollama.com) and pull a model, e.g. `ollama pull qwen2.5:7b`. With Docker Compose, Ollama is included: `docker compose -f deploy/compose.yml exec ollama ollama pull qwen2.5:7b`.
- **A cloud model:** pick the provider and paste its API key (Anthropic, Google, Groq, Mistral, Cohere, NVIDIA NIM, or any OpenAI-compatible service such as OpenRouter).

Optional extras in **Settings → Integrations**: GitHub, Spotify, and a SerpApi key for live store prices.

## 3. Use it on this computer (Local)

- **Browser:** http://localhost:8899
- **Desktop app:** opens on **This computer** by default (Settings → Server).

Nothing needs a token on the same computer.

## 4. Use it from your other devices (Remote, over Tailscale)

[Tailscale](https://tailscale.com) is a free private network between your devices. Luna stays off the public internet; only devices signed in to your tailnet can reach it.

### On the computer running Luna

Install Tailscale and sign in. Then:

| Server type | Share it |
|---|---|
| From source (C) | `npm run serve:tailscale` (starts Luna and shares it) |
| Desktop app (B) or Docker (A) | `tailscale serve --bg --https=8899 http://127.0.0.1:8899` |

Luna is now at `https://<this-computer>.<your-tailnet>.ts.net:8899`. Stop sharing with `npm run serve:tailscale:off` or `tailscale serve --https=8899 off`.

### On your other devices

Install Tailscale on each device and sign in with the **same account**.

| Device | How |
|---|---|
| Another computer with the desktop app | Settings → Server → **Remote over Tailscale**. Luna lists the servers it finds; pick yours and click **Save and restart**. |
| Any browser, including phones | Open `https://<this-computer>.<your-tailnet>.ts.net:8899`. On a phone, "Add to Home Screen" makes it open like an app. |
| Android app | Settings → Server: enter the same URL. |

### Who gets in without a token

- **Your own devices** (same Tailscale account) get in without a token when Luna was started from source or with the desktop app.
- **Docker:** Tailscale's proxy reaches the container from outside it, so Luna can't confirm the signed-in account and every remote device needs the **access token** once:
  ```bash
  docker exec luna cat /app/data/local_api_token
  ```
  Open `https://<…>.ts.net:8899/#token=<token>` once in each browser, or paste the token in the desktop app's Server settings.
- **Other people on your tailnet** always need the token. It's in `data/local_api_token` and printed by `npm run serve:tailscale`. Treat it like a password: it gives full access to that Luna.

Details: [REMOTE.md](REMOTE.md).

## 5. Updating

| Setup | Update |
|---|---|
| Docker | `docker pull ghcr.io/sehastrajit-s/luna:latest`, then recreate the container (or `docker compose -f deploy/compose.yml pull && docker compose -f deploy/compose.yml up -d`). Your data stays in the volume. |
| Desktop app | Download the new `Luna-Setup-<version>.exe` from Releases, quit Luna (including the tray icon), and run it. Settings and chats are kept. |
| From source | `git pull`, `npm install`, `pip install -r server/requirements.txt`, then restart the server. |

Building installers yourself: `npm run build:desktop` writes `dist/desktop/Luna-Setup-<version>.exe`. All build output goes under `dist/<target>/` (desktop, android, ios, server) and is never committed.

## Troubleshooting

- **"Luna's server isn't running" in the app:** with Docker, check `docker ps` and `docker logs luna`. From source, check the terminal running `npm run web`.
- **The `ts.net` address doesn't load:** Tailscale must be on and signed in on both devices, and `tailscale serve status` on the server should list port 8899.
- **Luna keeps asking for a token from your phone:** that phone is signed in to a different Tailscale account, or the server runs in Docker (see above).
- **PowerShell drops the `--`** in `npm run luna -- …`: use the dedicated scripts (`npm run serve:tailscale`, `npm run chat`, `npm run setup`).
- **Voice, meeting mode or microphone don't work in the browser:** the page must be HTTPS (the `ts.net` address) or `localhost`; browsers block the microphone elsewhere.

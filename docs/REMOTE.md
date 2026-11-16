# Using Luna from another device (Tailscale)

Step-by-step setup for every kind of install is in [SETUP.md](SETUP.md#4-use-it-from-your-other-devices-remote-over-tailscale). This page has the details.

Run Luna's server on one computer and use it from your laptop, phone or browser anywhere, over your private [Tailscale](https://tailscale.com) network. Nothing is exposed to the public internet.

## 1. Share the server

On the computer that runs Luna (Tailscale installed and signed in):

```bash
luna serve --tailscale        # or, without the global `luna` command:
npm run serve:tailscale       # works in PowerShell too
```

In PowerShell, avoid `npm run luna -- serve --tailscale`: PowerShell drops the `--`, so npm swallows `--tailscale` and the server starts without sharing.

This starts the server and runs `tailscale serve` so it's reachable at `https://<this-computer>.<your-tailnet>.ts.net:8899`, by devices on your tailnet only. It prints that URL and Luna's **access token**.

- Luna keeps listening on `127.0.0.1`. Tailscale forwards to it, so leave `host=127.0.0.1` in `.env`.
- It uses HTTPS port 8899, so other `tailscale serve` mappings (for example Ollama on 443) are left alone. Pick another with `--https=<port>`.
- Stop sharing with `luna serve --tailscale --off` (or `npm run serve:tailscale:off`).

## 2. Connect a client

Devices signed in to Tailscale with the **same account** as the server computer connect with nothing to copy:

| Client | How |
|---|---|
| Desktop app | Settings → Server → **Remote over Tailscale**. The app searches your tailnet and lists every shared Luna. If there's exactly one, it's picked for you. Click **Save and restart**. Switch back to **This computer** the same way. |
| Browser | Open the URL printed by `luna serve --tailscale`. |
| Mobile app | Settings → Server: enter the URL. The token field can stay empty. |

Other people on your tailnet (shared machines, other accounts) need the access token. It's printed by `luna serve --tailscale`, and the desktop app asks for it when a server shows **Needs token**.

## How access is checked

Apps on the server's own computer (desktop app, CLI, VS Code, Office) call `http://127.0.0.1:8899` and don't need anything.

Requests through `tailscale serve` are let in when either of these is true:

1. **Tailscale identity.** Tailscale adds `Tailscale-User-Login` for the signed-in user and strips any copy a client sends. The server trusts the login this computer is signed in as, plus any listed in `tailscale_trusted_logins`. It only believes the header when the connection comes from tailscaled on the same machine and isn't Funnel (public) traffic. Set `tailscale_trust_owner=false` to turn this off.
2. **Access token.** The token goes in the `X-Luna-Token` header, or `?luna_token=` for event streams.

`tailscale serve` always adds `X-Forwarded-Host`, so the server can tell proxied requests from local ones. `/api/remote/hello` is public: it tells a client "this is Luna, and you are or aren't authorized". The desktop app uses it for discovery. See [`server/core/access.py`](../server/core/access.py).

Some routes stay open without the token: `/api/system/health`, the web UI's static files, inbound webhooks that verify their own signatures (`/api/channels/*`, `/api/health/webhook/*`) and OAuth callbacks.

If you run Luna with `host=0.0.0.0` (LAN mode or Docker), other devices can also connect directly. Set `require_token_on_lan=true` in `.env` to require the token for those connections too. It's off by default so LAN mode and Docker keep working as before.

The token is in `data/local_api_token` on the server. Anyone who has it gets full access to that Luna, so treat it like a password. To rotate it, delete the file and restart the server, then reconnect your clients.

## Docker

`npm run serve:tailscale` needs a source checkout. For Docker (or the installed desktop app), share the port with Tailscale directly:

```bash
tailscale serve --bg --https=8899 http://127.0.0.1:8899
```

Tailscale's proxy reaches the container from outside it, so Luna can't tell that the connection came from tailscaled, and it doesn't trust identity headers. Every remote device uses the access token once:

```bash
docker exec luna cat /app/data/local_api_token
```

Keep the container's port on `127.0.0.1` (the default in `deploy/compose.yml`), so nothing on your network can reach Luna except through Tailscale.

## Limits

- **Google Workspace add-on:** it runs on Google's servers, which can't reach a tailnet address. It would need a public URL (`tailscale funnel`) and doesn't send the token yet.
- **VS Code and Office add-ins** have no token field yet, so they only work with a server on the same computer.

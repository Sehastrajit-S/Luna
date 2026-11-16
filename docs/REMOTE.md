# Using Luna from another device (Tailscale)

Run Luna's server on one computer and use it from your laptop, phone or browser anywhere, over your private [Tailscale](https://tailscale.com) network. Nothing is exposed to the public internet.

## 1. Share the server

On the computer that runs Luna (Tailscale installed and signed in):

```bash
luna serve --tailscale
```

This starts the server and runs `tailscale serve` so it's reachable at `https://<this-computer>.<your-tailnet>.ts.net:8899`, by devices on your tailnet only. It prints that URL and Luna's **access token**.

- Luna keeps listening on `127.0.0.1`. Tailscale forwards to it, so leave `host=127.0.0.1` in `.env`.
- It uses HTTPS port 8899, so other `tailscale serve` mappings (for example Ollama on 443) are left alone. Pick another with `--https=<port>`.
- Stop sharing with `luna serve --tailscale --off`.

## 2. Connect a client

| Client | How |
|---|---|
| Desktop app | Settings → Server → **Remote over Tailscale**, paste the URL and token, **Test connection**, then **Save and restart**. Switch back to **This computer** the same way. |
| Browser | Open the `…/#token=…` link printed by `luna serve --tailscale` once. The token is kept in that browser. |
| Mobile app | Settings → Server: enter the URL and access token. |

The device must be signed in to the same tailnet.

## How access is checked

Apps on the server's own computer (desktop app, CLI, VS Code, Office) call `http://127.0.0.1:8899` and don't need the token.

Requests that arrive through a proxy must send the token in the `X-Luna-Token` header, or as `?luna_token=` for event streams. `tailscale serve` always adds `X-Forwarded-Host`, and it strips any `Tailscale-*` headers a client tries to send, so the server can tell these requests apart. See [`server/core/access.py`](../server/core/access.py).

Some routes stay open without the token: `/api/system/health`, the web UI's static files, inbound webhooks that verify their own signatures (`/api/channels/*`, `/api/health/webhook/*`) and OAuth callbacks.

If you run Luna with `host=0.0.0.0` (LAN mode or Docker), other devices can also connect directly. Set `require_token_on_lan=true` in `.env` to require the token for those connections too. It's off by default so LAN mode and Docker keep working as before.

The token is in `data/local_api_token` on the server. Anyone who has it gets full access to that Luna, so treat it like a password. To rotate it, delete the file and restart the server, then reconnect your clients.

## Limits

- **Google Workspace add-on:** it runs on Google's servers, which can't reach a tailnet address. It would need a public URL (`tailscale funnel`) and doesn't send the token yet.
- **VS Code and Office add-ins** have no token field yet, so they only work with a server on the same computer.

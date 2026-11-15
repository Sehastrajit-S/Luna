"""
Messaging channel webhooks — Telegram, Discord, Slack, GitHub, generic HTTP.

Setup summary
─────────────
Telegram
  1. Set  telegram_bot_token  in .env
  2. Register webhook:
       curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://YOUR_HOST/api/channels/telegram"
  3. Luna replies to every text message sent to the bot.

Discord
  1. Set  discord_bot_token  and  discord_public_key  in .env
  2. In the Discord Developer Portal → Interactions Endpoint URL:
       https://YOUR_HOST/api/channels/discord
  3. Luna replies to APPLICATION_COMMAND and MESSAGE_COMPONENT interactions.

Slack
  1. Set  slack_bot_token  and  slack_signing_secret  in .env
  2. In your Slack App config → Event Subscriptions → Request URL:
       https://YOUR_HOST/api/channels/slack
  3. Subscribe to  message.channels  (or  message.im  for DMs).

GitHub
  1. Set  github_token  (PAT with repo scope) and  github_webhook_secret  in .env
  2. In your repo/org → Settings → Webhooks → Add webhook:
       Payload URL: https://YOUR_HOST/api/channels/github
       Content type: application/json
       Secret: same value as github_webhook_secret
  3. Tick push, pull_request, issues, issue_comment, release events.
  4. Optionally set github_notify_slack_channel or github_notify_telegram_chat_id
     in .env to forward event summaries to a notification channel.

Generic webhook
  POST /api/channels/webhook
  Body: { "user_id": "...", "user_name": "...", "text": "..." }
  Returns: { "reply": "..." }
"""
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.services.channel_bridge import (
    handle_channel_message,
    send_telegram,
    send_discord,
    send_slack,
)

router = APIRouter(prefix="/api/channels", tags=["channels"])


# ── Telegram ──────────────────────────────────────────────────────────────────

@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Telegram Bot API update endpoint."""
    if not settings.telegram_bot_token:
        raise HTTPException(503, "Telegram not configured")

    body = await request.json()
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}  # ignore non-message updates (reactions, etc.)

    text = message.get("text", "").strip()
    if not text:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", chat_id))
    first = from_user.get("first_name", "")
    last = from_user.get("last_name", "")
    user_display = f"{first} {last}".strip() or f"user_{user_id}"

    async def _reply():
        reply = await handle_channel_message("telegram", user_id, user_display, text)
        await send_telegram(chat_id, reply)

    background_tasks.add_task(_reply)
    return {"ok": True}


# ── Discord ───────────────────────────────────────────────────────────────────

def _verify_discord_signature(body: bytes, signature: str, timestamp: str) -> bool:
    if not settings.discord_public_key:
        return True
    try:
        from nacl.signing import VerifyKey
        from nacl.exceptions import BadSignatureError
        vk = VerifyKey(bytes.fromhex(settings.discord_public_key))
        vk.verify((timestamp + body.decode()).encode(), bytes.fromhex(signature))
        return True
    except Exception:
        return False


@router.post("/discord")
async def discord_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature_ed25519: str = Header(default=""),
    x_signature_timestamp: str = Header(default=""),
):
    """Discord interactions endpoint."""
    if not settings.discord_bot_token:
        raise HTTPException(503, "Discord not configured")

    raw = await request.body()

    # Discord requires signature verification for all requests
    if not _verify_discord_signature(raw, x_signature_ed25519, x_signature_timestamp):
        raise HTTPException(401, "Invalid signature")

    body = json.loads(raw)
    interaction_type = body.get("type")

    # Type 1 = PING (Discord's liveness check)
    if interaction_type == 1:
        return {"type": 1}

    # Type 2 = APPLICATION_COMMAND, type 3 = MESSAGE_COMPONENT
    if interaction_type in (2, 3):
        data = body.get("data", {})
        # Slash command text or message component custom_id
        text = (
            data.get("options", [{}])[0].get("value", "")
            if data.get("options")
            else data.get("custom_id", "")
        )
        if not text:
            return {"type": 4, "data": {"content": "No message received."}}

        user = body.get("member", {}).get("user") or body.get("user", {})
        user_id = user.get("id", "unknown")
        username = user.get("username", f"user_{user_id}")
        channel_id = body.get("channel_id", "")

        # Acknowledge immediately, then send the real reply
        async def _reply():
            reply = await handle_channel_message("discord", user_id, f"@{username}", text)
            await send_discord(channel_id, reply)

        background_tasks.add_task(_reply)
        # Deferred channel message (type 5) tells Discord we'll post separately
        return {"type": 5}

    return {"type": 4, "data": {"content": "Unsupported interaction type."}}


# ── Slack ─────────────────────────────────────────────────────────────────────

def _verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if not settings.slack_signing_secret:
        return True
    if abs(time.time() - int(timestamp)) > 300:
        return False
    base = f"v0:{timestamp}:{body.decode()}"
    computed = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        base.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


@router.post("/slack")
async def slack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_slack_request_timestamp: str = Header(default="0"),
    x_slack_signature: str = Header(default=""),
):
    """Slack Events API endpoint."""
    if not settings.slack_bot_token:
        raise HTTPException(503, "Slack not configured")

    raw = await request.body()

    if not _verify_slack_signature(raw, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(401, "Invalid Slack signature")

    body = json.loads(raw)

    # Slack URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body["challenge"]}

    event = body.get("event", {})
    if event.get("type") not in ("message", "app_mention"):
        return {"ok": True}

    # Skip bot messages (avoid echo loops)
    if event.get("bot_id") or event.get("subtype"):
        return {"ok": True}

    text = event.get("text", "").strip()
    if not text:
        return {"ok": True}

    user_id = event.get("user", "unknown")
    channel_id = event.get("channel", "")

    async def _reply():
        reply = await handle_channel_message("slack", user_id, f"<@{user_id}>", text)
        await send_slack(channel_id, reply)

    background_tasks.add_task(_reply)
    return {"ok": True}


# ── Generic webhook ───────────────────────────────────────────────────────────

@router.post("/webhook")
async def generic_webhook(request: Request):
    """
    Generic HTTP webhook for any integration.

    Request body (JSON):
      { "user_id": "string", "user_name": "string", "text": "string" }

    Response:
      { "reply": "string" }

    """
    body = await request.json()
    user_id = str(body.get("user_id", "webhook_user"))
    user_name = str(body.get("user_name", user_id))
    text = str(body.get("text", "")).strip()

    if not text:
        raise HTTPException(400, "text is required")

    reply = await handle_channel_message("webhook", user_id, user_name, text)
    return {"reply": reply, "user_id": user_id}


# ── GitHub ───────────────────────────────────────────────────────────────────

def _verify_github_signature(body: bytes, signature: str) -> bool:
    """Verify the X-Hub-Signature-256 header from GitHub."""
    if not settings.github_webhook_secret:
        return True
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _format_github_event(event_type: str, body: dict) -> str | None:
    """Turn a GitHub webhook payload into a human-readable summary line."""
    repo = body.get("repository", {}).get("full_name", "unknown/repo")

    if event_type == "push":
        pusher = body.get("pusher", {}).get("name", "someone")
        ref = body.get("ref", "").replace("refs/heads/", "")
        commits = body.get("commits", [])
        if not commits:
            return None
        headline = commits[0].get("message", "").split("\n")[0]
        n = len(commits)
        return f"[GitHub] {pusher} pushed {n} commit{'s' if n != 1 else ''} to {repo}/{ref}: {headline}"

    if event_type == "pull_request":
        action = body.get("action", "")
        if action not in ("opened", "closed", "reopened", "ready_for_review"):
            return None
        pr = body.get("pull_request", {})
        number = pr.get("number")
        title = pr.get("title", "")
        user = pr.get("user", {}).get("login", "someone")
        if action == "closed" and pr.get("merged"):
            action = "merged"
        return f"[GitHub] PR #{number} '{title}' {action} in {repo} by @{user}"

    if event_type == "issues":
        action = body.get("action", "")
        if action not in ("opened", "closed", "reopened"):
            return None
        issue = body.get("issue", {})
        number = issue.get("number")
        title = issue.get("title", "")
        user = issue.get("user", {}).get("login", "someone")
        return f"[GitHub] Issue #{number} '{title}' {action} in {repo} by @{user}"

    if event_type == "issue_comment":
        if body.get("action") != "created":
            return None
        issue = body.get("issue", {})
        comment = body.get("comment", {})
        number = issue.get("number")
        user = comment.get("user", {}).get("login", "someone")
        snippet = comment.get("body", "")[:120].replace("\n", " ")
        return f"[GitHub] @{user} commented on #{number} in {repo}: {snippet}"

    if event_type == "release":
        if body.get("action") != "published":
            return None
        release = body.get("release", {})
        tag = release.get("tag_name", "")
        name = release.get("name", tag) or tag
        return f"[GitHub] Release {name} published in {repo}"

    return None


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
):
    """GitHub webhook — push, pull_request, issues, issue_comment, release."""
    if not settings.github_token and not settings.github_webhook_secret:
        raise HTTPException(503, "GitHub not configured")

    raw = await request.body()

    if settings.github_webhook_secret and not _verify_github_signature(raw, x_hub_signature_256):
        raise HTTPException(401, "Invalid GitHub signature")

    body = json.loads(raw)

    # GitHub sends a ping on first registration — acknowledge it
    if x_github_event == "ping":
        return {"ok": True, "zen": body.get("zen", "")}

    message = _format_github_event(x_github_event, body)
    if not message:
        return {"ok": True}

    async def _notify():
        # Forward to a Slack channel if configured
        if settings.slack_bot_token and settings.github_notify_slack_channel:
            await send_slack(settings.github_notify_slack_channel, message)
        # Forward to a Telegram chat if configured
        if settings.telegram_bot_token and settings.github_notify_telegram_chat_id:
            await send_telegram(settings.github_notify_telegram_chat_id, message)

    background_tasks.add_task(_notify)
    return {"ok": True, "event": x_github_event, "summary": message}


# ── Channel status ────────────────────────────────────────────────────────────

@router.get("/status")
def channel_status():
    """Returns which channels are configured."""
    return {
        "telegram": bool(settings.telegram_bot_token),
        "discord":  bool(settings.discord_bot_token and settings.discord_public_key),
        "slack":    bool(settings.slack_bot_token and settings.slack_signing_secret),
        "github":   bool(settings.github_token or settings.github_webhook_secret),
        "webhook":  True,
    }

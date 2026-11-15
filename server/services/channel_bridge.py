"""
Channel bridge — routes messages from Telegram / Discord / Slack / generic
webhooks into Luna's chat engine and returns a plain-text reply.

Each channel user gets a persistent conversation keyed by  {channel}:{user_id}.
Widgets, map commands, Spotify commands, and [LAUNCH:…] tags are stripped from
channel replies since those depend on the Electron / browser UI.
"""
import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from server.config import settings
from server.services.llm import ollama as llm


# ── per-user session (no DB dependency for lightweight channel use) ───────────

@dataclass
class ChannelSession:
    channel: str
    user_id: str
    history: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    def add(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        # Keep last 20 turns to avoid blowing the context window
        if len(self.history) > 40:
            self.history = self.history[-40:]
        self.last_active = datetime.utcnow()


_sessions: dict[str, ChannelSession] = {}

def _get_session(channel: str, user_id: str) -> ChannelSession:
    key = f"{channel}:{user_id}"
    if key not in _sessions:
        _sessions[key] = ChannelSession(channel=channel, user_id=user_id)
    return _sessions[key]


# ── command stripping ─────────────────────────────────────────────────────────

_UI_CMD_RE = re.compile(
    r"\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET|WEB_SEARCH|WEB_RESEARCH|WEB_FETCH|AWAY):[^\]]*\]",
    re.IGNORECASE,
)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _clean_for_channel(text: str) -> str:
    from server.services.response_formatter import strip_cards
    text = strip_cards(_THINK_RE.sub("", text))
    text = _UI_CMD_RE.sub("", text)
    # Collapse excess whitespace/newlines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


# ── system prompt for channel context ────────────────────────────────────────

def _channel_system_prompt(channel: str, user_display: str) -> str:
    now = datetime.now()
    is_business = settings.luna_variant == "business"

    if is_business:
        biz = settings.business_name or "the team"
        desc = f"\nOrganization: {settings.business_description}" if settings.business_description else ""
        tone_map = {
            "professional": "formal and professional",
            "friendly":     "professional but friendly",
            "technical":    "technical and detailed",
            "concise":      "extremely brief and direct",
        }
        tone = tone_map.get(settings.business_tone, "professional")
        return (
            f"You are an AI assistant for {biz}.{desc}\n"
            f"Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}.\n"
            f"You are speaking with {user_display} via {channel}.\n\n"
            f"Your tone is {tone}. "
            "Reply concisely — this is a messaging channel. "
            "No greetings, filler, or personal chat. "
            "Focus on answering the question or completing the task. "
            "Do not mention desktop features, widgets, maps, or app launchers."
        )

    try:
        from server.services.skill_manager import get_skills_prompt
        skills_block = get_skills_prompt(ui="channel")
        skills_section = f"\n## Skills\n{skills_block}\n" if skills_block and "No local" not in skills_block else ""
    except Exception:
        skills_section = ""

    return (
        f"You are Luna, an AI assistant talking to {user_display} via {channel}.\n"
        f"Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}.\n"
        f"{skills_section}\n"
        "Reply concisely — this is a messaging channel, not a desktop UI. "
        "Keep responses under 3 short paragraphs. "
        "Do not mention widgets, maps, app launchers, or desktop features. "
        "Never say you're an AI or mention your underlying model."
    )


# ── main entry point ──────────────────────────────────────────────────────────

ChannelName = Literal["telegram", "discord", "slack", "webhook", "github"]


async def handle_channel_message(
    channel: ChannelName,
    user_id: str,
    user_display: str,
    text: str,
) -> str:
    """
    Process an inbound channel message and return Luna's plain-text reply.

    Args:
        channel:      Source channel ("telegram", "discord", "slack", "webhook")
        user_id:      Stable user identifier (Telegram chat_id, Discord user snowflake, etc.)
        user_display: Human-readable name for the system prompt (e.g. "@alice")
        text:         The user's message

    Returns:
        Plain-text reply string ready to send back via the channel API.
    """
    session = _get_session(channel, str(user_id))
    session.add("user", text)

    system = _channel_system_prompt(channel, user_display)

    full = ""
    try:
        gen = await llm.stream_chat(
            session.history[:-1] + [{"role": "user", "content": text}],
            system,
            num_ctx=2048,
            num_predict=256,
            temperature=0.65,
        )
        async for token in gen:
            full += token
    except Exception as exc:
        return f"[Luna error: {exc}]"

    reply = _clean_for_channel(full) or "I didn't catch that — could you rephrase?"
    session.add("assistant", reply)
    return reply


# ── outbound helpers (used by channel routers to send replies) ────────────────

async def send_telegram(chat_id: str | int, text: str) -> bool:
    """Send a message to a Telegram chat via Bot API."""
    if not settings.telegram_bot_token:
        return False
    import httpx
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
            return r.status_code == 200
    except Exception:
        return False


async def send_discord(channel_id: str, text: str) -> bool:
    """Send a message to a Discord channel via Bot API."""
    if not settings.discord_bot_token:
        return False
    import httpx
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                url,
                headers={"Authorization": f"Bot {settings.discord_bot_token}"},
                json={"content": text[:2000]},
            )
            return r.status_code in (200, 201)
    except Exception:
        return False


async def send_slack(channel_id: str, text: str) -> bool:
    """Post a message to a Slack channel via Web API."""
    if not settings.slack_bot_token:
        return False
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {settings.slack_bot_token}",
                    "Content-Type": "application/json",
                },
                json={"channel": channel_id, "text": text},
            )
            return r.json().get("ok", False)
    except Exception:
        return False

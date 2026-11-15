"""Slack Web API client for searchable workspace context."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from backend.config import reload_settings, settings


class SlackNotConfiguredError(RuntimeError):
    """Raised when Slack credentials are missing."""


def _headers() -> dict[str, str]:
    reload_settings()
    if not settings.slack_bot_token:
        raise SlackNotConfiguredError("Slack is not configured. Set slack_bot_token.")
    return {
        "Authorization": f"Bearer {settings.slack_bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }


def is_configured() -> bool:
    reload_settings()
    return bool(settings.slack_bot_token)


async def search_messages(query: str, count: int = 10) -> list[dict[str, Any]]:
    """Search Slack messages. Requires Slack search scopes for the token."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://slack.com/api/search.messages",
            headers=_headers(),
            params={"query": query, "count": max(1, min(count, 20)), "sort": "timestamp"},
        )
        response.raise_for_status()
        data = response.json()
    _raise_if_slack_error(data)
    matches = ((data.get("messages") or {}).get("matches") or [])
    return [
        {
            "channel": ((m.get("channel") or {}).get("name") or ""),
            "channel_id": ((m.get("channel") or {}).get("id") or ""),
            "user": m.get("username") or m.get("user") or "",
            "text": m.get("text", ""),
            "ts": m.get("ts", ""),
            "permalink": m.get("permalink", ""),
        }
        for m in matches
    ]


async def channel_history(channel_id: str, oldest: float = 0, limit: int = 20) -> list[dict[str, Any]]:
    """Read recent messages from one channel. Requires conversations.history scope."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://slack.com/api/conversations.history",
            headers=_headers(),
            params={
                "channel": channel_id,
                "oldest": oldest,
                "limit": max(1, min(limit, 100)),
                "inclusive": True,
            },
        )
        response.raise_for_status()
        data = response.json()
    _raise_if_slack_error(data)
    return [
        {
            "user": msg.get("user", ""),
            "text": msg.get("text", ""),
            "ts": msg.get("ts", ""),
            "datetime": _ts_to_iso(msg.get("ts", "")),
        }
        for msg in data.get("messages", [])
    ]


def _raise_if_slack_error(data: dict[str, Any]) -> None:
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown_error')}")


def _ts_to_iso(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return ""

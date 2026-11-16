"""Turning "add it so I remember" into a real task/event — never a claimed one.

Small models often answer "your reminder's set" without emitting the [TASK]/
[EVENT] command that actually saves it. When the user asked for it, or the
reply claims it happened, but no command exists, the details are extracted
from the conversation and turned into the command (or the reply is corrected).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

EXTRACT_TIMEOUT_S = 20.0
MAX_REQUEST_CHARS = 600
MAX_CLAIM_CHARS = 400      # "your reminder's set" is one line; long answers aren't claims

# The user asks for something to be saved / reminded.
ADD_REQUEST_RE = re.compile(
    # "remind me to …", not "remind me: what's the project called?" / "remind me of …" (recall questions)
    r"\bremind\s+me\b(?!\s*[:,]?\s*(?:what|which|who|whom|whose|how|where|why|of|again)\b)"
    r"|\bset\s+(?:a\s+|an\s+)?(?:reminder|alarm)\b|\bso\s+(?:that\s+)?i\s+(?:can\s+|will\s+|'ll\s+|don'?t\s+)?(?:remember|forget)\b"
    # "add/put/schedule … <calendar word>" — a scheduling noun is required, so
    # "make it shorter" or "add a paragraph to this" never create tasks.
    r"|\b(?:add|put|save|schedule|create|log|note|make|set\s+up)\b.{0,40}\b(?:task|event|meeting|reminder|"
    r"calendar|appointment|to-?do(?:\s+list)?|my\s+list|agenda|schedule)\b"
    # Noun first: "I have a meeting at 6 p.m. Make sure to add that."
    r"|\b(?:task|event|meeting|appointment|call|class|deadline|interview)\b.{0,120}"
    r"\b(?:add|put|save|schedule|note|log)\s+(?:it|that|this)\b",
    re.IGNORECASE | re.DOTALL,
)
_WHEN = (r"(?:\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)|noon|midnight|today|tonight|tomorrow"
         r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b")

# The reply claims it was saved.
CLAIM_RE = re.compile(
    # Only scheduling claims — "I've added the function" in a coding reply is not one.
    r"\breminder(?:'s|\s+is|\s+has\s+been)?\s+set\b"
    r"|\b(?:added|scheduled|saved|set|created|put|noted)\b.{0,40}\b(?:reminder|calendar|task|event|meeting|to-?do|"
    r"your\s+list|agenda)\b"
    # Noun first: "your meeting is scheduled for 6 PM", "the task has been added".
    r"|\b(?:reminder|task|event|meeting|appointment|call)\s+(?:is|'s|has\s+been|was)\s+(?:now\s+|all\s+)?"
    r"(?:scheduled|set|added|saved|booked|created|noted)\b"
    r"|\b(?:it'?s|that'?s|it\s+is)\s+(?:on|in)\s+your\s+(?:calendar|list|tasks|to-?do)"
    # Future / change claims: "I'll remind you to stretch at 5 PM", "moved it to 5 PM" —
    # tied to a time or day so "updated it to use async" isn't one.
    rf"|\bi(?:'ll|\s+will)\s+remind\s+you\b"
    rf"|\b(?:moved|changed|updated|rescheduled|pushed|shifted)\s+(?:it|that|this|the\s+\w+)\s+to\s+{_WHEN}",
    re.IGNORECASE,
)
COMMAND_RE = re.compile(r"\[(?:TASK|EVENT):", re.IGNORECASE)

SYSTEM = (
    "You extract one calendar item from a chat. Output only JSON: "
    '{"kind": "event" or "task", "title": short title, "datetime": "YYYY-MM-DDTHH:MM" local time or "", '
    '"duration_minutes": number}. Meetings, calls, appointments and classes are events; things to do are tasks. '
    'If the title or time is not stated, use "".'
)


def wants_saved(user_message: str, reply: str) -> bool:
    """True when something should have been saved but no command was emitted."""
    if COMMAND_RE.search(reply or ""):
        return False
    # A real "remind me / add it" request is short. A long paste (a log, an
    # article) can contain "schedule … record" by chance and must not create tasks.
    asked = len(user_message or "") <= MAX_REQUEST_CHARS and ADD_REQUEST_RE.search(user_message or "")
    return bool(asked or claims_saved(reply))


_FENCED_RE = re.compile(r"```.*?(?:```|$)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def reply_prose(reply: str) -> str:
    """The reply without code: comments and identifiers in code aren't claims."""
    return _INLINE_CODE_RE.sub(" ", _FENCED_RE.sub(" ", reply or "")).strip()


def claims_saved(reply: str) -> bool:
    """A short reply saying something was saved. A long answer (an explanation,
    code) that happens to say "created … task" is not a claim, and must never be
    replaced — that wiped whole code answers."""
    prose = reply_prose(reply)
    return len(prose) <= MAX_CLAIM_CHARS and bool(CLAIM_RE.search(prose))


async def extract_item(user_message: str, history: list[dict]) -> dict | None:
    """{"kind", "title", "datetime", "duration_minutes"} from the conversation, or None."""
    now = datetime.now()
    turns = [m for m in history if m.get("content")][-4:]
    transcript = "\n".join(f"{'User' if m['role'] == 'user' else 'Luna'}: {' '.join(m['content'].split())[:300]}"
                           for m in turns)
    prompt = (
        f"Now: {now:%A %Y-%m-%d %H:%M} (local time).\n\n"
        + (f"Conversation:\n{transcript}\n\n" if transcript else "")
        + f"Latest user message: {user_message[:400]}\n\nJSON:"
    )
    try:
        from server.services.llm import ollama
        raw = await asyncio.wait_for(ollama.complete(prompt=prompt, system=SYSTEM, temperature=0.0), EXTRACT_TIMEOUT_S)
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        data = json.loads(match.group(0)) if match else None
    except Exception as e:
        logger.warning("Schedule extraction failed: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    title = " ".join(str(data.get("title") or "").split())[:120]
    when = str(data.get("datetime") or "").strip()
    try:
        parsed = datetime.fromisoformat(when) if when else None
    except ValueError:
        parsed = None
    kind = "event" if str(data.get("kind", "")).lower() == "event" else "task"
    try:
        duration = max(5, min(int(data.get("duration_minutes") or 60), 24 * 60))
    except (TypeError, ValueError):
        duration = 60
    return {"kind": kind, "title": title, "datetime": parsed, "duration_minutes": duration}


def to_command(item: dict) -> str | None:
    """The bracket command that saves the item, or None if details are missing."""
    if not item or not item.get("title"):
        return None
    when = item.get("datetime")
    if item["kind"] == "event":
        if not when:
            return None
        return f"[EVENT:{item['title']}|{when.isoformat(timespec='minutes')}|{item['duration_minutes']}]"
    return f"[TASK:{item['title']}|{when.isoformat(timespec='minutes') if when else ''}|medium]"

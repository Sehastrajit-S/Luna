"""Routing-decision log: the training data for a learned router.

Luna makes many small decisions with hand-written rules: is this multi-step,
is it a save request, did the reply claim an action, crew or not. Each rule has
misfired at some point. To replace them with a small trained classifier, we
first need examples: every chat turn appends one JSON line with the message,
the route that handled it, the tools used, and what every rule decided. When
the user's next message reads as a correction or a repeat, a feedback line
marks the previous turn, so bad decisions can be relabelled before training.

Stored locally under DATA_DIR/decisions/, one file per month. Nothing leaves
the machine. Turn off with DECISION_LOG_ENABLED=false.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from server.config import DATA_DIR, settings

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
MAX_TEXT_CHARS = 2000
MAX_REPLY_CHARS = 1000

_CORRECTION_RE = re.compile(
    r"\b(?:that'?s\s+(?:wrong|not\s+(?:it|right|what\s+i))|you'?re\s+wrong|not\s+what\s+i\s+(?:said|meant|asked)"
    r"|i\s+(?:didn'?t|did\s+not)\s+(?:say|ask)|you\s+misunderstood|wrong\s+answer|no,?\s+i\s+(?:meant|said|asked)"
    r"|why\s+(?:did|would)\s+you|that\s+didn'?t\s+work|it\s+didn'?t\s+(?:work|save|open))\b",
    re.IGNORECASE,
)
_THANKS_RE = re.compile(r"^\s*(?:thanks|thank\s+you|ty|perfect|great|nice|awesome|that\s+works)\b", re.IGNORECASE)


def _log_path(now: datetime) -> Path:
    return DATA_DIR / "decisions" / f"decisions-{now:%Y-%m}.jsonl"


def _append(record: dict) -> None:
    now = datetime.now(timezone.utc)
    record = {"ts": now.isoformat(timespec="seconds"), **record}
    path = _log_path(now)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with _LOCK, path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        logger.warning("Decision log write failed: %s", e)


def signals_for(user_message: str, reply: str) -> dict:
    """What each hand-written rule decides for this turn (the labels to learn)."""
    from server.services.agent_loop.routing import is_multi_step
    from server.services.agents import is_crew_request
    from server.services.chat_pipeline.stage_generate import _WORKSPACE_WORK_RE
    from server.services.chat_pipeline.stage_tools import _promises_lookup
    from server.services.command_parser import is_coding_request
    from server.services.command_parser.schedule import ADD_REQUEST_RE, MAX_REQUEST_CHARS, claims_saved

    text = user_message or ""
    return {
        "multi_step": is_multi_step(text),
        "crew_heuristic": is_crew_request(text),
        "crew_explicit": is_crew_request(text, explicit_only=True),
        "coding_request": is_coding_request(text),
        "workspace_work": bool(_WORKSPACE_WORK_RE.search(text)),
        "save_request": len(text) <= MAX_REQUEST_CHARS and bool(ADD_REQUEST_RE.search(text)),
        "reply_claims_saved": claims_saved(reply or ""),
        "reply_promises_lookup": _promises_lookup(reply or "", text),
    }


def feedback_signal(user_message: str) -> str | None:
    """How the user's message reacts to the previous reply, if it clearly does."""
    if _CORRECTION_RE.search(user_message or ""):
        return "correction"
    if _THANKS_RE.search(user_message or ""):
        return "positive"
    return None


def record_turn(ctx, turn: int, previous_user_message: str | None = None) -> None:
    """One line per chat turn, plus a feedback line on the previous turn when the user reacted to it."""
    if not settings.decision_log_enabled:
        return
    try:
        from server.core.logging import request_id_var
        request_id = request_id_var.get("")
    except Exception:
        request_id = ""
    conversation_id = getattr(ctx.conv, "id", None)
    user_message = ctx.user_message or ""

    signal = feedback_signal(user_message)
    if previous_user_message and user_message.strip().lower() == previous_user_message.strip().lower():
        signal = "repeat"                        # asked the same thing again: the last answer didn't land
    if signal and turn > 1:
        _append({"type": "feedback", "conversation_id": conversation_id, "turn": turn - 1, "signal": signal,
                 "text": user_message[:MAX_TEXT_CHARS]})

    try:
        signals = signals_for(user_message, ctx.full_response)
    except Exception as e:                       # a rule failing must not lose the record
        logger.debug("Decision signals failed: %s", e)
        signals = {}
    _append({
        "type": "turn",
        "request_id": request_id,
        "conversation_id": conversation_id,
        "turn": turn,
        "source": "voice" if ctx.voice else "cli" if ctx.cli else "text",
        "text": user_message[:MAX_TEXT_CHARS],
        "reply": (ctx.full_response or "")[:MAX_REPLY_CHARS],
        "route": getattr(ctx, "route", "") or "unknown",
        "tools": list(getattr(ctx, "tools_used", None) or []),
        "tool_errors": int(getattr(ctx, "tool_errors", 0) or 0),
        "attachments": len(getattr(ctx, "attachment_ids", None) or []),
        "signals": signals,
    })

"""
finalize stage — Emit SSE response, persist assistant message, queue background tasks.
"""
import json
import logging
import re
from pathlib import Path

from fastapi import BackgroundTasks

from backend.config import settings
from backend.models.database import Message
from backend.services.command_parser import parse_commands, execute_commands
from backend.services.chat_background import post_conversation_processing, track_activity_bg
from backend.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)

_CHAT_LOG = Path("data/chat.log")
_CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
STRIP_RE = r"\s*\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET|FACE|WEB_SEARCH|WEB_RESEARCH|WEB_FETCH):[^\]]+\]"


def _chat_print(line: str):
    """Write to chat log file and stdout."""
    print(line, flush=True)
    try:
        with open(_CHAT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


async def finalize(ctx: ChatContext, background_tasks: BackgroundTasks) -> None:
    """
    Persist assistant response, log, emit remaining SSE, schedule background work.
    """
    full_response = ctx.full_response

    # ── Log to chat log ───────────────────────────────────────────────────────
    _src = "voice" if ctx.voice else "cli" if ctx.cli else "text"
    _chat_print(f"\n[chat] {settings.user_name} ({_src}): {ctx.user_message}")

    _cli_text = re.sub(STRIP_RE, "", full_response).strip()
    _cli_text = re.sub(r"<think>.*?</think>", "", _cli_text, flags=re.DOTALL).strip()
    if _cli_text:
        _chat_print(f"[chat] Luna: {_cli_text}")

    # ── Persist assistant message ─────────────────────────────────────────────
    luna_msg = Message(conversation_id=ctx.conv.id, role="assistant", content=full_response)
    ctx.db.add(luna_msg)
    ctx.conv.message_count += 1
    ctx.db.commit()

    # ── Parse UI commands from response ───────────────────────────────────────
    commands = parse_commands(full_response, user_message=ctx.user_message)
    if ctx.gmail_widget_cmd and not any(c.get("kind") == "emails" for c in commands):
        commands.append(ctx.gmail_widget_cmd)
    if commands:
        ctx.emit_sse({"type": "commands", "commands": commands})
        execute_commands(commands, ctx.db, ctx.conv.id)

    # ── Schedule background tasks ─────────────────────────────────────────────
    background_tasks.add_task(
        post_conversation_processing,
        ctx.db, ctx.conv.id, full_response, ctx.prev_luna or "", ctx.user_message,
        ctx.tool_succeeded, ctx.task_completed, False,
    )
    background_tasks.add_task(track_activity_bg, ctx.user_message, ctx.conv.id)

    # ── Emit final done event ─────────────────────────────────────────────────
    ctx.emit_sse({"type": "done", "conversation_id": ctx.conv.id})

    logger.debug(
        "Finalized conv=%d, response_len=%d, tool_call=%s",
        ctx.conv.id, len(full_response), ctx.had_tool_call,
    )

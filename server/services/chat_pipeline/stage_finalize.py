"""
finalize stage — Emit SSE response, persist assistant message, queue background tasks.
"""
import json
import logging
import re
from pathlib import Path

from fastapi import BackgroundTasks

from server.config import DATA_DIR, settings
from server.models.database import Message
from server.services.command_parser import parse_commands, execute_commands
from server.services.chat_background import post_conversation_processing, track_activity_bg
from server.services.chat_pipeline.context import ChatContext
from server.services.response_formatter import strip_cards

logger = logging.getLogger(__name__)

_CHAT_LOG = DATA_DIR / "chat.log"
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

    # ── Log to chat log (never for a temporary chat) ─────────────────────────
    if not ctx.temporary:
        _src = "voice" if ctx.voice else "cli" if ctx.cli else "text"
        _chat_print(f"\n[chat] {settings.user_name} ({_src}): {ctx.user_message}")

        _cli_text = strip_cards(re.sub(STRIP_RE, "", full_response)).strip()
        _cli_text = re.sub(r"<think>.*?</think>", "", _cli_text, flags=re.DOTALL).strip()
        if _cli_text:
            _chat_print(f"[chat] Luna: {_cli_text}")

    # ── Persist assistant message ─────────────────────────────────────────────
    luna_msg = Message(conversation_id=ctx.conv.id, role="assistant", content=full_response)
    ctx.db.add(luna_msg)
    ctx.conv.message_count += 1
    ctx.db.commit()

    # Code Luna wrote becomes part of the conversation's working state.
    if "```" in full_response:
        try:
            from server.services.session_state import record_artifacts
            record_artifacts(ctx.db, ctx.conv.id, luna_msg.id, ctx.user_message, full_response)
        except Exception as e:
            logger.warning("Could not record code artifacts: %s", e)

    # ── Routing-decision log (training data for a learned router; not for temporary chats) ──
    if not ctx.temporary:
        try:
            from server.services.decision_log import record_turn
            user_turns = [m.content for m in ctx.db.query(Message.content)
                          .filter(Message.conversation_id == ctx.conv.id, Message.role == "user")
                          .order_by(Message.id)]
            record_turn(ctx, turn=len(user_turns), previous_user_message=user_turns[-2] if len(user_turns) > 1 else None)
        except Exception as e:
            logger.warning("Decision log failed: %s", e)

    # ── Parse UI commands from response ───────────────────────────────────────
    commands = parse_commands(full_response, user_message=ctx.user_message)
    if ctx.gmail_widget_cmd and not any(c.get("kind") == "emails" for c in commands):
        commands.append(ctx.gmail_widget_cmd)
    if commands:
        ctx.emit_sse({"type": "commands", "commands": commands})
        execute_commands(commands, ctx.db, ctx.conv.id)

    # ── Schedule background tasks ─────────────────────────────────────────────
    # A temporary chat teaches Luna nothing: no fact extraction, summaries,
    # mood learning or activity tracking.
    if ctx.temporary:
        ctx.emit_sse({"type": "done", "conversation_id": ctx.conv.id, "route": ctx.route or "unknown", "temporary": True})
        return
    background_tasks.add_task(
        post_conversation_processing,
        ctx.db, ctx.conv.id, full_response, ctx.prev_luna or "", ctx.user_message,
        ctx.tool_succeeded, ctx.task_completed, False,
        skip_llm_work=ctx.small_talk,
    )
    if not ctx.small_talk:
        # Activity tracking classifies the message with the LLM — nothing to
        # learn from "hi" or "thanks".
        background_tasks.add_task(track_activity_bg, ctx.user_message, ctx.conv.id)

    # ── Emit final done event ─────────────────────────────────────────────────
    ctx.emit_sse({"type": "done", "conversation_id": ctx.conv.id, "route": ctx.route or "unknown"})

    logger.debug(
        "Finalized conv=%d, response_len=%d, tool_call=%s",
        ctx.conv.id, len(full_response), ctx.had_tool_call,
    )

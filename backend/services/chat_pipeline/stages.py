"""
Pipeline runner — orchestrates all chat stages in sequence.
"""
import asyncio
import json
import logging
import re
from typing import AsyncGenerator

from fastapi import BackgroundTasks

from backend.services.chat_pipeline.context import ChatContext
from backend.services.chat_pipeline.stage_persist import persist
from backend.services.chat_pipeline.stage_context import build_context
from backend.services.chat_pipeline.stage_dispatch import dispatch_direct_commands
from backend.services.chat_pipeline.stage_generate import generate
from backend.services.chat_pipeline.stage_tools import process_tools
from backend.services.chat_pipeline.stage_finalize import finalize

logger = logging.getLogger(__name__)


async def run_pipeline(ctx: ChatContext, background_tasks: BackgroundTasks) -> AsyncGenerator[str, None]:
    """
    Execute the chat pipeline stages in order and yield SSE events.

    This is the single entry point that replaces the monolithic chat_stream function.
    Each stage mutates the ChatContext; SSE events are yielded as they're produced.
    """

    # ── Stage 1: Persist user message ─────────────────────────────────────────
    await persist(ctx)

    # Emit conversation meta
    yield _sse({"conversation_id": ctx.conv.id, "type": "meta"})

    # ── Stage 2: Build context ────────────────────────────────────────────────
    await build_context(ctx)

    # Emit proactive message if any
    if ctx.proactive_message:
        yield _sse({"type": "proactive", "message": ctx.proactive_message})

    # ── Stage 3: Dispatch direct commands ─────────────────────────────────────
    await dispatch_direct_commands(ctx)

    # ── Stage 4: Generate LLM response (if not dispatched) ────────────────────
    if not ctx.dispatched:
        # For streaming stages, we need to flush SSE events as they're produced.
        # The generate stage queues events in ctx.sse_events.
        await generate(ctx)

        # Flush any SSE events from generate (coding agent tokens, plans, etc.)
        for event in ctx.sse_events:
            yield _sse(event)
        ctx.sse_events.clear()

    # ── Stage 5: Process tool calls ───────────────────────────────────────────
    await process_tools(ctx)

    # Flush any SSE events from tools (confirmation_required, etc.)
    for event in ctx.sse_events:
        yield _sse(event)
    ctx.sse_events.clear()

    # ── Stage 6: Stream visible response to client ────────────────────────────
    # (Only if not already streamed by generate stage for voice/coding)
    if not (ctx.voice_streamed and not ctx.had_tool_call):
        visible_events = _build_visible_response_events(ctx)
        for event in visible_events:
            yield event

    # ── Stage 7: Finalize ─────────────────────────────────────────────────────
    await finalize(ctx, background_tasks)

    # Flush finalize SSE events (commands, done)
    for event in ctx.sse_events:
        yield _sse(event)
    ctx.sse_events.clear()


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _build_visible_response_events(ctx: ChatContext) -> list[str]:
    """
    Build SSE events for the visible chat response text.
    Splits response into parts with delays for non-voice/non-CLI mode.
    """
    STRIP_RE = r"\s*\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET|FACE|WEB_SEARCH|WEB_RESEARCH|WEB_FETCH):[^\]]+\]"
    full_response = ctx.full_response

    visible_text = re.sub(STRIP_RE, "", full_response).strip()
    if ctx.cli:
        visible_text = _plain_terminal_format(visible_text)
    _max_parts = 10 if ctx.had_tool_call else 2

    refs_match = re.search(r"\n\s*References:\s*", visible_text, flags=re.IGNORECASE)
    if refs_match:
        body_text = visible_text[:refs_match.start()].strip()
        refs_text = visible_text[refs_match.start():].strip()
        body_parts = [p.strip() for p in re.split(r"\n{2,}", body_text) if p.strip()]
        visible_parts = body_parts[:_max_parts] + ([refs_text] if refs_text else [])
    else:
        visible_parts = [p.strip() for p in re.split(r"\n{2,}", visible_text) if p.strip()][:_max_parts]

    if not visible_parts:
        visible_parts = [full_response] if full_response else [""]

    events = []
    for index, part in enumerate(visible_parts):
        content = f"\n\n{part}" if ctx.cli and index > 0 else part
        events.append(_sse({"type": "message_part", "content": content}))

    return events


def _plain_terminal_format(text: str) -> str:
    """Remove markdown emphasis markers that read poorly in terminal chat."""
    text = re.sub(r"\*\*([^*\n][\s\S]*?[^*\n])\*\*", r"\1", text)
    text = re.sub(r"__([^_\n][\s\S]*?[^_\n])__", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    return text

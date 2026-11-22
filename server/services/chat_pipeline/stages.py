"""
Pipeline runner — orchestrates all chat stages in sequence.
"""
import asyncio
import json
import logging
import re
from typing import AsyncGenerator

from fastapi import BackgroundTasks

from server.services.chat_pipeline.context import ChatContext
from server.services.chat_pipeline.stage_persist import persist
from server.services.chat_pipeline.stage_context import build_context
from server.services.chat_pipeline.stage_dispatch import dispatch_direct_commands
from server.services.chat_pipeline.stage_generate import generate
from server.services.chat_pipeline.stage_tools import process_tools
from server.services.chat_pipeline.stage_finalize import finalize
from server.services.chat_pipeline.stage_small_talk import answer_small_talk
from server.services.agent_loop import agent_loop_applies, run_agent_turn
from server.services.response_formatter import strip_cards

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

    # ── Small talk fast path ("hi", "good morning", "thanks") ─────────────────
    # Answered without the LLM: skips context build, dispatch, generate, tools.
    if answer_small_talk(ctx):
        ctx.route = "small_talk"
    else:
        # ── Stage 2: Build context ────────────────────────────────────────────
        await build_context(ctx)

        # Emit proactive message if any
        if ctx.proactive_message:
            yield _sse({"type": "proactive", "message": ctx.proactive_message})

        # ── Stage 3: Dispatch direct commands ─────────────────────────────────
        # Streamed live: a shortcut can ask for approval and wait for the answer.
        async for event in _live(ctx, dispatch_direct_commands(ctx)):
            yield event

        # ── Stage 4: Agent loop (native tool calling, many steps) ─────────────
        if ctx.dispatched:
            ctx.route = f"shortcut:{ctx.direct_command_type or 'unknown'}"
        if agent_loop_applies(ctx):
            ctx.route = "agent_loop"
            async for event in run_agent_turn(ctx):
                yield _sse(event)
            for event in ctx.sse_events:
                yield _sse(event)
            ctx.sse_events.clear()

        # ── Stage 4 (fallback): single-shot generate + one tool call ──────────
        elif not ctx.dispatched:
            from server.services.chat_pipeline.stage_generate import uses_special_agent
            ctx.route = "special_agent" if uses_special_agent(ctx) else "single_shot"
            # For streaming stages, we need to flush SSE events as they're produced.
            # The generate stage queues events in ctx.sse_events.
            await generate(ctx)

            # Flush any SSE events from generate (coding agent tokens, plans, etc.)
            for event in ctx.sse_events:
                yield _sse(event)
            ctx.sse_events.clear()

            # ── Stage 5: Process the one tool call in the reply ───────────────
            # Streamed live: confirmation_required must reach the client while the
            # stage waits for the answer, not after the wait has timed out.
            async for event in _live(ctx, process_tools(ctx)):
                yield event

    # ── Stage 6: Stream visible response to client ────────────────────────────
    # (Only if not already streamed by generate stage for voice/coding)
    # The agent loop streams voice/CLI text live (reply_streamed); nothing to resend.
    if not ctx.reply_streamed and not (ctx.voice_streamed and not ctx.had_tool_call):
        visible_events = _build_visible_response_events(ctx)
        for event in visible_events:
            yield event

    # ── Stage 7: Finalize ─────────────────────────────────────────────────────
    await finalize(ctx, background_tasks)

    # Flush finalize SSE events (commands, done)
    for event in ctx.sse_events:
        yield _sse(event)
    ctx.sse_events.clear()


async def _live(ctx: ChatContext, work) -> AsyncGenerator[str, None]:
    """Run a stage, sending the events it queues as they appear instead of after it ends."""
    task = asyncio.ensure_future(work)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=0.2)
            while ctx.sse_events:
                yield _sse(ctx.sse_events.pop(0))
            if done:
                task.result()   # re-raise a stage error
                return
    finally:
        if not task.done():
            task.cancel()


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
    if ctx.cli or getattr(ctx, "voice", False):
        visible_text = strip_cards(visible_text).strip()   # cards are for rich UIs
    if ctx.cli:
        visible_text = _plain_terminal_format(visible_text)
    # Text chat shows the whole answer. Only spoken (voice) replies stay short —
    # capping text replies silently dropped long answers after paragraph two.
    _max_parts = 2 if getattr(ctx, "voice", False) and not ctx.had_tool_call else None

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

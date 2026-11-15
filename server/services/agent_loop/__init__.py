"""Luna's agent loop: native tool calling, many steps per request, parallel reads."""
from __future__ import annotations

from typing import AsyncGenerator

from server.services.agent_loop.loop import AgentLoop, run_agent_loop
from server.services.llm.tool_calling import native_tools_supported


def agent_loop_applies(ctx) -> bool:
    """The loop handles every model turn except crew/coding requests, which run their own agents."""
    from server.services.chat_pipeline.stage_generate import uses_special_agent
    return native_tools_supported() and not ctx.dispatched and not uses_special_agent(ctx)


async def run_agent_turn(ctx) -> AsyncGenerator[dict, None]:
    """Run the loop for this chat turn, then the usual checks on the final answer."""
    from server.services.chat_pipeline.stage_generate import attach_documents
    from server.services.chat_pipeline.stage_tools import finish_plain_reply

    messages = await attach_documents(ctx, list(ctx.messages))
    for event in ctx.sse_events:                 # e.g. an attachment error
        yield event
    ctx.sse_events.clear()
    async for event in run_agent_loop(ctx, messages):
        yield event
    await finish_plain_reply(ctx)


__all__ = ["AgentLoop", "agent_loop_applies", "run_agent_loop", "run_agent_turn"]

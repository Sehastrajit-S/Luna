"""
generate stage — LLM streaming, coding agent, and task planning.

Only runs if ctx.dispatched is False (no fast-path command handled the request).
"""
import logging
import re

from backend.config import settings
from backend.services.llm import ollama
from backend.services.command_parser import is_coding_request
from backend.services.coding_agent import stream_coding_agent
from backend.services.task_planner import is_complex_task, generate_plan, TaskPlan
from backend.services.response_formatter import format_luna_response
from backend.services.agents import is_crew_request, run_crew, CrewEventType
from backend.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)

# In-memory active plans per conversation (preserves original behavior)
_active_plans: dict[int, TaskPlan] = {}


async def generate(ctx: ChatContext) -> None:
    """
    Run LLM generation (streaming).

    This stage collects tokens into ctx.full_response_parts and ctx.full_response.
    SSE streaming events are queued in ctx.sse_events for the router to flush.
    """
    if ctx.dispatched:
        return

    conv_id = ctx.conv.id

    # ── Crew Mode (multi-agent orchestration) fast-path ───────────────────────
    if is_crew_request(ctx.user_message) and not ctx.is_business:
        ctx.voice_streamed = True
        ctx.had_tool_call = True
        await _run_crew_mode(ctx)
        return

    # ── Coding agent fast-path ────────────────────────────────────────────────
    if is_coding_request(ctx.user_message) and not ctx.is_business:
        ctx.voice_streamed = True
        async for event in stream_coding_agent(ctx.messages, auto_confirm_shell=False):
            etype = event.get("type")
            if etype == "token":
                tok = event["content"]
                ctx.full_response_parts.append(tok)
                ctx.emit_sse({"type": "message_part", "content": tok})
            elif etype == "tool_call":
                ctx.emit_sse({"type": "coding_tool_call", "tool": event["tool"], "args": event["args"]})
            elif etype == "tool_result":
                ctx.emit_sse({"type": "coding_tool_result", "tool": event["tool"], "result": event["result"]})
            elif etype == "confirmation_required":
                ctx.emit_sse({
                    "type": "confirmation_required",
                    "confirm_id": "shell_cmd",
                    "message": f"Run shell: {event['args'].get('command', '')}?",
                    "tool": event["tool"],
                    "args": event["args"],
                })
            elif etype == "error":
                ctx.emit_sse({"type": "error", "message": event["message"]})
                return

        ctx.full_response = "".join(ctx.full_response_parts)
        return

    # ── Planning mode ─────────────────────────────────────────────────────────
    plan = _active_plans.get(conv_id)
    step_messages = ctx.messages

    if plan and not plan.done:
        step_prompt = await plan.next_prompt()
        step_messages = [{"role": "user", "content": step_prompt}]
    elif is_complex_task(ctx.user_message):
        steps = await generate_plan(ctx.user_message)
        if len(steps) > 1:
            plan = TaskPlan(ctx.user_message, steps)
            _active_plans[conv_id] = plan
            ctx.emit_sse({"type": "plan", "steps": steps, "total": plan.total})
            step_prompt = await plan.next_prompt()
            step_messages = [{"role": "user", "content": step_prompt}]
        else:
            plan = None

    # ── LLM streaming ─────────────────────────────────────────────────────────
    try:
        async for token in ollama.stream_chat(
            step_messages, ctx.system_prompt,
            num_ctx=None, num_predict=None,
            temperature=0.5 if ctx.cli else 0.7,
        ):
            ctx.full_response_parts.append(token)
            if ctx.voice or ctx.cli:
                clean = re.sub(r'<think>.*?</think>', '', token, flags=re.DOTALL)
                if clean:
                    ctx.emit_sse({"type": "message_part", "content": clean})
                    ctx.voice_streamed = True
    except Exception as e:
        logger.error("LLM streaming failed: %s", e, exc_info=True)
        ctx.emit_sse({"type": "error", "message": str(e)})
        return

    ctx.full_response = format_luna_response("".join(ctx.full_response_parts))

    # ── Planning progress ─────────────────────────────────────────────────────
    if plan and not plan.done:
        plan.record_result(ctx.full_response[:80])
        if plan.done:
            ctx.task_completed = True
            _active_plans.pop(conv_id, None)
            ctx.emit_sse({"type": "plan_done", "summary": plan.progress_summary()})
        else:
            ctx.emit_sse({"type": "plan_progress", "step": plan.current, "total": plan.total})


# ── Crew Mode helper ─────────────────────────────────────────────────────────


async def _run_crew_mode(ctx: ChatContext) -> None:
    """
    Dispatch the user's request to the multi-agent crew.

    Streams agent events to the UI via ctx.sse_events. The final crew answer
    becomes ctx.full_response so downstream stages (finalize) can persist it.
    """
    final_answer = ""

    try:
        async for event in run_crew(ctx.user_message):
            payload = event.to_dict()
            etype = event.type

            if etype == CrewEventType.AGENT_TOKEN:
                # Surface agent tokens as message_part events for the chat UI.
                # Prefix with role so the UI can render an agent timeline.
                role = payload.get("role", "agent")
                content = payload.get("content", "")
                ctx.full_response_parts.append(content)
                ctx.emit_sse({
                    "type": "agent_token",
                    "role": role,
                    "content": content,
                })

            elif etype == CrewEventType.CREW_DONE:
                final_answer = payload.get("answer", "")
                ctx.emit_sse({
                    "type": "crew_done",
                    "answer": final_answer,
                    "scratchpad": payload.get("scratchpad", {}),
                })

            elif etype == CrewEventType.ERROR:
                logger.warning("Crew error: %s", payload.get("message"))
                ctx.emit_sse({"type": "agent_error", **payload})

            else:
                # All other events forwarded as-is for the UI to consume.
                ctx.emit_sse({"type": etype.value, **{k: v for k, v in payload.items() if k != "type"}})
    except Exception as e:
        logger.error("Crew mode failed: %s", e, exc_info=True)
        ctx.emit_sse({"type": "error", "message": f"Crew mode failed: {e}"})
        final_answer = f"I tried to coordinate multiple agents but ran into an issue: {e}"

    ctx.full_response = final_answer or "".join(ctx.full_response_parts) or "(no answer produced)"
    ctx.tool_succeeded = bool(final_answer)

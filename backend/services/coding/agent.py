"""
Coding agent main loop — plan + ReAct execution.

Supports all Luna LLM providers (Ollama, Anthropic, Groq, Google, etc.).
The provider used is determined by settings.coding_provider (falls back to
settings.llm_provider when empty).

Events emitted:
  {"type": "workspace_index", "summary": str}
  {"type": "plan",            "summary": str, "steps": [str]}
  {"type": "plan_step",       "index": int,   "status": "running"|"done"}
  {"type": "token",           "content": str}
  {"type": "tool_call",       "tool": str,    "args": dict}
  {"type": "tool_result",     "tool": str,    "result": str}
  {"type": "confirmation_required", "tool": str, "args": dict}
  {"type": "error",           "message": str}
  {"type": "done"}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncGenerator

import httpx

from backend.config import settings
from backend.services.coding.indexer import build_workspace_index
from backend.services.coding.parser import extract_plan, parse_tool_call, strip_tool_call
from backend.services.coding.prompts import PLAN_PROMPT, SYSTEM
from backend.services.coding.tools import WORKSPACE_ROOT, execute_coding_tool
from backend.services.llm import ollama as llm

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=5.0)

# Chars to buffer while watching for a JSON tool-call block.
# Must be >= len('{"tool_call"') == 12; 32 gives comfortable margin.
_HOLDBACK = 32
_JSON_TRIGGERS = ('{"tool_call"', '{"plan"')


# ── Provider resolution ───────────────────────────────────────────────────────

def _effective_provider() -> str:
    p = settings.coding_provider.strip().lower()
    return p if p else settings.llm_provider.strip().lower()


async def _resolve_ollama_model() -> str:
    """Return coding_model if available in Ollama, else fall back to ollama_model."""
    model = settings.coding_model
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": False},
            )
            if r.status_code == 404:
                return settings.ollama_model
    except Exception:
        pass
    return model


# ── Per-provider token streams ────────────────────────────────────────────────

async def _stream_ollama_tokens(
    model: str,
    messages: list[dict],
    system: str,
) -> AsyncGenerator[str, None]:
    from backend.services.llm import selector
    think, predict = selector.ollama_think_options(model, 8192)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": True,
        "think": think,
        "options": {
            "temperature": 0.1,
            "top_p": 0.95,
            "repeat_penalty": 1.05,
            "num_ctx": 16384,
            "num_predict": predict,
        },
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
                if data.get("done"):
                    break


async def _stream_provider_tokens(
    provider: str,
    model: str,
    messages: list[dict],
    system: str,
) -> AsyncGenerator[str, None]:
    if provider == "ollama":
        async for t in _stream_ollama_tokens(model, messages, system):
            yield t
    else:
        async for t in llm.stream_chat(messages, system, temperature=0.1):
            yield t


async def _complete_provider(
    provider: str,
    model: str,
    messages: list[dict],
    system: str,
) -> str:
    if provider == "ollama":
        from backend.services.llm import selector
        think, predict = selector.ollama_think_options(model, 512)
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "think": think,
            "options": {"temperature": 0.1, "num_ctx": 16384, "num_predict": predict},
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
        return ""
    else:
        return await llm.complete(
            messages[-1]["content"] if messages else "",
            system=system,
            temperature=0.1,
        )


# ── Main agent loop ───────────────────────────────────────────────────────────

async def stream_coding_agent(
    messages: list[dict],
    *,
    auto_confirm_shell: bool = False,
    workspace_root: Path | None = None,
) -> AsyncGenerator[dict, None]:
    provider = _effective_provider()
    coding_model = await _resolve_ollama_model() if provider == "ollama" else llm.model

    _ws_root = workspace_root or WORKSPACE_ROOT
    _ws_root.mkdir(parents=True, exist_ok=True)

    # ── Workspace index (always build, even for the default workspace) ────────
    ws_index = ""
    try:
        ws_index = build_workspace_index(_ws_root)
        summary = ws_index[:300] + "…" if len(ws_index) > 300 else ws_index
        yield {"type": "workspace_index", "summary": summary}
    except Exception:
        pass

    system_prompt = _build_system_prompt(workspace_root, ws_index)
    loop_messages = list(messages)
    max_iter = max(settings.coding_max_iterations, 20)

    # ── Phase 0: generate plan ────────────────────────────────────────────────
    plan_steps: list[str] = []
    current_step_index = 0

    try:
        plan_messages = list(loop_messages) + [{"role": "user", "content": PLAN_PROMPT}]
        plan_text = await _complete_provider(provider, coding_model, plan_messages, system_prompt)
        plan_obj = extract_plan(plan_text)
        if plan_obj:
            plan_steps = plan_obj.get("steps", [])
            yield {"type": "plan", "summary": plan_obj.get("summary", ""), "steps": plan_steps}
            steps_str = "\n".join(plan_steps)
            loop_messages = list(loop_messages) + [
                {"role": "assistant", "content": plan_text},
                {"role": "user", "content": (
                    f"Good plan. Now execute it step by step using tools.\n"
                    f"Steps:\n{steps_str}\n\n"
                    "Start with step 1 — emit a tool_call now."
                )},
            ]
    except Exception:
        pass  # plan is best-effort; execution continues without it

    # ── Phase 1+: ReAct tool loop ─────────────────────────────────────────────
    last_plan_step = -1  # last step index for which we emitted "running"
    for _iteration in range(max_iter):
        full_response = ""
        in_possible_json = False
        hold = ""

        try:
            async for token in _stream_provider_tokens(
                provider, coding_model, loop_messages, system_prompt
            ):
                full_response += token
                if in_possible_json:
                    pass  # accumulate silently
                elif any(t in hold + token for t in _JSON_TRIGGERS):
                    # Trigger found in the hold buffer — switch to JSON accumulation mode.
                    in_possible_json = True
                    combined = hold + token
                    first_brace = min(
                        combined.find(t)
                        for t in _JSON_TRIGGERS
                        if t in combined
                    )
                    pre = combined[:first_brace].strip()
                    if pre:
                        yield {"type": "token", "content": pre}
                    hold = ""
                else:
                    hold += token
                    if len(hold) > _HOLDBACK:
                        yield {"type": "token", "content": hold[:-_HOLDBACK]}
                        hold = hold[-_HOLDBACK:]

            # Flush any remaining hold content that isn't JSON
            if hold and not in_possible_json:
                yield {"type": "token", "content": hold}
                hold = ""

        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
            return

        tc = parse_tool_call(full_response)

        if not tc:
            suffix = strip_tool_call(full_response).strip()
            if suffix:
                yield {"type": "token", "content": suffix}
            if plan_steps and last_plan_step >= 0:
                yield {"type": "plan_step", "index": last_plan_step, "status": "done"}
            yield {"type": "done"}
            return

        visible = strip_tool_call(full_response).strip()
        if visible and not in_possible_json:
            yield {"type": "token", "content": visible}

        tool_name = tc.get("tool", "")
        args = tc.get("args", {})

        # ── Plan step tracking ────────────────────────────────────────────────
        # Model annotates "step": N (1-indexed); fall back to auto-increment.
        if plan_steps:
            announced = tc.get("step")
            if announced is not None:
                try:
                    target = max(0, min(int(announced) - 1, len(plan_steps) - 1))
                except (TypeError, ValueError):
                    target = current_step_index
            else:
                target = current_step_index

            if target != last_plan_step:
                if last_plan_step >= 0:
                    yield {"type": "plan_step", "index": last_plan_step, "status": "done"}
                yield {"type": "plan_step", "index": target, "status": "running"}
                last_plan_step = target
                current_step_index = target

            if announced is None:
                current_step_index = min(current_step_index + 1, len(plan_steps) - 1)

        yield {"type": "tool_call", "tool": tool_name, "args": args}

        result, needs_confirm = await execute_coding_tool(tool_name, args, workspace_root)

        if needs_confirm and not auto_confirm_shell:
            yield {"type": "confirmation_required", "tool": tool_name, "args": args}
            result = "Skipped — awaiting user confirmation before running shell command."

        # Truncate large results with a visible marker
        if len(result) > 8000:
            result_display = result[:8000] + f"\n…[truncated — {len(result) - 8000} more chars]"
        else:
            result_display = result

        yield {"type": "tool_result", "tool": tool_name, "result": result_display}

        loop_messages.append({"role": "assistant", "content": full_response})
        loop_messages.append({
            "role": "user",
            "content": f"Tool result for {tool_name}:\n{result}\n\nContinue with the next step.",
        })

    if plan_steps and last_plan_step >= 0:
        yield {"type": "plan_step", "index": last_plan_step, "status": "done"}
    yield {"type": "done"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_system_prompt(workspace_root: Path | None, ws_index: str) -> str:
    parts = [SYSTEM]
    if workspace_root:
        parts.append(
            f"\n\n## Active workspace\nPath: {workspace_root}\n"
            "All file paths are relative to this directory unless absolute.\n"
        )
    if ws_index:
        parts.append(f"\n\n## Workspace snapshot\n{ws_index}")
    return "".join(parts)

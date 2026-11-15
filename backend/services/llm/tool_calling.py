"""Native tool calling: one model step that may return tool calls.

The model gets the tool schemas in the request (Ollama `tools`, the same
function-calling shape OpenAI and Anthropic use) and answers with structured
`tool_calls` instead of JSON written into its text. Results go back as
`role: tool` messages. A small text fallback catches models that still write
the call into their reply.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import httpx

from backend.config import settings
from backend.services.llm.providers import _TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class AssistantTurn:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0      # real prompt size reported by the model server

    def as_message(self) -> dict:
        """The assistant message to append to the conversation before tool results."""
        message: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.args}}
                for c in self.tool_calls
            ]
        return message


def tool_result_message(call: ToolCall, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call.id, "tool_name": call.name, "content": content}


def native_tools_supported() -> bool:
    return settings.agent_loop_enabled and settings.llm_provider.strip().lower() == "ollama"


def _new_id() -> str:
    return f"call_{uuid.uuid4().hex[:10]}"


def _parse_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}
    return {}


_TAGGED_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def calls_from_text(content: str, known_tools: set[str]) -> tuple[str, list[ToolCall]]:
    """Tool calls a model wrote into its reply instead of calling natively."""
    from backend.services.tool_runner.parser import parse_tool_call_json, strip_tool_call_json

    calls: list[ToolCall] = []
    text = content or ""
    for match in _TAGGED_RE.finditer(text):
        try:
            data = json.loads(match.group(1))
        except ValueError:
            continue
        name = str(data.get("name") or "")
        if name in known_tools:
            calls.append(ToolCall(_new_id(), name, _parse_arguments(data.get("arguments"))))
    if calls:
        return _TAGGED_RE.sub("", text).strip(), calls

    legacy = parse_tool_call_json(text)          # {"tool_call": {"tool": …, "args": …}}
    if legacy and legacy.get("tool") in known_tools:
        return strip_tool_call_json(text).strip(), [ToolCall(_new_id(), legacy["tool"], _parse_arguments(legacy.get("args")))]

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("name") in known_tools:
            return "", [ToolCall(_new_id(), data["name"], _parse_arguments(data.get("arguments") or data.get("parameters")))]
    return text, []


async def chat_step(
    messages: list[dict],
    tools: list[dict] | None,
    *,
    temperature: float = 0.6,
    on_token: Callable[[str], Awaitable[None]] | None = None,
) -> AssistantTurn:
    """One model call with tools. Streams text tokens to `on_token` as they arrive."""
    from backend.services.llm import selector
    think, predict = selector.ollama_think_options(settings.ollama_model, settings.llm_max_output_tokens)
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": True,
        "think": think,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "num_ctx": settings.llm_context_window,
            "num_predict": predict,
        },
    }
    if tools:
        payload["tools"] = tools

    turn = AssistantTurn()
    parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream("POST", f"{settings.ollama_base_url}/api/chat", json=payload) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")[:300]
                    if selector.is_model_missing(response.status_code, body):
                        selector.on_connect_error()
                    raise RuntimeError(f"Ollama returned {response.status_code}: {body}")
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        raise RuntimeError(f"Ollama error: {data['error']}")
                    message = data.get("message") or {}
                    token = message.get("content") or ""
                    if token:
                        parts.append(token)
                        if on_token:
                            await on_token(token)
                    for raw in message.get("tool_calls") or []:
                        fn = raw.get("function") or {}
                        name = str(fn.get("name") or "")
                        if name:
                            turn.tool_calls.append(ToolCall(raw.get("id") or _new_id(), name, _parse_arguments(fn.get("arguments"))))
                    if data.get("done"):
                        turn.prompt_tokens = int(data.get("prompt_eval_count") or 0)
                        break
    except (httpx.ConnectError, httpx.ConnectTimeout):
        selector.on_connect_error()
        raise

    turn.content = "".join(parts)
    if not turn.tool_calls and tools:
        known = {t["function"]["name"] for t in tools}
        turn.content, turn.tool_calls = calls_from_text(turn.content, known)
        if turn.tool_calls:
            logger.info("Recovered %d tool call(s) written as text", len(turn.tool_calls))
    return turn

"""Per-provider streaming generators and non-streaming completions."""
import json
from typing import AsyncGenerator

import httpx

from server.config import settings
from server.services.llm.context_window import _clip_middle, estimate_tokens, fit_context

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=5.0)


def _openai_headers(api_key: str) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _ollama_unreachable() -> None:
    """Let the model selector re-probe right away when the chosen Ollama server stops answering."""
    from server.services.llm import selector
    selector.on_connect_error()


def _provider() -> str:
    return settings.llm_provider.strip().lower()


# ── streaming generators ──────────────────────────────────────────────────────

async def _stream_ollama(
    messages: list[dict],
    system_prompt: str,
    *,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    # Fixed window (Ollama reloads the model when num_ctx changes) and an
    # explicit fit so Ollama never truncates the prompt on its own. Callers that
    # already fitted (the chat pipeline) pass through unchanged.
    ctx = num_ctx or settings.llm_context_window
    max_output = num_predict or settings.llm_max_output_tokens
    from server.services.llm import selector
    think, predict = selector.ollama_think_options(settings.ollama_model, max_output)
    fitted = fit_context(system_prompt, messages, context_window=ctx, max_output_tokens=max_output)
    full_messages = [{"role": "system", "content": fitted.system_prompt}] + fitted.messages
    options = {
        "temperature": temperature,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
        "num_ctx": ctx,
        "num_predict": predict,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": full_messages,
                    "stream": True,
                    "think": think,
                    "options": options,
                },
            ) as response:
                if selector.is_model_missing(response.status_code):
                    _ollama_unreachable()
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if data.get("done"):
                        break
    except (httpx.ConnectError, httpx.ConnectTimeout):
        _ollama_unreachable()
        raise


async def _stream_openai_compatible(
    messages: list[dict],
    system_prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "model": model,
        "messages": full_messages,
        "stream": True,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/chat/completions",
            headers=_openai_headers(api_key),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content


async def _stream_anthropic(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Anthropic Messages API with server-sent events streaming."""
    payload = {
        "model": settings.anthropic_model,
        "system": system_prompt,
        "messages": messages,
        "max_tokens": 8192,
        "stream": True,
        "temperature": temperature,
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "content_block_delta":
                    text = data.get("delta", {}).get("text", "")
                    if text:
                        yield text
                elif data.get("type") == "message_stop":
                    break


async def _stream_google(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Google Gemini REST API with streaming (newline-delimited JSON)."""
    gemini_contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        gemini_contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "contents": gemini_contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 1024,
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{settings.google_model}:streamGenerateContent"
        f"?key={settings.google_api_key}&alt=sse"
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                for candidate in data.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        text = part.get("text", "")
                        if text:
                            yield text


async def _stream_groq(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Groq uses the OpenAI-compatible protocol at their own endpoint."""
    async for token in _stream_openai_compatible(
        messages,
        system_prompt,
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=temperature,
    ):
        yield token


async def _stream_cohere(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Cohere Chat API v2 with streaming."""
    cohere_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = "assistant" if m["role"] == "assistant" else "user"
        cohere_messages.append({"role": role, "content": m["content"]})

    payload = {
        "model": settings.cohere_model,
        "messages": cohere_messages,
        "stream": True,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.cohere_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            "https://api.cohere.com/v2/chat",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                event_type = data.get("type", "")
                if event_type == "content-delta":
                    text = data.get("delta", {}).get("message", {}).get("content", {}).get("text", "")
                    if text:
                        yield text
                elif event_type == "message-end":
                    break


async def _stream_mistral(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Mistral AI — OpenAI-compatible endpoint."""
    async for token in _stream_openai_compatible(
        messages,
        system_prompt,
        base_url="https://api.mistral.ai/v1",
        api_key=settings.mistral_api_key,
        model=settings.mistral_model,
        temperature=temperature,
    ):
        yield token


# ── non-streaming completions ─────────────────────────────────────────────────

async def _complete_ollama(prompt: str, system: str, temperature: float) -> str:
    ctx = settings.llm_context_window
    max_output = settings.llm_max_output_tokens
    room = ctx - max_output - 256 - estimate_tokens(system)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": _clip_middle(prompt, max(512, room))})
    from server.services.llm import selector
    think, predict = selector.ollama_think_options(settings.ollama_model, max_output)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": messages,
                    "stream": False,
                    "think": think,
                    "options": {"temperature": temperature, "num_ctx": ctx, "num_predict": predict},
                },
            )
            if selector.is_model_missing(r.status_code):
                _ollama_unreachable()
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")
    except (httpx.ConnectError, httpx.ConnectTimeout):
        _ollama_unreachable()
        raise


async def _complete_openai(
    prompt: str, system: str, temperature: float,
    base_url: str, api_key: str, model: str,
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=_openai_headers(api_key),
            json={"model": model, "messages": messages, "stream": False, "temperature": temperature},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"].get("content", "")


async def _complete_anthropic(prompt: str, system: str, temperature: float) -> str:
    payload = {
        "model": settings.anthropic_model,
        "system": system or "You are a helpful assistant.",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        r.raise_for_status()
        content = r.json().get("content", [])
        return content[0].get("text", "") if content else ""


async def _complete_google(prompt: str, system: str, temperature: float) -> str:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 512},
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{settings.google_model}:generateContent?key={settings.google_api_key}"
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        candidates = r.json().get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        return ""

"""Priority-based model selection: best Ollama model first, cloud fallback last.

Opt-in with ``llm_auto_select=true``. A background task probes every server in
``llm_ollama_servers``, ranks the chat models they serve and points
``llm_provider`` / ``ollama_base_url`` / ``ollama_model`` at the best one. Only
when no Ollama server offers a usable chat model does it switch ``llm_provider``
to ``llm_fallback_provider`` (for example openai-compatible → OpenRouter).

The rest of Luna reads those settings at call time, so chat, the agent loop,
the coding agent and the health route all follow the current choice.

Ranking (best first):
1. position in ``llm_model_preference`` (listed models beat unlisted ones),
2. native tool calling support (Luna's agent loop relies on it),
3. parameter count (bigger is better),
4. position of the server in ``llm_ollama_servers`` (tie-breaker).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT = httpx.Timeout(4.0)
_FAILURE_DEBOUNCE_SECONDS = 5.0
_UNITS = {"K": 1e-6, "M": 1e-3, "B": 1.0, "T": 1e3}


@dataclass(frozen=True)
class Candidate:
    server: str
    model: str
    params_b: float
    tools: bool


@dataclass
class SelectorState:
    source: str = "static"            # static | ollama | fallback
    server: str = ""
    model: str = ""
    checked_at: float = 0.0
    candidates: list[Candidate] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)


state = SelectorState()
_lock = asyncio.Lock()
_last_failure_probe = 0.0
_capability_cache: dict[tuple[str, str], list[str] | None] = {}
_startup_ollama_url = settings.ollama_base_url


def _split(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def servers() -> list[str]:
    configured = [s.rstrip("/") for s in _split(settings.llm_ollama_servers)]
    return configured or [_startup_ollama_url.rstrip("/")]


def parse_params(size: str) -> float:
    """'8.2B' → 8.2, '135M' → 0.135 (billions). Unknown → 0."""
    match = re.match(r"^\s*([\d.]+)\s*([KMBT])", str(size or "").upper())
    if not match:
        return 0.0
    try:
        return float(match.group(1)) * _UNITS[match.group(2)]
    except ValueError:
        return 0.0


def _looks_like_embedding(name: str, details: dict) -> bool:
    families = [str(f).lower() for f in (details.get("families") or [details.get("family") or ""])]
    return "embed" in name.lower() or any("bert" in f for f in families)


def rank_key(candidate: Candidate, preference: list[str], server_order: list[str]) -> tuple:
    def pref_index(model: str) -> int:
        bare = model.removesuffix(":latest")
        for i, wanted in enumerate(preference):
            if wanted in (model, bare) or wanted.removesuffix(":latest") == bare:
                return i
        return len(preference)

    server_index = server_order.index(candidate.server) if candidate.server in server_order else len(server_order)
    return (pref_index(candidate.model), 0 if candidate.tools else 1, -candidate.params_b, server_index)


def pick_best(candidates: list[Candidate]) -> Candidate | None:
    if not candidates:
        return None
    preference = _split(settings.llm_model_preference)
    order = servers()
    return min(candidates, key=lambda c: rank_key(c, preference, order))


async def _capabilities(client: httpx.AsyncClient, server: str, model: str, digest: str) -> list[str] | None:
    key = (server, digest or model)
    if key in _capability_cache:
        return _capability_cache[key]
    caps: list[str] | None = None
    try:
        r = await client.post(f"{server}/api/show", json={"model": model})
        if r.status_code == 200:
            raw = r.json().get("capabilities")
            caps = [str(c) for c in raw] if isinstance(raw, list) else None
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("capability probe failed for %s on %s: %s", model, server, e)
        return None  # don't cache transient failures
    _capability_cache[key] = caps
    return caps


async def probe_server(client: httpx.AsyncClient, server: str) -> list[Candidate]:
    """Chat-capable models served by one Ollama server. Raises on an unreachable server."""
    r = await client.get(f"{server}/api/tags")
    r.raise_for_status()
    found: list[Candidate] = []
    for m in r.json().get("models") or []:
        name = str(m.get("name") or m.get("model") or "")
        if not name:
            continue
        details = m.get("details") or {}
        caps = await _capabilities(client, server, name, str(m.get("digest") or ""))
        if caps is None:  # older Ollama without capabilities: infer
            if _looks_like_embedding(name, details):
                continue
            tools = False
        else:
            if "completion" not in caps:
                continue
            tools = "tools" in caps
        found.append(Candidate(server, name, parse_params(details.get("parameter_size", "")), tools))
    return found


def _apply(best: Candidate | None) -> None:
    previous = (state.source, state.server, state.model)
    if best is not None:
        settings.llm_provider = "ollama"
        settings.ollama_base_url = best.server
        settings.ollama_model = best.model
        state.source, state.server, state.model = "ollama", best.server, best.model
    else:
        fallback = settings.llm_fallback_provider.strip().lower()
        settings.llm_provider = fallback
        state.source, state.server = "fallback", ""
        state.model = settings.openai_model if fallback == "openai-compatible" else ""
    current = (state.source, state.server, state.model)
    if current != previous:
        if best is not None:
            logger.info("LLM selector: using Ollama %s on %s (%.1fB, tools=%s)",
                        best.model, best.server, best.params_b, best.tools)
        else:
            logger.warning("LLM selector: no Ollama model available on %s; falling back to %s",
                           ", ".join(servers()), settings.llm_provider)


async def select_now() -> SelectorState:
    """Probe all servers in parallel and apply the best choice."""
    async with _lock:
        order = servers()
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            results = await asyncio.gather(*(probe_server(client, s) for s in order), return_exceptions=True)
        candidates: list[Candidate] = []
        unreachable: list[str] = []
        for server, result in zip(order, results):
            if isinstance(result, BaseException):
                unreachable.append(server)
                logger.debug("LLM selector: %s unreachable: %s", server, result)
            else:
                candidates.extend(result)
        state.candidates, state.unreachable, state.checked_at = candidates, unreachable, time.time()
        _apply(pick_best(candidates))
        return state


def enabled() -> bool:
    return bool(settings.llm_auto_select)


def on_connect_error() -> None:
    """Called when an Ollama call cannot connect: re-select right away (debounced)."""
    global _last_failure_probe
    if not enabled():
        return
    now = time.monotonic()
    if now - _last_failure_probe < _FAILURE_DEBOUNCE_SECONDS:
        return
    _last_failure_probe = now
    try:
        asyncio.get_running_loop().create_task(select_now())
    except RuntimeError:
        pass


async def run_forever() -> None:
    interval = max(10, int(settings.llm_select_interval or 60))
    while True:
        try:
            await select_now()
        except Exception:  # never let the loop die
            logger.exception("LLM selector probe failed")
        await asyncio.sleep(interval)


def status() -> dict:
    return {
        "auto_select": enabled(),
        "source": state.source,
        "server": state.server,
        "model": state.model,
        "checked_at": state.checked_at,
        "unreachable": list(state.unreachable),
        "candidates": [
            {"server": c.server, "model": c.model, "params_b": c.params_b, "tools": c.tools}
            for c in sorted(state.candidates, key=lambda c: rank_key(c, _split(settings.llm_model_preference), servers()))
        ],
    }

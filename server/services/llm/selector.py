"""Priority-based model selection: best Ollama model first, cloud fallback last.

Opt-in with ``llm_auto_select=true``. A background task probes every server in
``llm_ollama_servers``, ranks the chat models they serve and points
``llm_provider`` / ``ollama_base_url`` / ``ollama_model`` at the best one. Only
when no Ollama server offers a usable chat model does it switch ``llm_provider``
to ``llm_fallback_provider`` (for example openai-compatible → OpenRouter).

The rest of Luna reads those settings at call time, so chat, the agent loop,
the coding agent and the health route all follow the current choice.

A manual choice (``set_override``) bypasses the ranking until it is cleared
with mode "auto"; it is kept in data/llm_override.json across restarts.

Ranking (best first):
1. position in ``llm_model_preference`` (listed models beat unlisted ones),
2. native tool calling support (Luna's agent loop relies on it),
3. parameter count (bigger is better),
4. position of the server in ``llm_ollama_servers`` (tie-breaker).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

from server.config import DATA_DIR, settings

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT = httpx.Timeout(4.0)
_FAILURE_DEBOUNCE_SECONDS = 5.0
_UNITS = {"K": 1e-6, "M": 1e-3, "B": 1.0, "T": 1e3}
OVERRIDE_PATH = DATA_DIR / "llm_override.json"


@dataclass(frozen=True)
class Candidate:
    server: str
    model: str
    params_b: float
    tools: bool
    always_thinks: bool = False       # thinking-only model: think=false is ignored, reasoning leaks into content


@dataclass
class SelectorState:
    source: str = "static"            # static | ollama | fallback | manual
    server: str = ""
    model: str = ""
    always_thinks: bool = False
    checked_at: float = 0.0
    candidates: list[Candidate] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)


state = SelectorState()
_lock = asyncio.Lock()
_last_failure_probe = 0.0
_capability_cache: dict[tuple[str, str], tuple[list[str] | None, bool]] = {}
_startup_ollama_url = settings.ollama_base_url


def _split(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _server_entries() -> list[tuple[str, str]]:
    """(label, url) pairs. Entries are 'url' or 'Label=url'."""
    entries = []
    for item in _split(settings.llm_ollama_servers):
        label, _, url = item.rpartition("=") if "=" in item and not item.startswith("http") else ("", "", item)
        url = url.strip().rstrip("/")
        entries.append((label.strip() or _host(url), url))
    return entries or [(_host(_startup_ollama_url), _startup_ollama_url.rstrip("/"))]


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/")[0].rsplit(":", 1)[0]


def servers() -> list[str]:
    return [url for _, url in _server_entries()]


def server_label(url: str) -> str:
    return dict((u, label) for label, u in _server_entries()).get(url, _host(url))


# ── manual override ──────────────────────────────────────────────────────────

def load_override() -> dict | None:
    try:
        data = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("mode") in {"ollama", "fallback"} else None


def fallback_ready() -> bool:
    p = settings.llm_fallback_provider.strip().lower()
    if p == "openai-compatible":
        return bool(settings.openai_api_key and settings.openai_base_url and settings.openai_model)
    return True


def fallback_label() -> str:
    p = settings.llm_fallback_provider.strip().lower()
    if p == "openai-compatible" and "openrouter.ai" in settings.openai_base_url:
        return "OpenRouter"
    return p


async def set_override(mode: str, server: str = "", model: str = "") -> SelectorState:
    """mode: auto (clear) | ollama (needs a configured server and a model it serves) | fallback."""
    mode = (mode or "").strip().lower()
    if mode == "auto":
        OVERRIDE_PATH.unlink(missing_ok=True)
    elif mode == "ollama":
        server = (server or "").rstrip("/")
        if server not in servers():
            raise ValueError("Unknown Ollama server.")
        if not model:
            raise ValueError("Pick a model.")
        _write_override({"mode": "ollama", "server": server, "model": model})
    elif mode == "fallback":
        if not fallback_ready():
            raise ValueError(f"{fallback_label()} is not configured (missing API key).")
        _write_override({"mode": "fallback"})
    else:
        raise ValueError("mode must be auto, ollama or fallback.")
    if not state.checked_at:
        return await select_now()
    async with _lock:  # instant: reuse the last probe instead of waiting on offline servers
        _apply_choice()
    return state


def _write_override(data: dict) -> None:
    OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDE_PATH.write_text(json.dumps(data), encoding="utf-8")


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


def _thinking_only(caps: list[str] | None, template: str) -> bool:
    """A thinking model whose template cannot switch thinking off (e.g. Qwen3 *-Thinking-2507).

    Hybrid models (qwen3:8b) render an empty think block when think=false, via a
    `not $.Think` / `not .Think` branch in their template; thinking-only ones don't.
    """
    if not caps or "thinking" not in caps:
        return False
    return not re.search(r"not\s+\$?\.Think\b", template or "")


async def _capabilities(client: httpx.AsyncClient, server: str, model: str, digest: str) -> tuple[list[str] | None, bool]:
    """(capabilities or None if unknown, thinking-only?)"""
    key = (server, digest or model)
    if key in _capability_cache:
        return _capability_cache[key]
    caps: list[str] | None = None
    template = ""
    try:
        r = await client.post(f"{server}/api/show", json={"model": model})
        if r.status_code == 200:
            data = r.json()
            raw = data.get("capabilities")
            caps = [str(c) for c in raw] if isinstance(raw, list) else None
            template = str(data.get("template") or "")
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("capability probe failed for %s on %s: %s", model, server, e)
        return None, False  # don't cache transient failures
    result = (caps, _thinking_only(caps, template))
    _capability_cache[key] = result
    return result


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
        caps, always_thinks = await _capabilities(client, server, name, str(m.get("digest") or ""))
        if caps is None:  # older Ollama without capabilities: infer
            if _looks_like_embedding(name, details):
                continue
            tools = False
        else:
            if "completion" not in caps:
                continue
            tools = "tools" in caps
        found.append(Candidate(server, name, parse_params(details.get("parameter_size", "")), tools, always_thinks))
    return found


def _apply(best: Candidate | None, manual: bool = False) -> None:
    previous = (state.source, state.server, state.model)
    if best is not None:
        settings.llm_provider = "ollama"
        settings.ollama_base_url = best.server
        settings.ollama_model = best.model
        state.source, state.server, state.model = "ollama", best.server, best.model
        state.always_thinks = best.always_thinks
    else:
        fallback = settings.llm_fallback_provider.strip().lower()
        settings.llm_provider = fallback
        state.source, state.server = "fallback", ""
        state.always_thinks = False
        state.model = settings.openai_model if fallback == "openai-compatible" else ""
    if manual:
        state.source = "manual"
    current = (state.source, state.server, state.model)
    if current != previous:
        if manual:
            logger.info("LLM selector: manual choice %s %s", settings.llm_provider, state.model)
            return
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
        _apply_choice()
        return state


def _apply_choice() -> None:
    """Apply the manual override if there is one, else the best of the last probe."""
    override = load_override()
    if override and override["mode"] == "ollama":
        server, model = override["server"], str(override.get("model") or "")
        known = next((c for c in state.candidates if c.server == server and c.model == model), None)
        _apply(known or Candidate(server, model, 0.0, True), manual=True)
    elif override:
        _apply(None, manual=True)
    else:
        _apply(pick_best(state.candidates))


def enabled() -> bool:
    return bool(settings.llm_auto_select)


def ollama_think_options(model: str, num_predict: int) -> tuple[bool, int]:
    """(think flag, num_predict) for an Ollama chat call.

    Thinking-only models ignore think=false and write their reasoning into the
    reply, so ask for think=true (Ollama then returns it in a separate field we
    drop) and leave room for the reasoning on top of the answer budget.
    """
    if enabled() and state.always_thinks and model == state.model and settings.llm_provider.strip().lower() == "ollama":
        return True, num_predict + max(0, int(settings.llm_thinking_budget or 0))
    return False, num_predict


def is_model_missing(status_code: int, body: str = "") -> bool:
    """Ollama answers 404 '{"error":"model 'x' not found"}' after a model is removed."""
    return status_code == 404 and ("not found" in body or not body)


def on_connect_error() -> None:
    """Called when the chosen Ollama server or model is gone: re-select right away (debounced)."""
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
    override = load_override()
    return {
        "auto_select": enabled(),
        "mode": "manual" if override else "auto",
        "override": override,
        "provider": settings.llm_provider,
        "fallback": {"provider": settings.llm_fallback_provider, "label": fallback_label(),
                     "model": settings.openai_model, "ready": fallback_ready()},
        "servers": [{"url": url, "label": label, "online": url not in state.unreachable}
                    for label, url in _server_entries()],
        "source": state.source,
        "server": state.server,
        "model": state.model,
        "always_thinks": state.always_thinks,
        "checked_at": state.checked_at,
        "unreachable": list(state.unreachable),
        "candidates": [
            {"server": c.server, "server_label": server_label(c.server), "model": c.model,
             "params_b": c.params_b, "tools": c.tools, "always_thinks": c.always_thinks}
            for c in sorted(state.candidates, key=lambda c: rank_key(c, _split(settings.llm_model_preference), servers()))
        ],
    }

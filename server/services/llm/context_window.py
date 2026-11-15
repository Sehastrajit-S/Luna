"""Explicit context budgeting for chat requests.

The model server must never be the one deciding what to cut: Ollama silently
truncates a prompt that exceeds num_ctx, which drops whatever falls off —
often the tool rules at the top of the system prompt. Instead every request is
fitted here, the way hosted assistants manage long conversations:

1. Pinned: the system prompt and the latest user message are always sent.
2. Clear old tool output first: long assistant replies (web results, file
   dumps) other than the most recent one are shortened — they are the largest
   and least useful part of old history.
3. Keep history newest-first while it fits. Turns that do not fit are covered
   by the conversation's rolling summary (compaction), which is added to the
   system prompt, and the drop is logged — nothing disappears silently.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Measured ~4.1 chars/token for Luna's prompts on Qwen3; a lower ratio
# over-estimates tokens, which keeps the budget on the safe side.
CHARS_PER_TOKEN = 3.5
MESSAGE_OVERHEAD_TOKENS = 6      # role markers / template tokens per message
SAFETY_MARGIN_TOKENS = 256
OLD_REPLY_MAX_CHARS = 700        # older assistant replies are clipped to this
LATEST_USER_MIN_TOKENS = 512     # never clip the user's own message below this

_REFERENCES_RE = re.compile(r"\n\s*References:\s*\n[\s\S]*$", re.IGNORECASE)


def estimate_tokens(text: str) -> int:
    return int(len(text or "") / CHARS_PER_TOKEN) + 1


def _message_tokens(message: dict) -> int:
    return estimate_tokens(message.get("content", "")) + MESSAGE_OVERHEAD_TOKENS


@dataclass
class FittedContext:
    system_prompt: str
    messages: list[dict]
    prompt_tokens: int          # estimated tokens actually being sent
    budget_tokens: int          # tokens available for the prompt
    dropped_messages: int       # older history turns not sent verbatim
    shortened_messages: int     # older replies clipped
    clipped_user_message: bool  # latest user message had to be clipped


def _shorten_reply(content: str) -> str:
    text = _REFERENCES_RE.sub("", content).strip()
    if len(text) <= OLD_REPLY_MAX_CHARS:
        return text
    return text[:OLD_REPLY_MAX_CHARS].rstrip() + " […earlier reply shortened]"


def _clip_middle(text: str, max_tokens: int) -> str:
    if len(text) <= int(max_tokens * CHARS_PER_TOKEN):
        return text
    max_chars = max(0, int(max_tokens * CHARS_PER_TOKEN) - 120)  # room for the marker
    head = int(max_chars * 0.7)
    tail = max_chars - head
    return f"{text[:head]}\n\n[…{len(text) - max_chars} characters omitted to fit the model's context…]\n\n{text[-tail:]}"


def fit_context(
    system_prompt: str,
    messages: list[dict],
    *,
    context_window: int,
    max_output_tokens: int,
    summary: str | None = None,
) -> FittedContext:
    """Return a system prompt + message list guaranteed to fit the window."""
    budget = max(1024, context_window - max_output_tokens - SAFETY_MARGIN_TOKENS)
    if not messages:
        system = system_prompt
        return FittedContext(system, [], estimate_tokens(system), budget, 0, 0, False)

    *history, latest = messages
    latest = dict(latest)

    # 1. Clear old tool output: clip every assistant reply except the newest.
    last_assistant = max((i for i, m in enumerate(history) if m.get("role") == "assistant"), default=-1)
    shortened = 0
    prepared: list[dict] = []
    for i, m in enumerate(history):
        content = m.get("content", "") or ""
        if m.get("role") == "assistant" and i != last_assistant:
            clipped = _shorten_reply(content)
            if clipped != content:
                shortened += 1
                content = clipped
        prepared.append({"role": m.get("role", "user"), "content": content})

    system = system_prompt
    summary = (summary or "").strip()

    def with_summary(base: str) -> str:
        return f"{base}\n\n## Earlier in this conversation (summary)\n{summary}" if summary else base

    # 2. Pinned content must fit; clip the user's message only as a last resort.
    clipped_user = False
    pinned = estimate_tokens(with_summary(system)) + _message_tokens(latest)
    if pinned > budget:
        room = max(LATEST_USER_MIN_TOKENS, budget - estimate_tokens(with_summary(system)) - MESSAGE_OVERHEAD_TOKENS)
        clipped = _clip_middle(latest.get("content", ""), room)
        if clipped != latest.get("content", ""):
            latest["content"] = clipped
            clipped_user = True
        pinned = estimate_tokens(with_summary(system)) + _message_tokens(latest)
    if pinned > budget:
        # The system prompt alone is over budget — keep its start (identity and
        # tool rules) and say so loudly; this needs a larger context window.
        logger.error(
            "System prompt (~%d tokens) exceeds the %d-token context budget; raise llm_context_window",
            estimate_tokens(system), budget,
        )
        system = _clip_middle(system, max(1024, budget - _message_tokens(latest)))
        summary = ""
        pinned = estimate_tokens(system) + _message_tokens(latest)

    # 3. Newest-first history until the budget is used.
    kept: list[dict] = []
    used = pinned
    for m in reversed(prepared):
        cost = _message_tokens(m)
        if used + cost > budget:
            break
        kept.append(m)
        used += cost
    kept.reverse()
    dropped = len(prepared) - len(kept)

    # A transcript should not open with a reply to a message we dropped.
    while kept and kept[0]["role"] == "assistant":
        kept.pop(0)
        dropped += 1

    final_system = with_summary(system)
    used = estimate_tokens(final_system) + sum(_message_tokens(m) for m in kept) + _message_tokens(latest)

    if dropped or clipped_user:
        logger.info(
            "Context fitted: ~%d/%d tokens, %d older message(s) %s, %d reply(ies) shortened%s",
            used, budget, dropped,
            "covered by summary" if summary else "omitted (no summary yet)",
            shortened,
            ", latest user message clipped" if clipped_user else "",
        )

    return FittedContext(
        system_prompt=final_system,
        messages=kept + [latest],
        prompt_tokens=used,
        budget_tokens=budget,
        dropped_messages=dropped,
        shortened_messages=shortened,
        clipped_user_message=clipped_user,
    )

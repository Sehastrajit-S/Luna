"""Turn a chat turn into a standalone web search query.

Follow-ups only make sense with the conversation ("I mean the new one for
actions, not chatbots", "search that again"), so before searching the query is
rewritten from recent history — the query-rewriting step hosted assistants run
before retrieval. Always returns a usable query: the model rewrite is bounded
by a timeout and falls back to a deterministic combination of recent turns.
"""
from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger(__name__)

REWRITE_TIMEOUT_S = 25.0
MAX_QUERY_CHARS = 160

# Words that only make sense with earlier context.
_CONTEXT_DEPENDENT_RE = re.compile(
    r"\b(it|its|that|this|those|these|them|they|one|ones|same|again|more|instead|else|"
    r"other|another|above|previous|earlier|mean|meant|not\s+that|the\s+last)\b",
    re.IGNORECASE,
)
_REFERENCES_RE = re.compile(r"\n\s*References:[\s\S]*$", re.IGNORECASE)
_TAG_RE = re.compile(r"\[[A-Z_]+:[^\]]*\]")

REWRITE_SYSTEM = (
    "You turn the user's latest chat message into ONE standalone web search query. "
    "Resolve pronouns and follow-ups using the conversation. Keep names, versions and constraints "
    "the user cares about. Never put file names in the query. "
    "Max 12 words. Output only the query — no quotes, no explanation."
)


def needs_context(message: str) -> bool:
    words = re.findall(r"\w+", message or "")
    return len(words) < 4 or bool(_CONTEXT_DEPENDENT_RE.search(message or ""))


def _clean_turn(content: str, limit: int = 300) -> str:
    text = _TAG_RE.sub("", _REFERENCES_RE.sub("", content or ""))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _sanitize(query: str) -> str:
    line = next((l for l in (query or "").splitlines() if l.strip()), "")
    line = re.sub(r"<think>.*?</think>", "", line, flags=re.DOTALL)
    line = re.sub(r"^\s*(?:search\s+)?query\s*:\s*", "", line, flags=re.IGNORECASE)
    line = line.strip().strip('"\'`').strip()
    return line[:MAX_QUERY_CHARS].strip()


def _fallback(message: str, history: list[dict]) -> str:
    previous = [m["content"] for m in history if m.get("role") == "user" and m.get("content")]
    parts = [_clean_turn(p, 120) for p in previous[-1:]] + [_clean_turn(message, 160)]
    return " ".join(p for p in parts if p)[:MAX_QUERY_CHARS]


_PLURAL_REF_RE = re.compile(r"\b(these|those|them|each|all\s+of\s+(?:them|these|those)|every\s+one)\b", re.IGNORECASE)
MAX_QUERIES = 5

MULTI_REWRITE_SYSTEM = (
    "The user's latest message refers to several items from the conversation (e.g. 'links for these'). "
    "Write one standalone web search query per item, max 5, one per line, most important first. "
    "Each query must name the item specifically (company, title, product) — max 12 words. "
    "Never put file names in a query. "
    "Output only the queries, no numbering, no explanation."
)


async def resolve_search_queries(message: str, history: list[dict] | None, candidate: str | None = None) -> list[str]:
    """Like resolve_search_query, but "links for these" after a list of five
    items becomes five targeted searches instead of one vague one."""
    history = [m for m in (history or []) if m.get("content")]
    if not history or not _PLURAL_REF_RE.search(message or ""):
        return [await resolve_search_query(message, history, candidate)]

    last_reply = next((m["content"] for m in reversed(history) if m.get("role") == "assistant"), "")
    prompt = (
        f"Previous reply from Luna:\n{_clean_turn(last_reply, 2000)}\n\n"
        f"Latest user message: {_clean_turn(message, 300)}\n\nSearch queries:"
    )
    try:
        from server.services.llm import ollama
        raw = await asyncio.wait_for(
            ollama.complete(prompt=prompt, system=MULTI_REWRITE_SYSTEM, temperature=0.0),
            timeout=REWRITE_TIMEOUT_S,
        )
        queries = []
        for line in (raw or "").splitlines():
            q = _sanitize(re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line))
            if len(q) >= 3 and q.lower() not in {x.lower() for x in queries}:
                queries.append(q)
        if queries:
            logger.info("Search split into %d queries from context: %r", len(queries[:MAX_QUERIES]), queries[:MAX_QUERIES])
            return queries[:MAX_QUERIES]
    except Exception as e:
        logger.warning("Multi-query rewrite failed (%s); using a single query", e)
    return [await resolve_search_query(message, history, candidate)]


async def resolve_search_query(message: str, history: list[dict] | None, candidate: str | None = None) -> str:
    """Best standalone search query for `message` given the conversation so far."""
    history = [m for m in (history or []) if m.get("content")]
    base = (candidate or message or "").strip()
    if base and (not history or not needs_context(message)):
        return base[:MAX_QUERY_CHARS]

    transcript = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'Luna'}: {_clean_turn(m['content'])}"
        for m in history[-6:]
    )
    prompt = f"Conversation:\n{transcript}\n\nLatest user message: {_clean_turn(message, 400)}\n\nSearch query:"
    try:
        from server.services.llm import ollama
        rewritten = _sanitize(await asyncio.wait_for(
            ollama.complete(prompt=prompt, system=REWRITE_SYSTEM, temperature=0.0),
            timeout=REWRITE_TIMEOUT_S,
        ))
        if len(rewritten) >= 3:
            logger.info("Search query rewritten from context: %r -> %r", message, rewritten)
            return rewritten
    except Exception as e:  # timeout, provider down, bad output — never block the search
        logger.warning("Search query rewrite failed (%s); using fallback", e)
    return _fallback(message, history) or base or message

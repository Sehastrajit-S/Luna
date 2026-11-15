"""Execute a lookup: a skill (extract → ask? → search → filter → verify → answer)
or, when no skill applies, a plain grounded web search. Domain-free."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

from server.config import settings
from server.services.skill_runtime.registry import SearchSkill
from server.services.skill_runtime import sources

logger = logging.getLogger(__name__)

EXTRACT_TIMEOUT_S = 25.0
MIN_RESULTS = 3
_NEAR_ME_RE = re.compile(r"\b(near\s+me|nearby|around\s+(?:here|me)|close\s+by|in\s+my\s+area)\b", re.IGNORECASE)
_FILE_NAME_RE = re.compile(r"\b[\w-]+\.(?:pdf|docx?|pptx?|xlsx?|csv|txt|md|png|jpe?g)\b", re.IGNORECASE)


@dataclass
class SkillRun:
    answer: str
    queries: list[str] = field(default_factory=list)
    results_text: str = ""
    asked: bool = False
    skill_id: str = ""
    cards: list[dict] = field(default_factory=list)


CARDS_MARKER = "luna-cards"


def embed_cards(answer: str, cards: list[dict]) -> str:
    """Attach cards to the reply as an HTML comment: rich clients render them
    (image, title, price, link), plain-text clients strip it, and it is stored
    with the message so reopened chats show the same cards."""
    if not cards:
        return answer
    payload = json.dumps(cards, ensure_ascii=True, separators=(",", ":")).replace("--", "-\\u002d")
    return f"{answer}\n\n<!--{CARDS_MARKER}:{payload}-->"


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _user_text(request: str, history: list[dict]) -> str:
    return " ".join([request] + [m.get("content", "") for m in history if m.get("role") == "user"]).lower()


async def extract_slots(skill: SearchSkill, request: str, history: list[dict], documents: str) -> dict:
    """Fill the skill's declared slots from the request, conversation and attached files."""
    if not skill.slots:
        return {}
    schema = "\n".join(f'- "{k}": {v}' for k, v in skill.slots.items())
    transcript = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'Luna'}: {_clip(m.get('content', ''), 400)}" for m in history[-6:]
    )
    prompt = (
        (f"User's files:\n{_clip(documents, 2500)}\n\n" if documents else "")
        + (f"Conversation:\n{transcript}\n\n" if transcript else "")
        + f"Latest request: {_clip(request, 400)}\n\n"
        + f"Return a JSON object with these keys:\n{schema}\n"
        "Use a list for plural keys. Use \"\" or [] when unknown — never guess, never use file names. JSON only."
    )
    raw = ""
    try:
        from server.services.llm import ollama
        raw = await asyncio.wait_for(
            ollama.complete(prompt=prompt, system="You extract search parameters. Output only valid JSON.",
                            temperature=0.0),
            timeout=EXTRACT_TIMEOUT_S,
        )
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        data = json.loads(match.group(0)) if match else {}
    except Exception as e:
        logger.warning("Slot extraction for %s failed (%s); raw=%r", skill.id, e, (raw or "")[:200])
        data = {}

    user_text = _user_text(request, history)
    slots: dict = {}
    for key in skill.slots:
        value = data.get(key, "")
        if isinstance(value, list):
            value = [_FILE_NAME_RE.sub("", str(v)).strip(" ,-") for v in value if str(v).strip()]
            value = [v for v in value if 2 <= len(v) <= 80]
        else:
            value = _FILE_NAME_RE.sub("", str(value or "")).strip(" ,-")
        # Grounded slots must come from what the user typed; the model otherwise
        # lifts names from files or earlier replies (a school as a "location").
        if key in skill.grounded:
            if isinstance(value, list):
                value = [v for v in value if v.lower() in user_text]
            elif value and value.lower() not in user_text:
                value = ""
        slots[key] = value

    # Search items must be about something the user actually said, attached or
    # discussed. A small model sometimes echoes the slot description instead
    # ("company" for "latest news on Nvidia"); such items are dropped, and the
    # query falls back to the user's own words.
    if skill.fan_out and isinstance(slots.get(skill.fan_out), list):
        known = _words(user_text + " " + documents + " " + " ".join(m.get("content", "") for m in history[-6:]))
        grounded_items = [item for item in slots[skill.fan_out] if _words(item) & known]
        if len(grounded_items) < len(slots[skill.fan_out]):
            logger.info("Dropped ungrounded %s items: %s", skill.fan_out,
                        [i for i in slots[skill.fan_out] if i not in grounded_items])
        slots[skill.fan_out] = grounded_items

    if "location" in skill.slots and not slots.get("location") and _NEAR_ME_RE.search(request):
        slots["location"] = settings.weather_city
    return slots


_STOP_WORDS = {"the", "a", "an", "and", "or", "of", "for", "in", "on", "to", "with", "me", "my", "some", "find", "best",
               "good", "new", "latest", "about", "near", "search", "look", "get", "show", "give", "any", "please"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+#]{3,}", (text or "").lower()) if w not in _STOP_WORDS}


def requirements_met(skill: SearchSkill, request: str, history: list[dict], documents: str, slots: dict) -> bool:
    conditions = (skill.requires or {}).get("any") or []
    if not conditions:
        return True
    text = " ".join([request] + [m.get("content", "") for m in history[-4:]])
    for cond in conditions:
        if cond == "documents" and documents:
            return True
        if cond.startswith("slot:") and slots.get(cond[5:]):
            return True
        if cond.startswith("pattern:") and re.search(cond[8:], text, re.IGNORECASE):
            return True
    return False


def build_queries(skill: SearchSkill, request: str, slots: dict) -> list[str]:
    items = slots.get(skill.fan_out) if skill.fan_out else None
    if isinstance(items, str):
        items = [items] if items else []
    if not items:
        # The user's own words, minus request filler ("can you find me …").
        fallback = re.sub(r"^\s*(?:(?:hey|please|can|could|would|will|you|find|search|look\s+for|me|some|for)\s+)+",
                          "", _FILE_NAME_RE.sub("", request), flags=re.IGNORECASE).strip(" ?.!")
        items = [fallback or request.strip()]
    values = {k: (" ".join(v) if isinstance(v, list) else v) for k, v in slots.items()}
    queries = []
    for item in items[: skill.max_items]:
        for template in skill.queries:
            try:
                q = template.format(item=item, **values)
            except (KeyError, IndexError):
                q = template.replace("{item}", item)
            q = " ".join(re.sub(r'""', "", q).split())
            if q and q not in queries:
                queries.append(q)
    return queries


async def _answer(request: str, queries: list[str], results_text: str, context: str, guidelines: str) -> str:
    from server.services.chat_pipeline.stage_tools import strip_unverified_links
    from server.services.response_formatter import attach_result_links, dedupe_linked_items, link_citations
    from server.services.tool_runner import verify_tool_result

    answer = await verify_tool_result(
        "web_search", {"query": queries[0] if queries else request, "queries": queries}, results_text, request,
        context=context, guidelines=guidelines,
    )
    answer = dedupe_linked_items(attach_result_links(link_citations(answer, results_text), results_text))
    answer = re.sub(r"(?m)^\s*#{1,6}\s*$\n?", "", answer).strip()
    return strip_unverified_links(answer, results_text + "\n" + context)


async def run_search_skill(skill: SearchSkill, request: str, history: list[dict] | None = None,
                           documents: str = "", context: str = "") -> SkillRun:
    history = history or []
    slots = await extract_slots(skill, request, history, documents)
    if not requirements_met(skill, request, history, documents, slots):
        return SkillRun(answer=skill.ask, asked=True, skill_id=skill.id)
    if skill.fan_out and not slots.get(skill.fan_out) and not documents:
        # The skill found nothing of its kind in the request (no product, paper,
        # place…): its templates would search the raw sentence ("best learn more
        # about X review"). A general web search fits better.
        logger.info("Skill %s found no %s in the request; using a general web search", skill.id, skill.fan_out)
        return await run_web_search(request, history, context=context)

    queries = build_queries(skill, request, slots)
    logger.info("Skill %s: slots=%s queries=%s", skill.id, slots, queries)
    results = await sources.run_searches(queries, per_query=skill.per_query, recency=skill.recency,
                                         backend=skill.backend)
    results = sources.rewrite_urls(results, skill.url_rewrites)
    results = sources.filter_results(results, skill.keep_urls, skill.drop_urls)
    if len(results) < MIN_RESULTS:
        # Safety net for every skill: the targeted queries came back thin, so
        # add a plain search on the user's own words (still filtered).
        plain = build_queries(SearchSkill(id="_", name="_", description="", queries=["{item}"]), request, {})
        extra = sources.filter_results(await sources.run_searches(plain, per_query=8, recency=skill.recency,
                                                                  backend=skill.backend),
                                       skill.keep_urls, skill.drop_urls)
        known = {r.url for r in results}
        results += [r for r in extra if r.url not in known]
        queries = queries + [q for q in plain if q not in queries]
        logger.info("Skill %s: thin results, added a plain search (%d total)", skill.id, len(results))
    removed = 0
    if skill.check_links:
        results, removed = await sources.drop_dead(results, skill.dead_phrases, skill.status_apis)
    results = sources.apply_labels(results, skill.labels)
    results_text = sources.format_results(results, queries, removed)

    cards: list[dict] = []
    if skill.cards:
        # Visual cards come straight from the item pages (exact image, title,
        # price) — not from the model's prose.
        cards = await _build_cards(skill.cards, request, results, results_text)
        if cards:
            listing = "\n".join(
                f"- {c['title']} — {(c['currency'] + ' ' + c['price']) if c['price'] else 'price not shown'} — {c['site']} — {c['url']}"
                for c in cards
            )
            results_text += f"\n\nItem pages shown to the user as cards (exact titles and prices):\n{listing}"

    answer = await _answer(request, queries, results_text, context, skill.guidelines)
    return SkillRun(answer=embed_cards(answer, cards), queries=queries, results_text=results_text,
                    skill_id=skill.id, cards=cards)


NAMES_SYSTEM = "You pick specific item names out of search results. Output one name per line, nothing else."


async def extract_item_names(request: str, results_text: str, what: str, limit: int) -> list[str]:
    """Specific items (e.g. product models) that the results recommend for the
    request. Names must appear in the results — never invented."""
    prompt = (
        f"Request: {_clip(request, 300)}\n\nSearch results:\n{results_text[:6000]}\n\n"
        f"List up to {limit} {what} that these results recommend for the request — exact names as written in "
        "the results, most relevant first, one per line, no numbering."
    )
    try:
        from server.services.llm import ollama
        raw = await asyncio.wait_for(ollama.complete(prompt=prompt, system=NAMES_SYSTEM, temperature=0.0),
                                     timeout=EXTRACT_TIMEOUT_S)
    except Exception as e:
        logger.warning("Item name extraction failed: %s", e)
        return []
    corpus = _words(results_text)
    names: list[str] = []
    for line in (raw or "").splitlines():
        name = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip(" *\"'")
        name_words = _words(name)
        # Grounding: most of the name's words must occur in the results.
        if 3 <= len(name) <= 90 and name_words and len(name_words & corpus) / len(name_words) >= 0.7 \
                and name.lower() not in {n.lower() for n in names}:
            names.append(name)
    return names[:limit]


async def _build_cards(spec: dict, request: str, results: list, results_text: str) -> list[dict]:
    """cards.lookup set: name the recommended items, look each one up (e.g. at
    stores) and card the first real item page. Otherwise card the results."""
    limit = int(spec.get("max", 6))
    image_patterns, price_patterns = spec.get("image_patterns"), spec.get("price_patterns")
    require_image = bool(spec.get("require_image", True))
    keep, drop = spec.get("keep_urls"), spec.get("drop_urls")

    if not spec.get("lookup"):
        candidates = sources.filter_results(results, keep, drop)
        return await sources.fetch_cards(candidates, limit, image_patterns, price_patterns, require_image)

    names = await extract_item_names(request, results_text, spec.get("names", "specific items"), limit)
    if not names:
        return []
    queries = [spec["lookup"].replace("{name}", name) for name in names]
    found = await sources.run_searches(queries, per_query=int(spec.get("per_query", 6)))

    async def card_for(query: str) -> dict | None:
        pages = sources.filter_results([r for r in found if r.query == query], keep, drop)
        cards = await sources.fetch_cards(pages, 1, image_patterns, price_patterns, require_image)
        return cards[0] if cards else None

    cards = await asyncio.gather(*(card_for(q) for q in queries))
    logger.info("Cards: %d of %d named items found (%s)", sum(1 for c in cards if c), len(names), names)
    return [c for c in cards if c]


async def run_web_search(request: str, history: list[dict] | None = None, context: str = "",
                         candidate: str | None = None) -> SkillRun:
    """No skill applies: resolve the request into standalone queries (one per
    item for "links for these"), search, drop dead links, answer from results."""
    from server.services.search_query import resolve_search_queries

    history = history or []
    queries = await resolve_search_queries(request, history, candidate=candidate)
    results = await sources.run_searches(queries, per_query=6 if len(queries) == 1 else 4)
    results, removed = await sources.drop_dead(results)
    results_text = sources.format_results(results, queries, removed)
    answer = await _answer(request, queries, results_text, context, "")
    return SkillRun(answer=answer, queries=queries, results_text=results_text, skill_id="web")

"""Skill runtime registry: use cases are declared as data in skills/<id>/.

The backend stays generic; everything specific to a use case (when it
applies, what to ask, where to look, how to judge results, how to answer)
lives in the skill folder.

A search skill is a normal Luna skill folder (skills/<id>/) whose skill.json
has a "search" block, e.g.:

    "search": {
      "intents":  [regex, ...],          what a request for this skill looks like
      "strong":   true,                     route on intent alone (no "search" verb needed)
      "slots":    {"titles": "...", "location": "..."},   what to extract from the request
      "fan_out":  "titles",                 list slot → one query set per item
      "grounded": ["location"],             slot values must appear in what the user typed
      "requires": {"any": ["documents", "pattern:..."], "ask": "question if none holds"},
      "queries":  ["\\"{item}\\" {location} (site:a OR site:b)", ...],
      "max_items": 3, "per_query": 8, "recency": "m", "backend": "text" | "news",
      "keep_urls": [...], "drop_urls": [...], "url_rewrites": [{"match": ..., "replace": ...}],
      "check_links": true, "dead_phrases": [...],
      "status_apis": [{"match": ..., "url": ...} | {"match": ..., "list_url": ..., "ids": ...}],
      "labels": [{"match": ..., "name": "Company", "group": 1}],
      "cards": {"max": 6, "keep_urls": [...], "require_image": true,
                "image_patterns": [...], "price_patterns": [...]}   visual result cards
    }

SKILL.md holds the answer-writing guidelines. Adding a skill = adding a folder.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SearchSkill:
    id: str
    name: str
    description: str
    intents: list[re.Pattern] = field(default_factory=list)
    strong: bool = False
    keywords: list[str] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)
    fan_out: str | None = None
    grounded: list[str] = field(default_factory=list)
    requires: dict = field(default_factory=dict)
    queries: list[str] = field(default_factory=list)
    max_items: int = 3
    per_query: int = 6
    recency: str | None = None
    backend: str = "text"
    keep_urls: list[str] = field(default_factory=list)
    drop_urls: list[str] = field(default_factory=list)
    url_rewrites: list[dict] = field(default_factory=list)
    check_links: bool = False
    dead_phrases: list[str] = field(default_factory=list)
    status_apis: list[dict] = field(default_factory=list)
    labels: list[dict] = field(default_factory=list)
    cards: dict = field(default_factory=dict)
    guidelines: str = ""
    order: int = 100

    @property
    def ask(self) -> str:
        return (self.requires or {}).get("ask", "")

    def score(self, text: str) -> int:
        lower = (text or "").lower()
        intent_hits = sum(1 for p in self.intents if p.search(text or ""))
        keyword_hits = sum(1 for k in self.keywords if re.search(rf"\b{re.escape(k)}\b", lower))
        return intent_hits * 3 + keyword_hits


def _skill_dirs() -> list[Path]:
    from backend.services.skill_manager import SKILL_DIRS
    return SKILL_DIRS


def _load(folder: Path) -> SearchSkill | None:
    meta_file = folder / "skill.json"
    if not meta_file.exists():
        return None
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Skipping search skill %s: %s", folder.name, e)
        return None
    spec = meta.get("search")
    if not isinstance(spec, dict):
        return None
    try:
        intents = [re.compile(p, re.IGNORECASE) for p in spec.get("intents", [])]
    except re.error as e:
        logger.warning("Skipping search skill %s: bad intent regex (%s)", folder.name, e)
        return None
    md = folder / "SKILL.md"
    return SearchSkill(
        id=meta.get("id") or folder.name,
        name=meta.get("name") or folder.name,
        description=meta.get("description", ""),
        intents=intents,
        strong=bool(spec.get("strong", False)),
        keywords=[str(k).lower() for k in meta.get("keywords", [])],
        slots=dict(spec.get("slots", {})),
        fan_out=spec.get("fan_out"),
        grounded=list(spec.get("grounded", [])),
        requires=dict(spec.get("requires", {})),
        queries=list(spec.get("queries", [])) or ["{item}"],
        max_items=int(spec.get("max_items", 3)),
        per_query=int(spec.get("per_query", 6)),
        recency=spec.get("recency"),
        backend=spec.get("backend", "text"),
        keep_urls=list(spec.get("keep_urls", [])),
        drop_urls=list(spec.get("drop_urls", [])),
        url_rewrites=list(spec.get("url_rewrites", [])),
        check_links=bool(spec.get("check_links", False)),
        dead_phrases=list(spec.get("dead_phrases", [])),
        status_apis=list(spec.get("status_apis", [])),
        labels=list(spec.get("labels", [])),
        cards=dict(spec.get("cards", {})),
        guidelines=md.read_text(encoding="utf-8", errors="replace").strip() if md.exists() else "",
        order=int(spec.get("order", 100)),
    )


def load_search_skills() -> list[SearchSkill]:
    skills = []
    for root in _skill_dirs():
        if root.exists():
            for folder in sorted(p for p in root.iterdir() if p.is_dir()):
                if skill := _load(folder):
                    skills.append(skill)
    return sorted(skills, key=lambda s: s.order)


def get_search_skill(skill_id: str) -> SearchSkill | None:
    return next((s for s in load_search_skills() if s.id == skill_id), None)


def pick_search_skill(text: str, *, strong_only: bool = False) -> SearchSkill | None:
    """Best specialised skill for a request, or None (→ general web search).

    strong_only: the message isn't phrased as a search, so only skills whose
    intents alone justify a lookup ("restaurants near me", "news on X") count.
    """
    best, best_score = None, 0
    for skill in load_search_skills():
        if strong_only and not (skill.strong and any(p.search(text or "") for p in skill.intents)):
            continue
        score = skill.score(text)
        if score > best_score:
            best, best_score = skill, score
    # A lone keyword ("python") isn't enough to take over a generic search.
    return best if best_score >= 2 else None


CHOOSE_TIMEOUT_S = 20.0


async def choose_skill_with_model(request: str, history: list[dict] | None = None) -> SearchSkill | None:
    """When no skill's patterns match, let the model pick from the skills'
    names and descriptions — the way hosted assistants choose a skill — or
    answer "none" for a plain web search."""
    import asyncio
    import re as _re

    skills = load_search_skills()
    if not skills:
        return None
    menu = "\n".join(f"- {s.id}: {s.description}" for s in skills)
    last_user = next((m.get("content", "") for m in reversed(history or []) if m.get("role") == "user"), "")
    prompt = (
        f"Skills:\n{menu}\n\n"
        + (f"Previous user message: {last_user[:300]}\n" if last_user else "")
        + f"Request: {request[:400]}\n\n"
        "Which skill fits this request best? Answer with the skill id only, or none if no skill clearly fits."
    )
    try:
        from backend.services.llm import ollama
        raw = await asyncio.wait_for(
            ollama.complete(prompt=prompt, system="You route requests to skills. Answer with one id or none.",
                            temperature=0.0),
            timeout=CHOOSE_TIMEOUT_S,
        )
    except Exception as e:
        logger.warning("Skill choice by model failed (%s); using web search", e)
        return None
    answer = (raw or "").strip().lower()
    for skill in skills:
        if _re.search(rf"(?<![\w-]){_re.escape(skill.id)}(?![\w-])", answer):
            logger.info("Model chose skill %s for %r", skill.id, request)
            return skill
    return None


def all_ask_replies() -> set[str]:
    return {s.ask for s in load_search_skills() if s.ask}

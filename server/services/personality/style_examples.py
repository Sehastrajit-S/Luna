"""Pick a few curated conversation examples that fit the current message.

The examples (style_examples.json) show how Luna talks in a given kind of
moment: a greeting, a bad day, a recipe, a correction. Showing the model the
few that match the message steers tone far better than a fixed list, and a
handful costs a few hundred tokens instead of thousands.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("style_examples.json")
_WORD_RE = re.compile(r"[a-z0-9']+")
_STOP = frozenset(("a an the i you me my it is to of and or for on in at this that be do can what so im i'm "
                   "about just really very how does get give some").split())
MIN_SCORE = 2.0


@lru_cache(maxsize=1)
def load_examples() -> tuple[dict, ...]:
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(ex for ex in data.get("examples", []) if ex.get("user") and ex.get("luna"))


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOP}


def _score(example: dict, message: str, words: set[str]) -> float:
    low = message.lower()
    score = 0.0
    for tag in example.get("tags", []):
        tag = tag.lower()
        if " " in tag:
            score += 3.0 if tag in low else 0.0
        elif tag in words:
            score += 2.0
    score += len(words & _words(example["user"])) * 1.0
    return score


def pick_examples(message: str, k: int = 4) -> list[dict]:
    """Up to k examples, best first, at most one per category."""
    examples = load_examples()
    if not examples or not (message or "").strip():
        return []
    words = _words(message)
    ranked = sorted(examples, key=lambda ex: -_score(ex, message, words))
    picked, seen = [], set()
    for ex in ranked:
        if _score(ex, message, words) < MIN_SCORE or ex.get("cat") in seen:
            continue
        picked.append(ex)
        seen.add(ex.get("cat"))
        if len(picked) == k:
            break
    return picked


def examples_prompt(message: str, k: int = 4) -> str:
    picked = pick_examples(message, k)
    if not picked:
        return ""
    lines = ["\n## How Luna talks (style examples; copy the tone, not the facts)"]
    for ex in picked:
        note = " (after the tool or context gave these facts)" if ex.get("after_tool") else ""
        lines.append(f"User: {ex['user']}\nLuna{note}: {ex['luna']}")
    return "\n\n".join(lines)

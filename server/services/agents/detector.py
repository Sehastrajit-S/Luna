"""
Detector — decide whether a user request warrants spinning up a Crew.

Crew Mode is more expensive (multiple LLM calls + parallel agents) than the
single-pass chat path or the linear TaskPlan.  We only invoke it when the
request looks materially benefit from coordinated multi-role work.

Heuristics (all required to fire, except keyword-only short-circuit):
  - Message has at least N words (excludes one-liners)
  - Contains a multi-domain signal (research + write, plan + book, code + test, ...)
  - Or matches a strong "crew" verb directly ("orchestrate", "delegate", "team up")

The detector is intentionally conservative.  Users can always force Crew Mode
via /api/agents/crew or by saying "use crew mode for ...".
"""
from __future__ import annotations

import re

# Strong signals that always trigger Crew Mode
_CREW_TRIGGERS = [
    r"\b(use\s+crew|crew\s+mode|orchestrate|delegate)\b",
    r"\b(multi[- ]?agent|swarm|sub[- ]?agents?)\b",
    r"\b(spawn|coordinate|dispatch)\b.{0,30}\bagents?\b",
]

# Multi-domain signals: research + planning, code + writing, etc.
_DOMAIN_PAIRS = [
    (r"\b(research|find|search|gather|investigate)\b", r"\b(write|draft|compile|summarize|publish)\b"),
    (r"\b(plan|schedule|organize)\b",                  r"\b(book|reserve|create|set up|configure)\b"),
    (r"\b(code|implement|build|write)\b",              r"\b(test|verify|review|critique|check)\b"),
    (r"\b(analyze|compute|compare)\b",                 r"\b(report|present|recommend|summarize)\b"),
    (r"\b(research|find|gather)\b",                    r"\b(plan|schedule|book|create)\b"),
]

_MIN_WORDS = 12


def is_crew_request(message: str, explicit_only: bool = False) -> bool:
    """
    Return True if the message should be handled by the multi-agent Crew.

    Conservative: returns False for short or single-domain messages.
    explicit_only: only an explicit ask ("use crew mode", "orchestrate agents")
    counts. The agent loop handles ordinary multi-step requests with the
    conversation in view; the word-pair heuristic misfired on phrases like
    "code word" + "quick check" and sent recall questions to a crew that has
    no conversation history.
    """
    if not message or not isinstance(message, str):
        return False

    lower = message.lower()

    # Strong crew keyword → always fire
    if any(re.search(p, lower) for p in _CREW_TRIGGERS):
        return True
    if explicit_only:
        return False

    # Length floor for everything else
    if len(message.split()) < _MIN_WORDS:
        return False

    # Multi-domain pair detection
    for verb_a, verb_b in _DOMAIN_PAIRS:
        if re.search(verb_a, lower) and re.search(verb_b, lower):
            return True

    return False

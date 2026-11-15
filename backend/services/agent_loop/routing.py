"""Which requests the fast single-purpose shortcuts may take.

The dispatch stage answers one-intent requests ("find me jobs", "play X",
"what time is it") without the model. A request with several steps ("find the
latest release, then add a task to read it") must reach the agent loop, or the
shortcut answers the first part and the rest is silently dropped.
"""
from __future__ import annotations

import re

_ACTION = (
    r"(?:add|save|put|schedule|remind|create|make|write|send|e-?mail|mail|text|message|open|launch|play|queue|"
    r"download|copy|book|set|note|log|summari[sz]e|compare|draft|post|comment|close|delete|update|move|share)"
)
# "…, then add …", "… and after that email …"
_JOINED_STEP_RE = re.compile(
    rf"\b(?:and\s+then|then|after\s+that|afterwards|also|as\s+well\s+as|plus)\b[\s,]+(?:\w+\s+){{0,3}}?{_ACTION}\b",
    re.IGNORECASE,
)
# "find X and add it to …" / "search Y and email me the top one"
_AND_ACTION_RE = re.compile(rf"\band\s+(?:\w+\s+){{0,2}}?{_ACTION}\s+(?:it|them|that|this|those|the|a|an|me|to|on|in)\b",
                            re.IGNORECASE)
# A later sentence that is its own instruction: "Find X. Add a task for Y."
_NEXT_SENTENCE_RE = re.compile(rf"[.!?;]\s+(?:please\s+|and\s+)?{_ACTION}\b", re.IGNORECASE)


def is_multi_step(message: str) -> bool:
    text = " ".join((message or "").split())
    return bool(_JOINED_STEP_RE.search(text) or _AND_ACTION_RE.search(text) or _NEXT_SENTENCE_RE.search(text))

"""Trivial messages — greetings, thanks, sign-offs — answered without the LLM.

A bare "hi" or "good morning" doesn't need memory retrieval, a 8K-token
system prompt, a model call, or background extraction. Only whole-message
small talk matches: "hi, can you check my email" or "how are you" still go
through the full pipeline.

Affirmatives ("ok", "yes", "sure") are never treated as small talk — they
usually answer a question Luna just asked ("want me to open it?").
"""
from __future__ import annotations

import random
import re
from datetime import datetime
from typing import Literal

SmallTalkKind = Literal["greeting", "morning", "afternoon", "evening", "night", "thanks", "ack", "farewell"]

_GREETING = r"(?:h+i+|he+y+|hel+o+|hiya|howdy|yo+|su+p|wa+s+u+p|what'?s\s+up|hey\s+there|hi\s+there|hello\s+there)"
_MORNING = r"(?:(?:good\s+)?mo+rning|gm)"
_AFTERNOON = r"(?:good\s+afternoon)"
_EVENING = r"(?:good\s+evening)"
_NIGHT = r"(?:good\s*night|g'?night|gn|night\s+night|nighty\s+night)"
_THANKS = r"(?:thanks|thank\s+(?:you|u)|thx|ty|tysm|appreciate\s+it|cheers)(?:\s+(?:so\s+much|a\s+lot|a\s+ton|again))?"
_ACK = r"(?:cool|nice|great|awesome|perfect|got\s+it|gotcha|noted|sounds\s+good|all\s+good|love\s+it)"
_FAREWELL = r"(?:bye+|bye\s+bye|good\s*bye|see\s+ya|see\s+you(?:\s+later)?|cya|later|talk\s+(?:to\s+you\s+)?later|ttyl)"

_KINDS: list[tuple[SmallTalkKind, str]] = [
    ("morning", _MORNING), ("afternoon", _AFTERNOON), ("evening", _EVENING), ("night", _NIGHT),
    ("thanks", _THANKS), ("farewell", _FAREWELL), ("ack", _ACK), ("greeting", _GREETING),
]
_ANY_PART = "|".join(p for _, p in _KINDS)


def _normalize(message: str, names: tuple[str, ...]) -> str:
    text = (message or "").lower().strip()
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[^\w\s']", " ", text)          # punctuation, emoji
    for name in names:
        if name:
            text = re.sub(rf"\b{re.escape(name.lower())}\b", " ", text)
    return " ".join(text.split())


def classify_small_talk(message: str, prev_assistant: str = "", user_name: str = "") -> SmallTalkKind | None:
    """Return the small-talk kind when the WHOLE message is small talk, else None."""
    if len(message or "") > 60:
        return None
    text = _normalize(message, ("luna", user_name))
    if not text or not re.fullmatch(rf"(?:{_ANY_PART})(?:\s+(?:{_ANY_PART}))*", text):
        return None
    for kind, pattern in _KINDS:
        if re.search(rf"\b{pattern}\b", text):
            # "cool"/"got it" right after Luna asked something is an answer.
            if kind == "ack" and (prev_assistant or "").rstrip().endswith("?"):
                return None
            return kind
    return None


_REPLIES: dict[str, list[str]] = {
    "morning": ["Morning{name}! What's on today?", "Good morning{name}. How'd you sleep?", "Morning{name}. What are we getting into today?"],
    "afternoon": ["Afternoon{name}! How's the day going?", "Good afternoon{name}. What's up?"],
    "evening": ["Evening{name}! How was the day?", "Good evening{name}. What's on your mind?"],
    "night": ["Night{name}. Sleep well.", "Good night{name}. Sweet dreams.", "Night night{name}. Rest well."],
    "thanks": ["Anytime{name}.", "Happy to help.", "Of course{name}.", "No problem."],
    "ack": ["👍", "Glad that works.", "Nice."],
    "farewell": ["See you{name}!", "Later{name}. I'll be here.", "Bye{name}! Talk soon."],
}
_GREETING_BY_HOUR = [
    (5, 12, ["Morning{name}! What's up?", "Hey{name}, good morning. What's on today?"]),
    (12, 17, ["Hey{name}! How's the day going?", "Hi{name}. What's up?"]),
    (17, 22, ["Hey{name}! How was the day?", "Evening{name}. What's on your mind?"]),
    (22, 29, ["Hey{name}, you're up late. What's going on?", "Hi{name}. Can't sleep?"]),
]


def small_talk_reply(kind: SmallTalkKind, user_name: str = "", now: datetime | None = None) -> str:
    now = now or datetime.now()
    name = f", {user_name}" if user_name and user_name.lower() != "friend" else ""
    if kind == "greeting":
        hour = now.hour if now.hour >= 5 else now.hour + 24
        pool = next(p for lo, hi, p in _GREETING_BY_HOUR if lo <= hour < hi)
    else:
        pool = _REPLIES[kind]
    return random.choice(pool).format(name=name)

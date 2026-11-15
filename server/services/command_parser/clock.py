"""Current date/time questions — answered from the local clock, never the web."""
import re
from datetime import datetime
from typing import Literal

ClockQuery = Literal["date", "time", "datetime"]

_WHAT = r"(?:what(?:'?s|\s+is)?|whats|tell\s+me|do\s+you\s+know)"

_DATE_RE = re.compile(
    rf"^\s*(?:hey\s+|so\s+|luna,?\s+)*{_WHAT}\s+(?:the\s+)?"
    r"(?:day|date|day\s+(?:of\s+the\s+week|today)|today'?s\s+(?:date|day))"
    r"(?:\s+(?:is\s+it|it\s+is|today|now|right\s+now))*\s*\??\s*$"
    r"|^\s*what\s+day\s+is\s+(?:it|today)(?:\s+today)?\s*\??\s*$"
    r"|^\s*(?:what\s+is\s+|what'?s\s+)?today'?s\s+date\s*\??\s*$"
    r"|^\s*(?:what\s+is\s+|what'?s\s+)?today\s*\?\s*$",
    re.IGNORECASE,
)

_TIME_RE = re.compile(
    rf"^\s*(?:hey\s+|so\s+|luna,?\s+)*(?:{_WHAT}\s+(?:the\s+)?(?:current\s+)?time|what\s+time\s+is\s+it)"
    r"(?:\s+(?:is\s+it|it\s+is|now|right\s+now))*\s*\??\s*$",
    re.IGNORECASE,
)


def parse_clock_question(message: str) -> ClockQuery | None:
    """Return which clock fact the user wants, or None.

    Only whole-message questions match, so "what time is my meeting" or
    "what time is it in Tokyo" still go to the model/tools.
    """
    text = (message or "").strip()
    if not text:
        return None
    is_date = bool(_DATE_RE.match(text))
    is_time = bool(_TIME_RE.match(text))
    if is_date and is_time:
        return "datetime"
    if is_date:
        return "date"
    if is_time:
        return "time"
    return None


def answer_clock_question(kind: ClockQuery, now: datetime | None = None) -> str:
    now = now or datetime.now()
    day = f"{now:%A}, {now:%B} {now.day}, {now.year}"
    clock = now.strftime("%I:%M %p").lstrip("0")
    if kind == "time":
        return f"It's {clock}."
    if kind == "date":
        return f"Today is {day}."
    return f"It's {clock} on {day}."

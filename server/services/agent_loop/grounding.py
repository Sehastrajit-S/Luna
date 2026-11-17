"""Requests that can only be answered by a tool, never from the model's memory.

In live tests the model was offered get_volume / get_system_info /
workspace_read, skipped them, and answered "75%", "16 GB RAM, i7-12700K" and
"# Welcome to Luna" — all invented, all stated with confidence. For these
questions the loop must not accept an answer until the read tool has run.
Each rule returns the exact call to make, so the loop can run it itself when
the model won't.
"""
from __future__ import annotations

import re

# Changing something is a different tool (set_volume, set_clipboard…), not a read.
_CHANGE_RE = re.compile(
    r"\b(?:set|turn|change|increase|decrease|raise|lower|bump|put|make|mute|unmute|copy|paste|"
    r"up|down|max(?:imum)?|louder|quieter|brighter|dimmer)\b", re.IGNORECASE)
_ASKS_RE = re.compile(
    r"\b(?:what(?:'s|\s+is|\s+are)?|which|how\s+(?:much|many|loud|bright|high)|tell\s+me|check|show|"
    r"current(?:ly)?|right\s+now|is\s+it|do\s+i\s+have|does\s+(?:this|my))\b", re.IGNORECASE)

_STATE_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bvolume\b", re.IGNORECASE), "get_volume"),
    (re.compile(r"\bbrightness\b", re.IGNORECASE), "get_brightness"),
    (re.compile(r"\bclipboard\b", re.IGNORECASE), "get_clipboard"),
    (re.compile(r"\b(?:ram|cpu|processor|battery|specs?|system\s+info(?:rmation)?|operating\s+system|os\s+version)\b"
                r"|\bhow\s+much\s+memory\b.{0,30}\b(?:pc|computer|laptop|machine|system)\b", re.IGNORECASE),
     "get_system_info"),
)

_FILE_RE = re.compile(r"(?<![\w/\\.-])((?:[A-Za-z]:)?[\w./\\-]*[\w-]\.(?:md|txt|py|json|csv|js|ts|tsx|html|css|"
                      r"ya?ml|toml|ini|cfg|log|sql|xml|env\.example))\b", re.IGNORECASE)
_READ_RE = re.compile(r"\b(?:read|open|show|look\s+at|what(?:'s|\s+is)\s+in|contents?|says?|summari[sz]e|"
                      r"first\s+(?:line|heading)|heading|title)\b", re.IGNORECASE)

# "Summarize this: https://…" / "Why does this matter? <article link>" — the
# answer comes from the page, so read it first instead of guessing from the
# URL or treating words in the pasted blurb ("daily news") as a news request.
_LINK_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_ABOUT_LINK_RE = re.compile(
    r"\?|\b(?:summari[sz]e|summary|explain|tl;?dr|key\s+points|background|context|sides|matter|mean|"
    r"what|why|how|who|when|where|tell\s+me|read|about)\b", re.IGNORECASE)


def linked_page(text: str) -> str | None:
    """The page a message asks about (its first link), or None."""
    match = _LINK_RE.search(text or "")
    if not match or not _ABOUT_LINK_RE.search(_LINK_RE.sub(" ", text)):
        return None
    return match.group(0).rstrip(".,;:!?")


_NUM = r"(-?\d+(?:\.\d+)?)"
_OPS = {
    "times": "*", "x": "*", "×": "*", "*": "*", "multiplied by": "*",
    "plus": "+", "+": "+", "minus": "-", "-": "-",
    "divided by": "/", "over": "/", "/": "/", "÷": "/",
}
# "Forget everything you know about my dog" — a command at the start of a
# sentence, so "I always forget my keys" never wipes anything. The model
# answered "I've reset my memory about your dog" and deleted nothing.
_FORGET_RE = re.compile(
    r"(?:^|[.!?]\s+)(?:please\s+|(?:can|could)\s+you\s+|luna,?\s+)?(?:forget|erase|wipe)\s+"
    r"(?:(?:everything|anything|all|what)\s+)?(?:(?:you\s+)?(?:know|remember)\s+)?(?:about\s+)?"
    r"(?P<about>[^.?!]{2,80})", re.IGNORECASE)

# Facts that change after a model's training (versions, prices, office holders,
# results, news): look them up, then answer from what was found. Personal
# questions, this PC's state, time and weather have their own sources.
_FRESH_RE = re.compile(
    r"\b(?:latest|newest|current(?:ly)?|today'?s|this\s+(?:week|month|year)|right\s+now|recent(?:ly)?|"
    r"news|headlines?|price\s+of|prices?|cost\s+of|exchange\s+rate|stock|who\s+won|winner|score|"
    r"who\s+is\s+the\s+(?:current|new)|released?|release\s+date|newest\s+version|20[2-9]\d)\b", re.IGNORECASE)
_NOT_WEB_RE = re.compile(
    r"\b(?:my|me|mine|i|i'm|i've|we|our|you|your|weather|temperature|forecast|time|date|day|"
    r"volume|brightness|clipboard|ram|cpu|battery|tasks?|calendar|meetings?|reminders?|emails?|inbox)\b",
    re.IGNORECASE)
_QUESTION_RE = re.compile(r"\?\s*$|^\s*(?:what|which|who|when|where|how|is|are|does|did|tell\s+me)\b", re.IGNORECASE)

# "What's the news today?" — headlines come from the news feeds, never from memory.
_NEWS_RE = re.compile(r"\b(?:news|headlines?|current\s+events|what'?s\s+happening\s+in\s+the\s+world)\b", re.IGNORECASE)
_NEWS_ASK_RE = re.compile(r"\?|\b(?:what|any|give|tell|show|get|brief|catch\s+me\s+up|read|top|today'?s|daily|latest)\b",
                          re.IGNORECASE)
_NEWS_TOPIC_RE = re.compile(r"\b(?:about|on|regarding|from|in)\s+(?:the\s+)?(?P<topic>[^?.!,]{2,40})", re.IGNORECASE)
_NEWS_NOT_TOPIC = {"today", "the world", "world", "the morning", "this morning", "the news"}

_MATH_RE = re.compile(
    rf"\b(?:what(?:'s|\s+is)|how\s+much\s+is|calculate|compute|work\s+out|solve)\b[^?]*?{_NUM}\s*"
    r"(times|multiplied\s+by|divided\s+by|plus|minus|over|x|×|\*|\+|/|÷|-)\s*" + _NUM, re.IGNORECASE)


_NOW_RE = re.compile(r"\b(?:latest|newest|current(?:ly)?|now|today|recent(?:ly)?|this\s+(?:week|month|year))\b",
                     re.IGNORECASE)


def _settled_past(text: str) -> bool:
    """"Who won the 2018 World Cup?" has a settled answer; only recent years and
    "latest/current" questions need a lookup."""
    from datetime import date

    years = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", text)]
    return bool(years) and max(years) < date.today().year - 1 and not _NOW_RE.search(text)


def _news_request(text: str) -> dict | None:
    """daily_news arguments when the message asks for the news, else None."""
    if not (_NEWS_RE.search(text) and _NEWS_ASK_RE.search(text)) or re.search(r"\bmy\b", text, re.IGNORECASE):
        return None
    topic = _NEWS_TOPIC_RE.search(text)
    about = topic.group("topic").strip() if topic else ""
    return {"topic": "" if about.lower() in _NEWS_NOT_TOPIC else about}


def is_general_news(text: str) -> bool:
    """Asks for today's news in general, not news about a topic."""
    request = _news_request(text or "")
    return request is not None and not request["topic"]


def required_calls(message: str) -> list[tuple[str, dict]]:
    """The calls this message needs before any answer is trustworthy."""
    text = message or ""
    calls: list[tuple[str, dict]] = []
    forget = _FORGET_RE.search(text)
    if forget:
        calls.append(("forget_memory", {"about": forget.group("about").strip()}))
    if _ASKS_RE.search(text) and not _CHANGE_RE.search(text):
        for pattern, tool in _STATE_RULES:
            if pattern.search(text) and (tool, {}) not in calls:
                calls.append((tool, {}))
    page = linked_page(text)
    if page and not calls:
        return [("web_fetch", {"url": page})]      # "page.html" in a URL is not a workspace file
    if _READ_RE.search(text):
        for path in _FILE_RE.findall(text)[:2]:
            calls.append(("workspace_read", {"path": path.replace("\\", "/")}))
    math = _MATH_RE.search(text)
    if math:
        op = _OPS[re.sub(r"\s+", " ", math.group(2).lower())]
        calls.append(("calculate", {"expression": f"{math.group(1)}{op}{math.group(3)}"}))
    news = None if calls else _news_request(text)
    if news is not None:
        calls.append(("daily_news", news))
    if (not calls and _QUESTION_RE.search(text) and _FRESH_RE.search(text)
            and not _NOT_WEB_RE.search(text) and not _settled_past(text) and len(text) < 300):
        calls.append(("web_search", {"query": " ".join(text.split())}))
    return calls

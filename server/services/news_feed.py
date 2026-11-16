"""News by category, straight from publishers' RSS feeds (BBC, The Guardian, NPR).

Used by the News tab (GET /api/news) and by chat: "what's the news today?" or
"tech news" is answered from these feeds directly, as headline cards with
images plus category buttons, so every headline is real and linked.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger("luna.news")

MEDIA = "{http://search.yahoo.com/mrss/}"
CACHE_TTL_S = 600
HEADERS = {"User-Agent": "Mozilla/5.0 (Luna news reader)", "Accept": "application/rss+xml,application/xml,text/xml,*/*"}


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    feeds: tuple[tuple[str, str], ...]


CATEGORIES: tuple[Category, ...] = (
    Category("top", "Top stories", (
        ("BBC", "https://feeds.bbci.co.uk/news/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/world/rss"),
        ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    )),
    Category("world", "World", (
        ("BBC", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/world/rss"),
        ("NPR", "https://feeds.npr.org/1004/rss.xml"),
    )),
    Category("us", "U.S.", (
        ("BBC", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/us-news/rss"),
        ("NPR", "https://feeds.npr.org/1003/rss.xml"),
    )),
    Category("business", "Business", (
        ("BBC", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/business/rss"),
        ("NPR", "https://feeds.npr.org/1006/rss.xml"),
    )),
    Category("tech", "Tech", (
        ("BBC", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/technology/rss"),
        ("NPR", "https://feeds.npr.org/1019/rss.xml"),
    )),
    Category("science", "Science", (
        ("BBC", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/science/rss"),
        ("NPR", "https://feeds.npr.org/1007/rss.xml"),
    )),
    Category("health", "Health", (
        ("BBC", "https://feeds.bbci.co.uk/news/health/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/society/health/rss"),
        ("NPR", "https://feeds.npr.org/1128/rss.xml"),
    )),
    Category("sports", "Sports", (
        ("BBC", "https://feeds.bbci.co.uk/sport/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/sport/rss"),
        ("NPR", "https://feeds.npr.org/1055/rss.xml"),
    )),
    Category("entertainment", "Entertainment", (
        ("BBC", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
        ("The Guardian", "https://www.theguardian.com/culture/rss"),
        ("NPR", "https://feeds.npr.org/1008/rss.xml"),
    )),
)
BY_KEY = {c.key: c for c in CATEGORIES}

# Words people use for each category, as in "tech news" or "sports headlines".
_ALIASES = {
    "top": r"top|latest|breaking|today'?s|daily|main|big|general",
    "world": r"world|international|global",
    "us": r"u\.?s\.?|us|american|national|domestic",
    "business": r"business|finance|financial|economy|economic|market|markets|money",
    "tech": r"tech|technology|ai",
    "science": r"science|scientific|climate|environment|space",
    "health": r"health|medical|medicine",
    "sports": r"sports?|football|soccer|nba|nfl",
    "entertainment": r"entertainment|celebrity|celebrities|movies?|film|music|arts?|culture|showbiz",
}
_NEWS_WORD = r"(?:news|headlines?|stories|updates?)"
_CATEGORY_RES = {
    key: re.compile(
        rf"\b(?:{alias})\s+{_NEWS_WORD}\b|\b{_NEWS_WORD}\s+(?:on|in|for|from|about)\s+(?:the\s+)?(?:{alias})\b",
        re.I,
    )
    for key, alias in _ALIASES.items()
}
_GENERAL_RE = re.compile(
    rf"^\s*(?:(?:what'?s|what\s+is|any|give\s+me|show\s+me|tell\s+me|get\s+me|catch\s+me\s+up\s+on)\s+)?"
    rf"(?:the\s+)?(?:latest\s+|today'?s\s+|top\s+|breaking\s+)?{_NEWS_WORD}(?:\s+(?:update|today|now|for\s+today|this\s+morning|tonight))*"
    rf"(?:\s+today)?\s*[?.!]*\s*$",
    re.I,
)


@dataclass
class Story:
    title: str
    link: str
    source: str
    image: str
    summary: str
    published: str          # ISO 8601, UTC; "" when the feed gave no date


_cache: dict[str, tuple[float, list[Story]]] = {}
_locks: dict[str, asyncio.Lock] = {}


def news_category_request(text: str) -> str | None:
    """The category a chat message asks for ("tech news" → "tech", "what's the news today?" → "top"),
    or None when it isn't a plain news request (news *about* something goes to the news-search skill)."""
    text = (text or "").strip()
    if not text or len(text) > 120:
        return None
    for key, pattern in _CATEGORY_RES.items():
        if pattern.search(text) and key != "top":
            return key
    if _CATEGORY_RES["top"].search(text) or _GENERAL_RE.match(text):
        return "top"
    return None


def _clean(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return " ".join(text.split())


def _image(item) -> str:
    best, best_width = "", -1
    for tag in ("content", "thumbnail"):
        for el in item.findall(MEDIA + tag):
            url = el.get("url", "")
            if not url.startswith("https://") or (el.get("medium") and el.get("medium") != "image"):
                continue
            width = int(el.get("width") or 0)
            if width > best_width:
                best, best_width = url, width
    if not best:
        enclosure = item.find("enclosure")
        if enclosure is not None and "image" in (enclosure.get("type") or "") and enclosure.get("url", "").startswith("https://"):
            best = enclosure.get("url")
    # BBC thumbnails come at 240px; the same image exists at 480px.
    return re.sub(r"(ichef\.bbci\.co\.uk/(?:ace/standard|news))/240/", r"\1/480/", best)


def _published(item) -> str:
    raw = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
    try:
        when = parsedate_to_datetime(raw) if "," in raw or raw[:3].isalpha() else datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return when.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def parse_feed(source: str, xml_bytes: bytes) -> list[Story]:
    root = ET.fromstring(xml_bytes)
    stories = []
    for item in root.findall(".//item")[:30]:
        title = _clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        if len(title) < 12 or not link.startswith("http"):
            continue
        summary = _clean(item.findtext("description") or "")
        stories.append(Story(title=title, link=link, source=source, image=_image(item),
                             summary=summary[:240], published=_published(item)))
    return stories


async def _fetch(client: httpx.AsyncClient, source: str, url: str) -> list[Story]:
    try:
        response = await client.get(url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        return parse_feed(source, response.content)
    except (httpx.HTTPError, ET.ParseError) as e:
        logger.warning("News feed %s (%s) failed: %s", source, url, type(e).__name__)
        return []


def _title_key(story: Story) -> str:
    return re.sub(r"[^a-z0-9]+", " ", story.title.lower())[:70]


def _mix(groups: list[list[Story]], limit: int) -> list[Story]:
    """Newest first, but no more than two from one source in a row, and no repeats.

    Each step takes the newest story whose source hasn't just had two in a row;
    only when nothing else is left does a source get a third.
    """
    queues: dict[str, list[Story]] = {}
    for story in sorted((s for g in groups for s in g), key=lambda s: s.published or "", reverse=True):
        queues.setdefault(story.source, []).append(story)
    out, seen, run_source, run = [], set(), None, 0
    while len(out) < limit and any(queues.values()):
        heads = sorted((q[0] for q in queues.values() if q), key=lambda s: s.published or "", reverse=True)
        allowed = [s for s in heads if not (s.source == run_source and run >= 2)] or heads
        story = allowed[0]
        queues[story.source].pop(0)
        if _title_key(story) in seen:
            continue
        seen.add(_title_key(story))
        out.append(story)
        run = run + 1 if story.source == run_source else 1
        run_source = story.source
    return out


async def get_category(key: str, *, limit: int = 30, refresh: bool = False,
                       client: httpx.AsyncClient | None = None) -> list[Story]:
    category = BY_KEY.get(key) or BY_KEY["top"]
    cached = _cache.get(category.key)
    if cached and not refresh and time.time() - cached[0] < CACHE_TTL_S:
        return cached[1][:limit]
    lock = _locks.setdefault(category.key, asyncio.Lock())
    async with lock:
        cached = _cache.get(category.key)
        if cached and not refresh and time.time() - cached[0] < CACHE_TTL_S:
            return cached[1][:limit]
        owns = client is None
        client = client or httpx.AsyncClient()
        try:
            groups = await asyncio.gather(*(_fetch(client, source, url) for source, url in category.feeds))
        finally:
            if owns:
                await client.aclose()
        stories = _mix(list(groups), 40)
        if stories:
            _cache[category.key] = (time.time(), stories)
        elif cached:
            return cached[1][:limit]            # keep showing the last good set
        return stories[:limit]


def ago(published: str, now: datetime | None = None) -> str:
    if not published:
        return ""
    try:
        seconds = ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(published)).total_seconds()
    except ValueError:
        return ""
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


SUGGEST_MARKER = "luna-suggest"


def embed_suggestions(text: str, suggestions: list[dict]) -> str:
    """Buttons under a reply (<!--luna-suggest:[{label, message}]-->); tapping one sends its message."""
    if not suggestions:
        return text
    payload = json.dumps(suggestions, ensure_ascii=True, separators=(",", ":")).replace("--", "-\\u002d")
    return f"{text}\n\n<!--{SUGGEST_MARKER}:{payload}-->"


def category_suggestions(current: str) -> list[dict]:
    return [{"label": c.label if c.key != "top" else "Top", "message": f"{c.label if c.key != 'top' else 'Top'} news"}
            for c in CATEGORIES if c.key != current]


def render_answer(key: str, stories: list[Story], now: datetime | None = None) -> str:
    """Chat reply: headline cards with images, more headlines as a list, and category buttons."""
    from server.services.skill_runtime.runner import embed_cards

    category = BY_KEY.get(key) or BY_KEY["top"]
    day = (now or datetime.now()).strftime("%A, %B %d").replace(" 0", " ")
    if not stories:
        text = f"I couldn't reach the {category.label.lower()} news feeds just now. Try again in a minute."
        return embed_suggestions(text, category_suggestions(category.key))
    with_images = [s for s in stories if s.image][:6]
    rest = [s for s in stories if s not in with_images][:6]
    lines = [f"**{category.label}** · {day}"]
    if rest:
        lines += ["", "More headlines:"]
        lines += [f"- [{s.title}]({s.link}) · {s.source}" + (f" · {ago(s.published, now)}" if s.published else "") for s in rest]
    cards = [{"title": s.title, "url": s.link, "image": s.image,
              "site": " · ".join(x for x in (s.source, ago(s.published, now)) if x)} for s in with_images]
    return embed_suggestions(embed_cards("\n".join(lines), cards), category_suggestions(category.key))


def stories_json(stories: list[Story]) -> list[dict]:
    return [{**asdict(s), "ago": ago(s.published)} for s in stories]

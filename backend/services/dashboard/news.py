import asyncio
import re
import time
import xml.etree.ElementTree as ET

import httpx

from backend.config import settings
from backend.services.dashboard.common import HEADERS, log

FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Top", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
    ("AP News", "https://feeds.apnews.com/rss/apf-topnews"),
]
NEWS_TTL = 300
MEDIA_NS = "http://search.yahoo.com/mrss/"

_news_cache: list[dict] = []
_news_ts: float = 0


def clean_title(text: str) -> str:
    text = re.sub(r"<!\[CDATA\[|\]\]>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+-\s+[A-Z][^-]+$", "", text)
    return text.strip()


def rss_image(item) -> str:
    for selector in (f"{{{MEDIA_NS}}}content", f"{{{MEDIA_NS}}}thumbnail"):
        el = item.find(selector)
        if el is not None:
            url = el.get("url", "")
            if url.startswith("http"):
                return url
    el = item.find("enclosure")
    if el is not None and "image" in el.get("type", ""):
        url = el.get("url", "")
        if url.startswith("http"):
            return url
    return ""


async def fetch_feed(client: httpx.AsyncClient, source: str, url: str) -> list[dict]:
    try:
        response = await client.get(
            url,
            headers={**HEADERS, "Accept": "application/xml,text/xml,*/*"},
            timeout=10.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        items = []
        for item in root.findall(".//item")[:15]:
            title = clean_title(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            if len(title) > 12:
                image = rss_image(item)
                items.append({"source": source, "title": title, "link": link, "image": image or None, "provider": "RSS"})
        log(f"[news] {source}: {len(items)} items")
        return items
    except Exception as exc:
        log(f"[news] {source}: failed - {type(exc).__name__}: {exc}")
        return []


async def fetch_thenewsapi(client: httpx.AsyncClient) -> list[dict]:
    token = settings.the_news_api.strip()
    if not token:
        return []
    try:
        response = await client.get(
            "https://api.thenewsapi.com/v1/news/top",
            params={"api_token": token, "locale": "us", "language": "en", "limit": 50},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        items = []
        for item in data.get("data", []):
            title = clean_title(item.get("title") or "")
            link = (item.get("url") or "").strip()
            source = item.get("source") or item.get("source_name") or item.get("source_domain") or "TheNewsAPI"
            if len(title) > 12:
                items.append({
                    "source": str(source),
                    "title": title,
                    "link": link,
                    "image": item.get("image_url"),
                    "published_at": item.get("published_at"),
                    "provider": "TheNewsAPI",
                })
        log(f"[news] TheNewsAPI: {len(items)} items")
        return items
    except Exception as exc:
        log(f"[news] TheNewsAPI failed - {type(exc).__name__}: {exc}")
        return []


async def refresh_news() -> list[dict]:
    global _news_cache, _news_ts
    log("[news] refreshing feeds...")
    async with httpx.AsyncClient() as client:
        items = await fetch_thenewsapi(client)
        results = []
        if len(items) < 10:
            results = await asyncio.gather(
                *[fetch_feed(client, source, url) for source, url in FEEDS],
                return_exceptions=True,
            )
    for result in results:
        if isinstance(result, list):
            items.extend(result)

    seen: set[str] = set()
    deduped = []
    for item in items:
        key = item["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    _news_cache = deduped[:60]
    _news_ts = time.time()
    log(f"[news] total {len(_news_cache)} unique items cached")
    return _news_cache


async def get_news() -> list[dict]:
    if time.time() - _news_ts > NEWS_TTL or not _news_cache:
        await refresh_news()
    return _news_cache


_TOPIC_STOPWORDS = {"the", "news", "today", "todays", "today's", "latest", "headlines", "about", "on", "in", "of", "and"}


async def daily_news(topic: str = "", limit: int = 8) -> str:
    """Today's headlines for the `daily_news` tool: numbered, with source and link,
    optionally only those about a topic. Links come straight from the feeds."""
    limit = max(1, min(int(limit or 8), 20))
    items = await get_news()
    if not items:
        return "Error: no news feeds could be reached right now."
    words = [w for w in re.findall(r"[a-z0-9']+", (topic or "").lower()) if w not in _TOPIC_STOPWORDS and len(w) > 1]
    if words:
        items = [i for i in items if any(re.search(rf"\b{re.escape(w)}", i["title"].lower()) for w in words)]
        if len(items) < 3:
            found = "".join(f"\n- {i['title']} — {i['source']} ({i['link']})" for i in items)
            return (f"Today's top headlines have {len(items)} item(s) about “{topic}”.{found}\n"
                    "For more, look it up with the news-search skill (use_skill) or web_search.")
    lines = [f"{n}. {i['title']} — {i['source']}" + (f" ({i['link']})" if i.get("link") else "")
             for n, i in enumerate(items[:limit], 1)]
    heading = f"Today's headlines about “{topic}”" if words else "Today's top headlines"
    return f"{heading} ({time.strftime('%A %d %B')}):\n" + "\n".join(lines)

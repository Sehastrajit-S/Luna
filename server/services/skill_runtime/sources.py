"""Generic search execution for the skill runtime.

Nothing here knows about any domain. Skills supply the specifics as data:

* run_searches  — many queries in parallel (DuckDuckGo text or news), with a
                  recency filter that falls back to "any time" when empty.
* filter / rewrite — keep_urls / drop_urls / url_rewrites from the skill.
* liveness      — drop results whose page is gone: 404/410, a redirect that
                  loses the item id, the skill's "dead" phrases in the page,
                  or the skill's status_apis (e.g. a site's public API).
* labels        — values pulled out of result URLs (e.g. an organisation
                  slug) so the answer writer doesn't mix up results.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

SEARCH_CONCURRENCY = 4
PER_HOST_CONCURRENCY = 3
BODY_SCAN_BYTES = 400_000
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
_TRACKING_RE = re.compile(r"[?&](?:utm_[a-z]+|trk|refId|trackingId|gclid|fbclid)=[^&#]*", re.IGNORECASE)
_ITEM_ID_RE = re.compile(r"/(\d{5,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?=[/?#-]|$)", re.IGNORECASE)
GENERIC_DEAD_PHRASES = ["page not found", "this page no longer exists", "404 not found"]
_SITE_FILTER_RE = re.compile(r"\((?:\s*(?:OR\s+)?site:\S+)+\s*\)|\bsite:\S+", re.IGNORECASE)


@dataclass
class Result:
    query: str
    title: str
    snippet: str
    url: str
    date: str = ""
    source: str = ""
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def host(self) -> str:
        return urlsplit(self.url).netloc.lower().removeprefix("www.")


# ── Searching ────────────────────────────────────────────────────────────────

def _ddg(query: str, max_results: int, timelimit: str | None, backend: str) -> list[dict]:
    from ddgs import DDGS

    kwargs = {"max_results": max_results}
    if timelimit:
        kwargs["timelimit"] = timelimit
    try:
        ddgs = DDGS()
        return list(ddgs.news(query, **kwargs) if backend == "news" else ddgs.text(query, **kwargs))
    except Exception as e:  # ddgs raises on "no results" as well as real failures
        logger.info("Search %r (timelimit=%s) returned nothing: %s", query, timelimit, e)
        return []


async def run_searches(queries: list[str], per_query: int = 6, recency: str | None = None,
                       backend: str = "text") -> list[Result]:
    """Run queries concurrently; de-duplicate by URL; keep query order."""
    sem = asyncio.Semaphore(SEARCH_CONCURRENCY)

    async def one(query: str) -> list[Result]:
        async with sem:
            rows = await asyncio.to_thread(_ddg, query, per_query, recency, backend)
            if not rows and recency:
                rows = await asyncio.to_thread(_ddg, query, per_query, None, backend)
            if not rows:
                # The provider intermittently returns nothing (rate limits);
                # retry once, then broaden by dropping site: filters.
                await asyncio.sleep(1.2)
                rows = await asyncio.to_thread(_ddg, query, per_query, None, backend)
            if not rows and "site:" in query:
                broad = " ".join(_SITE_FILTER_RE.sub(" ", query).split())
                if broad:
                    rows = await asyncio.to_thread(_ddg, broad, per_query, None, backend)
                    if rows:
                        logger.info("Search %r empty; broadened to %r", query, broad)
        out = []
        for r in rows:
            url = _TRACKING_RE.sub("", (r.get("href") or r.get("url") or "").strip()).rstrip("?&")
            if url.startswith("http"):
                out.append(Result(query, (r.get("title") or "").strip(), " ".join((r.get("body") or "").split()),
                                  url, date=(r.get("date") or "")[:10], source=r.get("source") or ""))
        print(f"[web] search {query!r}: {len(out)} results")
        return out

    batches = await asyncio.gather(*(one(q) for q in queries))
    seen, merged = set(), []
    for batch in batches:
        for result in batch:
            key = result.url.split("#")[0].rstrip("/").lower()
            if key not in seen:
                seen.add(key)
                merged.append(result)
    return merged


# ── Filtering, rewriting, labelling (all driven by skill data) ───────────────

def rewrite_urls(results: list[Result], rewrites: list[dict] | None) -> list[Result]:
    for rule in rewrites or []:
        pattern = re.compile(rule["match"], re.IGNORECASE)
        for r in results:
            r.url = pattern.sub(rule.get("replace", ""), r.url)
    return results


def filter_results(results: list[Result], keep: list[str] | None, drop: list[str] | None) -> list[Result]:
    keep_re = [re.compile(p, re.IGNORECASE) for p in keep or []]
    drop_re = [re.compile(p, re.IGNORECASE) for p in drop or []]
    return [
        r for r in results
        if not any(p.search(r.url) for p in drop_re) and (not keep_re or any(p.search(r.url) for p in keep_re))
    ]


def apply_labels(results: list[Result], labels: list[dict] | None) -> list[Result]:
    """labels: [{"match": regex, "name": "Company", "group": 1}] → r.labels["Company"]."""
    rules = [(re.compile(rule["match"], re.IGNORECASE), rule["name"], int(rule.get("group", 1))) for rule in labels or []]
    for r in results:
        for pattern, name, group in rules:
            if name not in r.labels and (m := pattern.search(r.url)):
                r.labels[name] = m.group(group)
    return results


# ── Liveness ─────────────────────────────────────────────────────────────────

def _json_values(data, path: str) -> set[str]:
    """Values at a dotted path, walking lists: "items.id" → {every items[i].id}."""
    items = [data]
    for key in path.split("."):
        nxt = []
        for item in items:
            if isinstance(item, list):
                nxt.extend(x.get(key) for x in item if isinstance(x, dict))
            elif isinstance(item, dict):
                nxt.append(item.get(key))
        items = nxt
    flat = []
    for item in items:
        flat.extend(item if isinstance(item, list) else [item])
    return {str(v) for v in flat if v is not None}


class LinkChecker:
    """status_apis (from the skill):
      {"match": regex, "url": "https://api.example/{1}/items/{2}"}                  404 → gone
      {"match": regex, "list_url": "https://api.example/{1}/items", "ids": "items.id", "id_group": 2}
                                                                                   id missing → gone
    """

    def __init__(self, client: httpx.AsyncClient, dead_phrases: list[str], status_apis: list[dict] | None):
        self.client = client
        self.dead_phrases = [p.lower() for p in dead_phrases]
        self.apis = [(re.compile(a["match"], re.IGNORECASE), a) for a in status_apis or []]
        self.host_limits: dict[str, asyncio.Semaphore] = {}
        self.lists: dict[str, asyncio.Future] = {}

    def _limit(self, url: str) -> asyncio.Semaphore:
        return self.host_limits.setdefault(urlsplit(url).netloc, asyncio.Semaphore(PER_HOST_CONCURRENCY))

    async def _fetch(self, url: str, scan_body: bool) -> tuple[int, str, str] | None:
        for attempt in range(2):
            try:
                async with self._limit(url):
                    async with self.client.stream("GET", url) as response:
                        status, final, body = response.status_code, str(response.url), ""
                        if scan_body and status == 200 and "html" in response.headers.get("content-type", ""):
                            chunks, size = [], 0
                            async for chunk in response.aiter_bytes():
                                chunks.append(chunk)
                                size += len(chunk)
                                if size >= BODY_SCAN_BYTES:
                                    break
                            body = b"".join(chunks).decode("utf-8", "ignore").lower()
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 0:
                    await asyncio.sleep(0.8)
                    continue
                return None
            except (httpx.HTTPError, ValueError):
                return None
            if status == 429 and attempt == 0:
                await asyncio.sleep(1.5)
                continue
            return status, final, body
        return None

    async def _list_ids(self, url: str, path: str) -> set[str] | None:
        try:
            r = await self.client.get(url)
            if r.status_code == 404:
                return set()
            r.raise_for_status()
            return _json_values(r.json(), path)
        except (httpx.HTTPError, ValueError):
            return None

    @staticmethod
    def _fill(template: str, match: re.Match) -> str:
        return re.sub(r"\{(\d+)\}", lambda m: match.group(int(m.group(1))), template)

    async def is_dead(self, url: str) -> bool:
        """True only when sure. Timeouts, bot-blocks (403) and rate limits count
        as alive — the link may well work in the user's browser."""
        for pattern, api in self.apis:
            if not (m := pattern.search(url)):
                continue
            if "list_url" in api:
                list_url = self._fill(api["list_url"], m)
                if list_url not in self.lists:
                    self.lists[list_url] = asyncio.ensure_future(self._list_ids(list_url, api.get("ids", "id")))
                ids = await self.lists[list_url]
                if ids is not None:
                    return m.group(int(api.get("id_group", 2))) not in ids
            elif "url" in api:
                fetched = await self._fetch(self._fill(api["url"], m), scan_body=False)
                if fetched is not None:
                    return fetched[0] in (404, 410)
            break

        fetched = await self._fetch(url, scan_body=bool(self.dead_phrases))
        if fetched is None:
            return False
        status, final, body = fetched
        if status in (404, 410) or "error=true" in final:
            return True
        ids = _ITEM_ID_RE.findall(url)
        if ids and final.rstrip("/") != url.rstrip("/") and not any(i in final for i in ids):
            return True   # redirected away from the item (e.g. a removed listing → its index page)
        return bool(body) and any(p in body for p in self.dead_phrases)


async def drop_dead(results: list[Result], dead_phrases: list[str] | None = None,
                    status_apis: list[dict] | None = None) -> tuple[list[Result], int]:
    if not results:
        return results, 0
    phrases = GENERIC_DEAD_PHRASES + list(dead_phrases or [])
    async with httpx.AsyncClient(timeout=httpx.Timeout(6.0, connect=4.0), follow_redirects=True,
                                 headers={"User-Agent": _UA}) as client:
        checker = LinkChecker(client, phrases, status_apis)
        dead = await asyncio.gather(*(checker.is_dead(r.url) for r in results))
    kept = [r for r, d in zip(results, dead) if not d]
    if len(kept) < len(results):
        print(f"[web] dropped {len(results) - len(kept)} result(s) whose pages are gone")
    return kept, len(results) - len(kept)


# ── Page metadata (cards) ────────────────────────────────────────────────────

META_SCAN_BYTES = 1_200_000
_LD_JSON_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL)


def _meta_tag(html: str, name: str) -> str | None:
    for pattern in (
        rf'<meta[^>]+(?:property|name|itemprop)=["\']{re.escape(name)}["\'][^>]*?content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*?(?:property|name|itemprop)=["\']{re.escape(name)}["\']',
    ):
        if m := re.search(pattern, html, re.IGNORECASE):
            return m.group(1).strip()
    return None


def _ld_objects(html: str):
    import json

    for block in _LD_JSON_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                yield item
                stack.extend(v for k, v in item.items() if k in ("@graph", "mainEntity", "itemListElement", "item"))
                if isinstance(item.get("@graph"), list):
                    stack.extend(item["@graph"])
            elif isinstance(item, list):
                stack.extend(item)


def _first_url(value) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _first_url(value[0])
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    return None


def extract_page_meta(html: str, base_url: str, image_patterns: list[str] | None = None,
                      price_patterns: list[str] | None = None) -> dict:
    """Title, main image and price from a page: structured data (JSON-LD),
    Open Graph / Twitter tags, then the skill's own patterns."""
    import html as _html
    from urllib.parse import urljoin

    meta = {"title": None, "image": None, "price": None, "currency": None, "site": None}
    for obj in _ld_objects(html):
        types = obj.get("@type")
        types = types if isinstance(types, list) else [types]
        if not any(str(t).lower() in ("product", "productgroup", "offer") for t in types):
            continue
        meta["title"] = meta["title"] or obj.get("name")
        meta["image"] = meta["image"] or _first_url(obj.get("image"))
        offers = obj.get("offers")
        offers = offers[0] if isinstance(offers, list) and offers else offers
        if isinstance(offers, dict):
            price = offers.get("price") or offers.get("lowPrice")
            if price not in (None, "", 0, "0"):
                meta["price"] = meta["price"] or str(price)
                meta["currency"] = meta["currency"] or offers.get("priceCurrency")
    meta["title"] = meta["title"] or _meta_tag(html, "og:title") or _meta_tag(html, "twitter:title")
    meta["image"] = meta["image"] or _meta_tag(html, "og:image") or _meta_tag(html, "twitter:image") \
        or _meta_tag(html, "og:image:secure_url")
    if not meta["image"] and (m := re.search(r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)', html, re.I)):
        meta["image"] = m.group(1)
    for pattern in image_patterns or []:
        if meta["image"]:
            break
        if m := re.search(pattern, html, re.IGNORECASE | re.DOTALL):
            meta["image"] = m.group(1)
    meta["price"] = meta["price"] or _meta_tag(html, "product:price:amount") or _meta_tag(html, "og:price:amount") \
        or _meta_tag(html, "price")
    meta["currency"] = meta["currency"] or _meta_tag(html, "product:price:currency") or _meta_tag(html, "og:price:currency") \
        or _meta_tag(html, "priceCurrency")
    for pattern in price_patterns or []:
        if meta["price"]:
            break
        if m := re.search(pattern, html, re.IGNORECASE | re.DOTALL):
            meta["price"] = m.group(1)
    meta["site"] = _meta_tag(html, "og:site_name")
    if meta["image"]:
        meta["image"] = urljoin(base_url, _html.unescape(meta["image"]))
        if not meta["image"].startswith("https://"):
            meta["image"] = None
    if meta["title"]:
        title = " ".join(_html.unescape(str(meta["title"])).split())
        # Drop store branding around the name: "Amazon.com: X", "X : Target", "X - Walmart.com".
        title = re.sub(r"^[A-Z][\w&'.-]*\.(?:com|co\.uk|ca|de|in)\s*[:|\-–]\s*", "", title)
        title = re.sub(r"\s*[:|\-–]\s*(?:[A-Z][\w&'.-]*\.(?:com|co\.uk|ca)|Target|Walmart|Best Buy|Newegg)\s*$", "", title)
        meta["title"] = title[:140]
    return meta


async def fetch_cards(results: list[Result], limit: int, image_patterns: list[str] | None = None,
                      price_patterns: list[str] | None = None, require_image: bool = True) -> list[dict]:
    """Visit result pages and build display cards (image, exact title, price, link)."""
    sem_by_host: dict[str, asyncio.Semaphore] = {}

    async def one(client: httpx.AsyncClient, r: Result) -> dict | None:
        sem = sem_by_host.setdefault(r.host, asyncio.Semaphore(2))
        try:
            async with sem:
                async with client.stream("GET", r.url) as response:
                    if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
                        return None
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        chunks.append(chunk)
                        size += len(chunk)
                        if size >= META_SCAN_BYTES:
                            break
            html = b"".join(chunks).decode("utf-8", "ignore")
        except (httpx.HTTPError, ValueError):
            return None
        meta = extract_page_meta(html, r.url, image_patterns, price_patterns)
        if require_image and not meta["image"]:
            return None
        price = (meta["price"] or "").replace(",", "").strip()
        try:
            price = f"{float(price):,.2f}" if price else ""
        except ValueError:
            price = ""
        currency = (meta["currency"] or ("USD" if price else "")).upper()
        return {"title": meta["title"] or r.title, "url": r.url, "image": meta["image"], "price": price,
                "currency": currency, "site": meta["site"] or r.host}

    headers = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html,application/xhtml+xml"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=True, headers=headers) as client:
        cards = await asyncio.gather(*(one(client, r) for r in results[: limit * 2]))
    seen_titles, out = set(), []
    for card in cards:
        if not card:
            continue
        key = " ".join(re.findall(r"[a-z0-9]+", card["title"].lower())[:6])
        if key in seen_titles:
            continue
        seen_titles.add(key)
        out.append(card)
        if len(out) >= limit:
            break
    return out


def format_results(results: list[Result], queries: list[str], removed: int = 0) -> str:
    """Numbered results grouped by query, plus a References block (the format
    the answer writer and the citation linker expect)."""
    if not results:
        return "No live results found." if removed else "No results found."
    blocks, refs, n = [], [], 0
    for query in queries:
        group = [r for r in results if r.query == query]
        if not group:
            continue
        lines = [f"Results for: {query}"] if len(queries) > 1 else []
        for r in group:
            n += 1
            extra = [f"{k} (from link): {v}" for k, v in r.labels.items()]
            if r.date:
                extra.append(f"Date: {r.date}")
            if r.source:
                extra.append(f"Source: {r.source}")
            extra.append(f"Site: {r.host}")
            lines.append(f"[{n}] {r.title}\nSnippet: {r.snippet}\n" + "\n".join(extra) + f"\nURL: {r.url}")
            refs.append(f"[{n}] {r.title} - {r.url}")
        blocks.append("\n\n".join(lines))
    note = f"\n\n(Removed {removed} result(s) whose pages no longer exist.)" if removed else ""
    return "\n\n".join(blocks) + note + "\n\nReferences:\n" + "\n".join(refs)

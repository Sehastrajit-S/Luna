"""Free fallback when no SerpApi key is set: web search each store's own site.

One DuckDuckGo search per store (site:walmart.com …), keeping only real
product pages. The price comes from the search snippet, or from the product
page's structured data (JSON-LD / meta tags). Some stores hide prices from
pages fetched this way (Costco often does, and prices that vary by store
need a ZIP), so a listing may come back with a link but no price.
"""
from __future__ import annotations

import asyncio
import re

import httpx

from server.services.shopping.serpapi import Listing
from server.services.shopping.stores import Store

# A store's product page, not a search, category or help page.
PRODUCT_PAGE = {
    "walmart": re.compile(r"walmart\.com/ip/", re.I),
    "costco": re.compile(r"costco\.com/[^?#]+\.product\.", re.I),
    "target": re.compile(r"target\.com/p/", re.I),
    "sams": re.compile(r"samsclub\.com/p/", re.I),
    "safeway": re.compile(r"safeway\.com/shop/product-details\.", re.I),
}
_PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*\.\d{2})\b")
CANDIDATES_PER_STORE = 3
PAGE_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


def snippet_price(text: str) -> float | None:
    match = _PRICE_RE.search(text or "")
    return float(match.group(1).replace(",", "")) if match else None


async def _page_meta(client: httpx.AsyncClient, url: str) -> dict:
    from server.services.skill_runtime.sources import META_SCAN_BYTES, extract_page_meta

    try:
        async with client.stream("GET", url) as response:
            if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
                return {}
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= META_SCAN_BYTES:
                    break
    except (httpx.HTTPError, ValueError):
        return {}
    return extract_page_meta(b"".join(chunks).decode("utf-8", "ignore"), url)


async def search_stores(product: str, stores: list[Store], *, score, min_match: float,
                        search=None, client: httpx.AsyncClient | None = None) -> dict[str, Listing]:
    """Best-matching product page per store, with a price when one could be read."""
    from server.services.skill_runtime.sources import _UA, run_searches

    search = search or run_searches
    queries = {store.key: f"{product} site:{store.domain}" for store in stores}
    results = await search(list(queries.values()), per_query=8)

    candidates: dict[str, list] = {}
    for position, r in enumerate(results):
        for store in stores:
            pattern = PRODUCT_PAGE.get(store.key)
            if pattern and pattern.search(r.url):
                s = score(product, r.title)
                if s >= min_match:
                    candidates.setdefault(store.key, []).append((s, -position, r))
                break

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=PAGE_TIMEOUT, follow_redirects=True, headers={
        "User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html,application/xhtml+xml"})
    try:
        async def resolve(store: Store) -> tuple[str, Listing | None]:
            ranked = sorted(candidates.get(store.key, []), key=lambda c: (c[0], c[1]), reverse=True)[:CANDIDATES_PER_STORE]
            fallback = None
            for s, neg_pos, r in ranked:
                title, price, image = r.title, snippet_price(r.snippet), ""
                if price is None:
                    meta = await _page_meta(client, r.url)
                    try:
                        price = float(str(meta.get("price") or "").replace(",", "")) or None
                    except ValueError:
                        price = None
                    title = meta.get("title") or title
                    image = meta.get("image") or ""
                listing = Listing(
                    title=" ".join(str(title).split()), source=store.name, price=price,
                    price_text=f"${price:,.2f}" if price is not None else "", url=r.url, image=image,
                    rating=None, reviews=None, delivery="", position=-neg_pos + 1,
                )
                if price is not None:
                    return store.key, listing
                fallback = fallback or listing     # a page to link to, price not shown
            return store.key, fallback

        resolved = await asyncio.gather(*(resolve(store) for store in stores))
    finally:
        if owns_client:
            await client.aclose()
    return {key: listing for key, listing in resolved if listing}

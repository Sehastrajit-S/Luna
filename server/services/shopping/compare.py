"""Compare one product's price across Walmart, Costco, Target, Sam's Club and Safeway.

One general Google Shopping search usually lists the big stores; each store it
missed gets a follow-up search naming that store, up to shopping_max_searches
(every search is one SerpApi credit). For each store the listing that best
matches the product wins; the cheapest of those is called out.
"""
from __future__ import annotations

import json
import re

import httpx

from server.config import settings
from server.services.audit_log import record_audit
from server.services.shopping import serpapi
from server.services.shopping.serpapi import Listing, ShoppingError
from server.services.shopping.stores import Store, resolve_stores, store_for_source

_WORD_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOP = {"the", "a", "an", "of", "for", "and", "with", "at", "in", "on", "to", "pack", "count", "ct", "oz", "fl"}
# A store's listing has to share at least this much of the product's wording.
MIN_MATCH = 0.5

# Icons the chat will render (markdown.js ICON_URL): Google's favicon hosts only.
ICON_HOSTS = re.compile(r"https://(?:[a-z0-9-]+\.gstatic\.com/|www\.google\.com/s2/favicons\?)[^\s\"'<>()]*$", re.I)

WEB_NOTE = ("Prices come from free web search and the stores' own pages, so they can be missing or out of "
            "date. Add a SerpApi key in Settings for live Google Shopping prices.")

NOTE = ("Prices are Google Shopping listings for each store's own website. In-store, member, "
        "pickup and sale prices can differ, and package sizes vary between stores.")


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOP and len(w) > 1}


def _lead_word(product: str) -> str | None:
    """The first real word the user typed, usually the brand ("Kirkland paper towels")."""
    for word in _WORD_RE.findall((product or "").lower()):
        if word not in _STOP and len(word) > 1 and not word[0].isdigit():
            return word
    return None


def match_score(product: str, title: str) -> float:
    """Share of the product's words in the listing title; 0 when the lead word
    (brand) is missing, so "Kirkland paper towels" never matches Brawny."""
    want, have = _tokens(product), _tokens(title)
    lead = _lead_word(product)
    if not want or (lead and lead not in have):
        return 0.0
    return len(want & have) / len(want)


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def same_size(product: str, title: str) -> bool:
    """Every number the user gave (count, ounces, pack size) appears in the listing.
    "Tide Pods 81 count" vs "Tide PODS, 156 Count" isn't the same thing to compare."""
    wanted = set(_NUM_RE.findall(product or ""))
    return wanted <= set(_NUM_RE.findall(title or ""))


def _best(product: str, listings: list[Listing]) -> tuple[Listing | None, float]:
    """The store's listing for this product: it must be the same product first
    (MIN_MATCH), then the requested size wins over a better-worded other size."""
    best, best_key = None, None
    for item in listings:
        if item.price is None:
            continue
        score = match_score(product, item.title)
        if score < MIN_MATCH:
            continue
        key = (same_size(product, item.title), score, -item.position)
        if best_key is None or key > best_key:
            best, best_key = item, key
    return best, (best_key[1] if best_key else 0.0)


def _offer(product: str, store: Store, item: Listing, score: float) -> dict:
    return {
        "store": store.name, "status": "found", "title": item.title, "price": item.price,
        "icon": item.source_icon if ICON_HOSTS.match(item.source_icon or "") else store.icon,
        "price_text": item.price_text or f"${item.price:,.2f}", "url": item.url, "image": item.image,
        "rating": item.rating, "reviews": item.reviews, "delivery": item.delivery,
        "match": round(score, 2), "same_size": same_size(product, item.title),
    }


async def compare_store_prices(product: str, stores: list[str] | None = None, *,
                               client: httpx.AsyncClient | None = None) -> dict:
    product = " ".join(str(product or "").split())
    if not product:
        raise ShoppingError("bad_request", "Say which product to compare, e.g. 'Tide Pods 81 count'.")
    chosen = resolve_stores(stores)
    if not settings.serpapi_api_key:
        return await _compare_via_web(product, chosen)
    budget = max(1, int(settings.shopping_max_searches or 1))
    found: dict[str, dict] = {}
    missed: dict[str, str] = {}
    searches = 0

    def take(listings: list[Listing], only: Store | None = None) -> None:
        by_store: dict[str, list[Listing]] = {}
        for item in listings:
            store = store_for_source(item.source, [only] if only else chosen)
            if store and store.key not in found:
                by_store.setdefault(store.key, []).append(item)
        for store in chosen:
            item, score = _best(product, by_store.get(store.key, []))
            if item and score >= MIN_MATCH:
                found[store.key] = _offer(product, store, item, score)

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=serpapi.TIMEOUT)
    status = "ok"
    try:
        try:
            take(await serpapi.search(product, api_key=settings.serpapi_api_key,
                                      location=settings.shopping_location, client=client))
            searches += 1
        except ShoppingError as e:
            status = e.kind
            raise
        for store in chosen:
            if store.key in found:
                continue
            if searches >= budget:
                missed[store.key] = "not_searched"
                continue
            try:
                take(await serpapi.search(f"{product} {store.name}", api_key=settings.serpapi_api_key,
                                          location=settings.shopping_location, client=client), only=store)
                searches += 1
            except ShoppingError as e:
                # Keep what we have; a quota or rate limit ends the follow-ups.
                missed[store.key] = e.kind
                if e.kind in ("quota_exhausted", "rate_limited", "invalid_key"):
                    budget = searches
                continue
            if store.key not in found:
                missed[store.key] = "not_found"
    finally:
        if owns_client:
            await client.aclose()
        record_audit(
            "external_read", tool="compare_store_prices", risk="safe", status=status,
            args={"provider": "serpapi", "service": "google_shopping", "product": product,
                  "stores": [s.key for s in chosen]},
            result=f"{len(found)}/{len(chosen)} stores priced, {searches} search(es)",
        )

    return _result(product, chosen, found, missed, searches, source="google_shopping")


def _result(product: str, chosen: list[Store], found: dict[str, dict], missed: dict[str, str],
            searches: int, *, source: str) -> dict:
    results = []
    for store in chosen:
        if store.key in found:
            results.append(found[store.key])
        else:
            results.append({"store": store.name, "status": missed.get(store.key, "not_found"), "icon": store.icon})
    priced = [r for r in results if r["status"] == "found"]
    # A bigger pack isn't "cheaper": compare like with like when we can.
    comparable = [r for r in priced if r["same_size"]] or priced
    cheapest = min(comparable, key=lambda r: r["price"]) if comparable else None
    return {
        "product": product,
        "location": settings.shopping_location or "United States (online prices)",
        "source": source,
        "searches_used": searches,
        "stores": results,
        "cheapest": {"store": cheapest["store"], "price": cheapest["price"], "title": cheapest["title"]} if cheapest else None,
        "note": NOTE if source == "google_shopping" else WEB_NOTE,
    }


async def _compare_via_web(product: str, chosen: list[Store], client: httpx.AsyncClient | None = None,
                           search=None) -> dict:
    """No SerpApi key: free web search of each store's site (see web.py)."""
    from server.services.shopping import web

    found: dict[str, dict] = {}
    missed: dict[str, str] = {}
    status = "ok"
    try:
        listings = await web.search_stores(product, chosen, score=match_score, min_match=MIN_MATCH,
                                           search=search, client=client)
    except Exception as e:                      # free search failing must not crash the chat
        status = "upstream_error"
        raise ShoppingError("upstream_error", "The free web search didn't respond. Try again in a minute.") from e
    finally:
        record_audit(
            "external_read", tool="compare_store_prices", risk="safe", status=status,
            args={"provider": "duckduckgo", "service": "web_search", "product": product,
                  "stores": [s.key for s in chosen]},
            result=f"web search across {len(chosen)} store site(s)",
        )
    for store in chosen:
        listing = listings.get(store.key)
        if listing is None:
            missed[store.key] = "not_found"
        elif listing.price is None:
            missed[store.key] = "price_hidden"
            found_page = {"store": store.name, "status": "price_hidden", "title": listing.title,
                          "url": listing.url, "icon": store.icon}
            found[store.key] = found_page
        else:
            found[store.key] = _offer(product, store, listing, match_score(product, listing.title))
    return _result(product, chosen, found, missed, len(chosen), source="web")


_STATUS_TEXT = {
    "not_found": "no listing from this store matched",
    "price_hidden": "found the product page, but it doesn't show a price without visiting the store's site",
    "not_searched": "not checked (search limit reached; raise shopping_max_searches to check more stores)",
    "quota_exhausted": "not checked (SerpApi searches used up this month)",
    "rate_limited": "not checked (SerpApi rate limit)",
    "invalid_key": "not checked (SerpApi key rejected)",
    "upstream_error": "not checked (Google Shopping error)",
}


def _cell(text: str) -> str:
    return " ".join(str(text or "").replace("|", "/").split())


def _store_cell(r: dict) -> str:
    return f"![]({r['icon']}) {r['store']}" if r.get("icon") else r["store"]


def _cards(result: dict) -> list[dict]:
    return [{
        "title": f"{r['store']}: {r['title']}", "url": r["url"], "image": r["image"],
        "price": f"{r['price']:,.2f}", "currency": "USD", "site": r["store"], "icon": r.get("icon", ""),
    } for r in sorted((r for r in result["stores"] if r["status"] == "found"), key=lambda r: r["price"])
        if r.get("url") and r.get("image")]


def render_markdown(result: dict) -> str:
    """A complete answer built only from the listings: used when the user picks
    Compare store prices from the + menu, so no model can misquote a price."""
    from server.services.skill_runtime.runner import embed_cards

    priced = sorted((r for r in result["stores"] if r["status"] == "found"), key=lambda r: r["price"])
    hidden = [r for r in result["stores"] if r["status"] == "price_hidden"]
    missing = [r for r in result["stores"] if r["status"] not in ("found", "price_hidden")]
    if not priced and not hidden:
        lines = [f"I couldn't find **{_cell(result['product'])}** at any of these stores on Google Shopping."]
    else:
        if priced:
            best = next((r for r in priced if r["store"] == (result.get("cheapest") or {}).get("store")), priced[0])
            lead = f"**{_cell(result['product'])}** is cheapest at **{best['store']}** ({best['price_text']})."
        else:
            lead = f"I found **{_cell(result['product'])}** at these stores, but their pages don't show a price here."
        lines = [lead, "", "| Store | Item | Price |", "|---|---|---|"]
        lines += [f"| {_store_cell(r)} | {_cell(r['title'])}{'' if r.get('same_size', True) else ' (different size)'} | {_cell(r['price_text'])} |"
                  for r in priced]
        lines += [f"| {_store_cell(r)} | {_cell(r['title'])} | [See price]({r['url']}) |" for r in hidden]
    if missing:
        lines += ["", "Not priced: " + "; ".join(f"{r['store']} ({_STATUS_TEXT.get(r['status'], r['status'])})" for r in missing) + "."]
    lines += ["", f"_{result['note']}_"]
    return embed_cards("\n".join(lines), _cards(result))


def format_for_chat(result: dict) -> str:
    """Tool result for the model: compact facts, how to present them, and price cards for the UI."""
    from server.services.skill_runtime.runner import embed_cards

    rows = []
    for r in result["stores"]:
        if r["status"] == "found":
            rows.append({"store": r["store"], "item": r["title"], "price": r["price_text"],
                         **({} if r.get("same_size", True) else {"size": "different from what the user asked for"}),
                         **({"delivery": r["delivery"]} if r.get("delivery") else {})})
        else:
            rows.append({"store": r["store"], "price": None, "why": _STATUS_TEXT.get(r["status"], r["status"]),
                         **({"item": r["title"], "link": r["url"]} if r.get("url") else {})})
    facts = {"product": result["product"], "where": result["location"], "stores": rows,
             "cheapest": result["cheapest"], "note": result["note"]}
    guide = ("Present this as a table (Store | Item | Price), cheapest first, then name the cheapest store. "
             "Point out when items differ in size or count so prices aren't comparable, list stores with no "
             "price and why, and repeat the note in one short sentence. Only use prices shown here.")
    return embed_cards(json.dumps(facts, ensure_ascii=False) + "\n\n" + guide, _cards(result))

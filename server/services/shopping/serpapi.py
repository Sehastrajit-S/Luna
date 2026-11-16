"""Google Shopping listings through SerpApi (https://serpapi.com/google-shopping-api).

Errors are typed so the chat can say what to fix, and never include the
request URL: it carries the API key.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger("luna.shopping")

ENDPOINT = "https://serpapi.com/search.json"
TIMEOUT = httpx.Timeout(20.0, connect=6.0)


class ShoppingError(Exception):
    """kind: not_configured | invalid_key | quota_exhausted | rate_limited | upstream_error"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class Listing:
    title: str
    source: str
    price: float | None
    price_text: str
    url: str
    image: str
    rating: float | None
    reviews: int | None
    delivery: str
    position: int
    source_icon: str = ""


def _float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_listings(data: dict) -> list[Listing]:
    listings = []
    for i, item in enumerate(data.get("shopping_results") or []):
        if not isinstance(item, dict) or not item.get("title"):
            continue
        reviews = item.get("reviews")
        listings.append(Listing(
            title=str(item.get("title", "")).strip(),
            source=str(item.get("source", "")).strip(),
            price=_float(item.get("extracted_price")),
            price_text=str(item.get("price", "")).strip(),
            url=str(item.get("product_link") or item.get("link") or ""),
            image=str(item.get("thumbnail") or item.get("serpapi_thumbnail") or ""),
            rating=_float(item.get("rating")),
            reviews=int(reviews) if isinstance(reviews, (int, float)) else None,
            delivery=str(item.get("delivery") or ""),
            position=int(item.get("position") or i + 1),
            source_icon=str(item.get("source_icon") or ""),
        ))
    return listings


def _error_from(status: int, payload: dict) -> ShoppingError:
    detail = str(payload.get("error") or "").strip()
    lowered = detail.lower()
    if status in (401, 403) or "invalid api key" in lowered:
        return ShoppingError("invalid_key", "SerpApi rejected the API key. Check serpapi_api_key in Settings → Integrations.")
    if "run out of searches" in lowered or ("plan" in lowered and "searches" in lowered):
        return ShoppingError("quota_exhausted", "The SerpApi account has used all its searches for this month.")
    if status == 429:
        return ShoppingError("rate_limited", "SerpApi is rate limiting requests. Try again in a minute.")
    return ShoppingError("upstream_error", f"Google Shopping search failed ({status}){': ' + detail[:160] if detail else ''}.")


async def search(query: str, *, api_key: str, location: str = "", client: httpx.AsyncClient | None = None) -> list[Listing]:
    """One Google Shopping search (one SerpApi credit). Empty list when nothing matched."""
    if not api_key:
        raise ShoppingError(
            "not_configured",
            "Store price comparison needs a SerpApi key. Get a free one at serpapi.com "
            "(100 searches a month) and add it as serpapi_api_key in Settings → Integrations.",
        )
    params = {"engine": "google_shopping", "q": query, "gl": "us", "hl": "en", "api_key": api_key}
    if location:
        params["location"] = location

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)
    try:
        response = await client.get(ENDPOINT, params=params)
    except httpx.TimeoutException:
        raise ShoppingError("upstream_error", "Google Shopping didn't answer in time. Try again.") from None
    except httpx.HTTPError as e:
        # str(e) can include the URL, and with it the API key.
        logger.warning("SerpApi request failed: %s", type(e).__name__)
        raise ShoppingError("upstream_error", "Couldn't reach SerpApi. Check the internet connection.") from None
    finally:
        if owns_client:
            await client.aclose()

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200:
        raise _error_from(response.status_code, payload if isinstance(payload, dict) else {})
    if isinstance(payload, dict) and payload.get("error"):
        if "hasn't returned any results" in str(payload["error"]).lower():
            return []
        raise _error_from(200, payload)
    return parse_listings(payload if isinstance(payload, dict) else {})

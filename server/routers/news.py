"""News tab: GET /api/news?category=tech[&refresh=true]."""
from __future__ import annotations

from fastapi import APIRouter, Query

from server.services import news_feed

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
async def get_news(category: str = Query("top", max_length=32), refresh: bool = False, limit: int = Query(30, ge=1, le=40)):
    key = category if category in news_feed.BY_KEY else "top"
    stories = await news_feed.get_category(key, limit=limit, refresh=refresh)
    return {
        "category": key,
        "label": news_feed.BY_KEY[key].label,
        "categories": [{"key": c.key, "label": c.label} for c in news_feed.CATEGORIES],
        "stories": news_feed.stories_json(stories),
    }

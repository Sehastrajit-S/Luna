from fastapi import APIRouter, HTTPException

from backend.services.dashboard import articles, markets, news, weather

router = APIRouter(prefix="/api/luna", tags=["luna"])


@router.get("/news")
async def get_news():
    return await news.get_news()


@router.get("/stocks")
async def get_stocks():
    return await markets.get_stocks()


@router.get("/stocks/{symbol}/history")
async def get_stock_history(symbol: str):
    normalized = symbol.upper().strip()
    if normalized not in markets.US_SYMBOLS and normalized not in markets.CRYPTO_IDS:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    result = await markets.get_stock_history(normalized)
    if not result:
        raise HTTPException(status_code=502, detail="History unavailable")
    return result


@router.get("/weather")
async def get_weather():
    return await weather.get_weather()


@router.get("/article")
async def fetch_article(url: str):
    return await articles.fetch_article(url)

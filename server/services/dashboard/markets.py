import asyncio
import csv
import io
import time
from typing import Optional

import httpx

from backend.config import settings
from backend.services.dashboard.common import HEADERS, log

US_SYMBOLS = ["TSLA", "AAPL", "NVDA", "MSFT", "AMZN", "SPY"]
CRYPTO_IDS = {"BTC": "bitcoin", "ETH": "ethereum"}
STOCKS_TTL = 90

_stocks_cache: list[dict] = []
_stocks_ts: float = 0
_stocks_last_good: list[dict] = []


def safe_float(value: str) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed if parsed > 0 else None
    except (ValueError, TypeError):
        return None


def any_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


async def fetch_stooq(client: httpx.AsyncClient, symbol: str) -> Optional[dict]:
    try:
        response = await client.get(
            f"https://stooq.com/q/l/?s={symbol.lower()}.us&f=sd2t2ohlcv&h&e=csv",
            headers=HEADERS,
            timeout=10.0,
        )
        response.raise_for_status()
        row = next(csv.DictReader(io.StringIO(response.text)), None)
        if not row:
            log(f"[market] {symbol}: empty CSV")
            return None
        close = safe_float(row.get("Close", ""))
        open_price = safe_float(row.get("Open", ""))
        if close is None:
            log(f"[market] {symbol}: N/A close")
            return None
        if open_price is None:
            open_price = close
        change = close - open_price
        pct = (change / open_price * 100) if open_price else 0.0
        date = row.get("Date") or row.get("date") or ""
        result = {"symbol": symbol, "price": round(close, 2), "change": round(change, 2), "pct": round(pct, 2), "date": date}
        log(f"[market] {symbol}: ${close:.2f} {pct:+.2f}% [{date}]")
        return result
    except Exception as exc:
        log(f"[market] {symbol}: error - {type(exc).__name__}: {exc}")
        return None


async def fetch_alpha_vantage(client: httpx.AsyncClient, symbol: str) -> Optional[dict]:
    token = settings.alpha_vantage.strip()
    if not token:
        return None
    try:
        response = await client.get(
            "https://www.alphavantage.co/query",
            params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": token},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=12.0,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("Note") or data.get("Information"):
            log(f"[market] Alpha Vantage {symbol}: rate/info response")
            return None
        quote = data.get("Global Quote") or {}
        price = safe_float(quote.get("05. price", ""))
        if price is None:
            log(f"[market] Alpha Vantage {symbol}: empty quote")
            return None
        change = any_float(quote.get("09. change", ""))
        pct = any_float(str(quote.get("10. change percent", "")).replace("%", ""))
        result = {
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change or 0.0, 2),
            "pct": round(pct or 0.0, 2),
            "source": "Alpha Vantage",
        }
        log(f"[market] Alpha Vantage {symbol}: ${price:.2f} {result['pct']:+.2f}%")
        return result
    except Exception as exc:
        log(f"[market] Alpha Vantage {symbol}: error - {type(exc).__name__}: {exc}")
        return None


async def fetch_crypto(client: httpx.AsyncClient) -> list[dict]:
    ids = ",".join(CRYPTO_IDS.values())
    try:
        response = await client.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        output = []
        for ticker, coin_id in CRYPTO_IDS.items():
            if coin_id in data:
                price = float(data[coin_id].get("usd", 0))
                pct = float(data[coin_id].get("usd_24h_change", 0))
                output.append({"symbol": ticker, "price": round(price, 2), "change": 0.0, "pct": round(pct, 2)})
        return output
    except Exception as exc:
        log(f"[market] crypto error - {type(exc).__name__}: {exc}")
        return []


async def refresh_stocks() -> list[dict]:
    global _stocks_cache, _stocks_ts, _stocks_last_good
    async with httpx.AsyncClient() as client:
        alpha_stocks = []
        if settings.alpha_vantage.strip():
            result = await fetch_alpha_vantage(client, US_SYMBOLS[0])
            if result:
                alpha_stocks.append(result)

        stock_results, crypto_results = await asyncio.gather(
            asyncio.gather(
                *[fetch_stooq(client, symbol) for symbol in US_SYMBOLS if symbol not in {stock["symbol"] for stock in alpha_stocks}],
                return_exceptions=True,
            ),
            fetch_crypto(client),
            return_exceptions=True,
        )

    stocks = alpha_stocks + [item for item in (stock_results or []) if isinstance(item, dict)]
    crypto = crypto_results if isinstance(crypto_results, list) else []

    if not stocks and _stocks_last_good:
        stocks = [{**stock, "stale": True} for stock in _stocks_last_good if stock.get("symbol") not in CRYPTO_IDS]
    elif stocks:
        by_symbol = {stock["symbol"]: stock for stock in _stocks_last_good}
        for stock in stocks:
            by_symbol[stock["symbol"]] = stock
        _stocks_last_good = list(by_symbol.values())

    if crypto:
        by_symbol = {stock["symbol"]: stock for stock in _stocks_last_good}
        for stock in crypto:
            by_symbol[stock["symbol"]] = stock
        _stocks_last_good = list(by_symbol.values())
    elif _stocks_last_good:
        crypto = [stock for stock in _stocks_last_good if stock.get("symbol") in CRYPTO_IDS]

    _stocks_cache = stocks + crypto
    _stocks_ts = time.time()
    return _stocks_cache


async def get_stocks() -> list[dict]:
    if time.time() - _stocks_ts > STOCKS_TTL or not _stocks_cache:
        await refresh_stocks()
    return _stocks_cache


def get_cached_stocks() -> list[dict]:
    return _stocks_cache


async def fetch_stooq_history(client: httpx.AsyncClient, symbol: str) -> Optional[dict]:
    try:
        response = await client.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": "3mo", "interval": "1d"},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=12.0,
        )
        response.raise_for_status()
        result = ((response.json().get("chart") or {}).get("result") or [None])[0]
        if not result:
            return None
        timestamps = result.get("timestamp") or []
        quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
        points = []
        for timestamp, close in zip(timestamps, quote.get("close") or []):
            if close is None:
                continue
            price = safe_float(str(close))
            if price is not None:
                points.append({"date": time.strftime("%Y-%m-%d", time.gmtime(timestamp)), "price": round(price, 2)})
        if not points:
            return None
        prices = [point["price"] for point in points]
        return {"symbol": symbol, "source": "Yahoo Finance", "points": points, "high": max(prices), "low": min(prices), "open": prices[0], "close": prices[-1]}
    except Exception as exc:
        log(f"[market] history {symbol}: Yahoo failed - {type(exc).__name__}: {exc}")
        return None


async def fetch_crypto_history(client: httpx.AsyncClient, symbol: str) -> Optional[dict]:
    coin_id = CRYPTO_IDS.get(symbol)
    if not coin_id:
        return None
    try:
        response = await client.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": 30, "interval": "daily"},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=12.0,
        )
        response.raise_for_status()
        points = [
            {"date": time.strftime("%Y-%m-%d", time.gmtime(timestamp / 1000)), "price": round(float(price), 2)}
            for timestamp, price in response.json().get("prices", [])[-30:]
        ]
        if not points:
            return None
        prices = [point["price"] for point in points]
        return {"symbol": symbol, "source": "CoinGecko", "points": points, "high": max(prices), "low": min(prices), "open": prices[0], "close": prices[-1]}
    except Exception as exc:
        log(f"[market] history {symbol}: CoinGecko failed - {type(exc).__name__}: {exc}")
        return None


async def get_stock_history(symbol: str) -> Optional[dict]:
    symbol = symbol.upper().strip()
    if symbol not in US_SYMBOLS and symbol not in CRYPTO_IDS:
        return None
    async with httpx.AsyncClient() as client:
        if symbol in CRYPTO_IDS:
            return await fetch_crypto_history(client, symbol)
        return await fetch_stooq_history(client, symbol)

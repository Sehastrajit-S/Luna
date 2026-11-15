import time
from typing import Optional
from urllib.parse import quote

import httpx

from backend.config import settings
from backend.services.dashboard.common import log

WEATHER_TTL = 600
WMO_DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Showers", 81: "Rain showers", 82: "Heavy showers",
    95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Thunderstorm + heavy hail",
}

_weather_cache: Optional[dict] = None
_weather_ts: float = 0


async def fetch_open_meteo(client: httpx.AsyncClient) -> Optional[dict]:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={settings.weather_lat}&longitude={settings.weather_lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone={quote(settings.weather_timezone)}"
    )
    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        current = response.json()["current"]
        code = int(current.get("weather_code", 0))
        description = WMO_DESCRIPTIONS.get(code, "Unknown")
        result = {
            "temp_f": round(current["temperature_2m"]),
            "feels_f": round(current["apparent_temperature"]),
            "humidity": round(current["relative_humidity_2m"]),
            "wind_mph": round(current["wind_speed_10m"]),
            "condition": description,
            "city": settings.weather_city,
            "source": "Open-Meteo",
        }
        log(f"[weather] open-meteo: {result['temp_f']}F {description}")
        return result
    except Exception as exc:
        log(f"[weather] open-meteo failed - {exc}")
        return None


async def fetch_wttr(client: httpx.AsyncClient) -> Optional[dict]:
    try:
        response = await client.get(
            f"https://wttr.in/{quote(settings.weather_city)}?format=j1",
            headers={"User-Agent": "curl/7.68.0"},
            timeout=10.0,
        )
        response.raise_for_status()
        current = response.json()["current_condition"][0]
        description = (current.get("weatherDesc") or [{}])[0].get("value", "")
        result = {
            "temp_f": int(current.get("temp_F", 0)),
            "feels_f": int(current.get("FeelsLikeF", 0)),
            "humidity": int(current.get("humidity", 0)),
            "wind_mph": int(current.get("windspeedMiles", 0)),
            "condition": description,
            "city": settings.weather_city,
            "source": "wttr.in",
        }
        log(f"[weather] wttr.in: {result['temp_f']}F {description}")
        return result
    except Exception as exc:
        log(f"[weather] wttr.in failed - {exc}")
        return None


async def get_weather() -> Optional[dict]:
    global _weather_cache, _weather_ts
    if _weather_cache and (time.time() - _weather_ts) < WEATHER_TTL:
        return _weather_cache
    async with httpx.AsyncClient() as client:
        result = await fetch_open_meteo(client)
        if result is None:
            result = await fetch_wttr(client)
    if result:
        _weather_cache = result
        _weather_ts = time.time()
    return _weather_cache


def get_cached_weather() -> Optional[dict]:
    return _weather_cache

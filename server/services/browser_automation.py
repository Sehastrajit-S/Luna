"""Optional Playwright browser automation.

The service degrades gracefully if Playwright is not installed.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Any

import httpx


async def browser_read(url: str, max_chars: int = 6000) -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        raise ValueError("Only http and https URLs are supported")
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            res = await client.get(url, headers={"User-Agent": "Luna/1.0"})
            res.raise_for_status()
            text = re.sub(r"<(script|style).*?</\1>", " ", res.text, flags=re.I | re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return {"url": str(res.url), "status": res.status_code, "text": text[:max_chars]}
    except Exception as exc:
        return {"url": url, "status": 0, "error": str(exc)}


def browser_open(url: str) -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        raise ValueError("Only http and https URLs are supported")
    if os.name == "nt":
        os.startfile(url)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", url])
    return {"url": url, "opened": True}


async def playwright_status() -> dict[str, Any]:
    try:
        import playwright.async_api  # noqa: F401
        return {"available": True}
    except Exception as exc:
        return {
            "available": False,
            "reason": str(exc),
            "install": "pip install playwright && python -m playwright install chromium",
        }

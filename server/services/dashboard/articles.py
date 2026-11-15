import re

import httpx

from backend.services.dashboard.common import HEADERS, log


async def fetch_article(url: str) -> dict:
    """Fetch a news article URL and return cleaned text + title for in-app reading."""
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.get(url, headers={**HEADERS, "Accept": "text/html,*/*"})
            response.raise_for_status()
        html = response.text

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""

        image_match = (
            re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
            or re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        )
        image = image_match.group(1).strip() if image_match else ""
        if image and not image.startswith("http"):
            image = ""

        for tag in ("script", "style", "nav", "header", "footer", "aside", "figure", "form", "iframe", "noscript", "advertisement"):
            html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)

        lines = []
        for paragraph in re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE):
            text = re.sub(r"<[^>]+>", " ", paragraph)
            for entity, char in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")]:
                text = text.replace(entity, char)
            text = re.sub(r"&#\d+;", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 60:
                lines.append(text)

        body = "\n\n".join(lines[:20]) or "Article content could not be extracted."
        return {"title": title[:200], "body": body[:6000], "image": image, "url": url}
    except Exception as exc:
        log(f"[article] fetch failed: {exc}")
        return {"title": "", "body": f"Could not load article: {exc}", "url": url}

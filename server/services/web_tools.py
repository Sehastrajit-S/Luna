"""Web search (DuckDuckGo via ddgs) and page fetch for Luna tool calls."""
import html
import base64
import json
import re
from datetime import datetime, timezone

import httpx

from server.services.workspace import write_workspace_file, write_workspace_file_base64

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
_TIMEOUT = 12.0


def _strip_html(html_text: str) -> str:
    for tag in ("script", "style", "nav", "header", "footer", "aside"):
        html_text = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    html_text = re.sub(r"<[^>]+>", " ", html_text)
    html_text = html.unescape(html_text)
    html_text = re.sub(r"&#\d+;", "", html_text)
    html_text = re.sub(r"\s{3,}", "\n\n", html_text)
    return html_text.strip()


async def web_search(query: str, max_results: int = 6) -> str:
    """Search DuckDuckGo via the ddgs library and return snippets with numbered sources."""
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        if not results:
            print(f"[web] search '{query}': 0 results")
            return "No results found."
        lines = []
        refs = []
        for idx, r in enumerate(results[:max_results], start=1):
            title = r.get("title", "")
            snippet = r.get("body", "")
            url = r.get("href", "")
            if title:
                lines.append(f"[{idx}] {title}\nSnippet: {snippet}\nURL: {url}")
                refs.append(f"[{idx}] {title} - {url}")
        print(f"[web] search '{query}': {len(lines)} results")
        if not lines:
            return "No results found."
        return "\n\n".join(lines) + "\n\nReferences:\n" + "\n".join(refs)
    except Exception as e:
        print(f"[web] search failed: {e}")
        return f"Search failed: {e}"


_RESULT_RE = re.compile(r"^\[\d+\] (.+?)\nSnippet: (.*?)\nURL: (\S*)", re.MULTILINE | re.DOTALL)


async def multi_web_search(queries: list[str], max_results_each: int = 4, check_links: bool = True) -> str:
    """Run one or more searches, drop results whose pages are gone, and merge
    them with one continuous numbering grouped by query. Domain-free: skills
    add site-specific checks through the skill runtime."""
    from server.services.skill_runtime import sources

    per_query = max_results_each if len(queries) > 1 else 6
    collected: list = []
    seen: set[str] = set()
    for query in queries:
        raw = await web_search(query, max_results=per_query)
        for title, snippet, url in _RESULT_RE.findall(raw):
            url = url.strip()
            if url and url not in seen:
                seen.add(url)
                collected.append(sources.Result(query, title.strip(), " ".join(snippet.split()), url))
    if not collected:
        return "No results found."
    removed = 0
    if check_links:
        collected, removed = await sources.drop_dead(collected)
    return sources.format_results(collected, queries, removed)


def _extract_reference_urls(search_result: str, limit: int = 3) -> list[str]:
    urls = []
    for match in re.finditer(r"^URL:\s*(https?://\S+)", search_result, re.MULTILINE):
        url = match.group(1).strip()
        if url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


async def web_research(query: str, max_results: int = 6, fetch_results: int = 3, max_chars_per_source: int = 1800) -> str:
    """Search the web, fetch top readable pages, and return cited research context."""
    search_result = await web_search(query, max_results=max_results)
    urls = _extract_reference_urls(search_result, limit=fetch_results)
    if not urls:
        return search_result

    sections = [f"Research query: {query}", "", "Search results:", search_result, "", "Fetched source notes:"]
    for idx, url in enumerate(urls, start=1):
        fetched = await web_fetch(url, max_chars=max_chars_per_source)
        sections.append(f"\nSource [{idx}] {url}\n{fetched[:max_chars_per_source]}")
    return "\n".join(sections)


async def dataset_search(query: str, max_results_per_source: int = 3) -> str:
    """Search common dataset portals and primary data publishers with citations."""
    sources = [
        ("Kaggle", f"site:kaggle.com/datasets {query} dataset"),
        ("UCI ML Repository", f"site:archive.ics.uci.edu {query} dataset"),
        ("Hugging Face Datasets", f"site:huggingface.co/datasets {query} dataset"),
        ("data.gov", f"site:data.gov {query} dataset csv"),
        ("NOAA/NCEI", f"site:ncei.noaa.gov OR site:noaa.gov {query} dataset csv"),
        ("World Bank Data", f"site:data.worldbank.org {query} dataset csv"),
        ("Google Dataset Search indexed pages", f"{query} dataset csv download"),
    ]
    sections = [f"Dataset search query: {query}", ""]
    for label, source_query in sources:
        result = await web_search(source_query, max_results=max_results_per_source)
        sections.append(f"## {label}\n{result}")
    return "\n\n".join(sections)


async def web_fetch(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and extract readable text content."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": _UA})
            r.raise_for_status()
        text = _strip_html(r.text)
        text = text[:max_chars] if len(text) > max_chars else text
        print(f"[web] fetch '{url}': {len(text)} chars")
        return f"Source: {url}\n\n{text}"
    except Exception as e:
        print(f"[web] fetch failed: {e}")
        return f"Fetch failed: {e}"


async def web_download_file(url: str, path: str, max_bytes: int = 250_000_000) -> dict:
    """Download any HTTP(S) file into Luna's workspace and write source metadata."""
    if not url or not url.lower().startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")
    if not path:
        raise ValueError("path is required")

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": _UA})
        response.raise_for_status()
    data = response.content
    if len(data) > max_bytes:
        raise ValueError(f"download is too large ({len(data)} bytes > {max_bytes} bytes)")

    written = write_workspace_file_base64(path, base64.b64encode(data).decode("ascii"))
    metadata = {
        "source_url": str(response.url),
        "requested_url": url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "content_type": response.headers.get("content-type", ""),
        "size": len(data),
        "path": written["path"],
    }
    write_workspace_file(f"{written['path']}.source.json", json.dumps(metadata, indent=2, ensure_ascii=True))
    print(f"[web] downloaded '{url}' -> {written['path']} ({len(data)} bytes)")
    return metadata

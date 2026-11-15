"""Luna MCP server — web tools.

Exposes: web_search, web_fetch, web_research, dataset_search

Run:
    python -m backend.mcp.server_web

Claude Desktop config:
    "luna-web": {
        "command": "python",
        "args": ["-m", "backend.mcp.server_web"],
        "cwd": "/path/to/Luna"
    }
"""
from mcp.server.fastmcp import FastMCP
from backend.services.web_tools import (
    web_search as _web_search,
    web_fetch as _web_fetch,
    web_research as _web_research,
    dataset_search as _dataset_search,
)

mcp = FastMCP("luna-web")


@mcp.tool()
async def web_search(query: str) -> str:
    """Search the web via DuckDuckGo and return numbered results with snippets."""
    return await _web_search(query)


@mcp.tool()
async def web_fetch(url: str) -> str:
    """Fetch a URL and return its readable text content."""
    return await _web_fetch(url)


@mcp.tool()
async def web_research(query: str) -> str:
    """Search the web, fetch top readable sources, and return cited research context."""
    return await _web_research(query)


@mcp.tool()
async def dataset_search(query: str) -> str:
    """Search dataset portals (Kaggle, UCI, Hugging Face, data.gov, NOAA, World Bank) and return citations."""
    return await _dataset_search(query)


if __name__ == "__main__":
    mcp.run()

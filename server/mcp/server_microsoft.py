"""Luna MCP server — Microsoft 365.

Exposes tools for Outlook, Calendar, OneDrive, To Do.

Requires: microsoft_workspace_access_token in .env

Run:
    python -m backend.mcp.server_microsoft
"""
import json
from mcp.server.fastmcp import FastMCP
from backend.services.workspace_integrations import microsoft_workspace

mcp = FastMCP("luna-microsoft")


def _fmt(result) -> str:
    if hasattr(result, "as_dict"):
        return json.dumps(result.as_dict(), indent=2, default=str)
    return json.dumps(result, indent=2, default=str)


# ── Outlook Mail ───────────────────────────────────────────────────────────────

@mcp.tool()
async def outlook_search(query: str, max_results: int = 10) -> str:
    """Search Outlook messages via Microsoft Graph.

    Args:
        query: Search query string
        max_results: Maximum number of messages to return
    """
    return _fmt(await microsoft_workspace("mail", "search_messages", {"query": query, "limit": max_results}))


@mcp.tool()
async def outlook_send(to: str, subject: str, body: str) -> str:
    """Send an email via Outlook.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
    """
    return _fmt(await microsoft_workspace("mail", "send_message", {
        "to": [to], "subject": subject, "body": body,
    }))


@mcp.tool()
async def outlook_read(message_id: str) -> str:
    """Read an Outlook message by its Graph API message ID."""
    return _fmt(await microsoft_workspace("mail", "raw_request", {
        "method": "GET", "path": f"/me/messages/{message_id}",
    }))


# ── Microsoft Calendar ─────────────────────────────────────────────────────────

@mcp.tool()
async def ms_calendar_list(max_results: int = 10) -> str:
    """List upcoming Microsoft Calendar events."""
    return _fmt(await microsoft_workspace("calendar", "list_events", {"limit": max_results}))


@mcp.tool()
async def ms_calendar_create(title: str, start: str, end: str, description: str = "") -> str:
    """Create a Microsoft Calendar event.

    Args:
        title: Event subject
        start: ISO 8601 start datetime
        end: ISO 8601 end datetime
        description: Optional event description
    """
    return _fmt(await microsoft_workspace("calendar", "create_event", {
        "title": title, "start": start, "end": end, "description": description,
    }))


# ── OneDrive ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def onedrive_list(item_id: str = "root") -> str:
    """List files and folders in OneDrive.

    Args:
        item_id: OneDrive item ID or 'root' for the root folder
    """
    return _fmt(await microsoft_workspace("drive", "list_children", {"item_id": item_id}))


@mcp.tool()
async def onedrive_search(query: str) -> str:
    """Search for files in OneDrive.

    Args:
        query: Search query string
    """
    return _fmt(await microsoft_workspace("drive", "search_files", {"query": query}))


# ── To Do ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def todo_list_lists() -> str:
    """List all Microsoft To Do task lists (returns list IDs needed for todo_create)."""
    return _fmt(await microsoft_workspace("todo", "list_tasks", {}))


@mcp.tool()
async def todo_create(list_id: str, title: str, notes: str = "", due: str = "") -> str:
    """Create a Microsoft To Do task in a specific list.

    Args:
        list_id: Task list ID (get from todo_list_lists)
        title: Task title
        notes: Optional task body/notes
        due: Optional due date (ISO 8601 datetime)
    """
    args: dict = {"list_id": list_id, "title": title}
    if notes:
        args["body"] = notes
    if due:
        args["due"] = due
    return _fmt(await microsoft_workspace("todo", "create_task", args))


if __name__ == "__main__":
    mcp.run()

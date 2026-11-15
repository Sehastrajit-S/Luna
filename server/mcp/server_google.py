"""Luna MCP server — Google Workspace.

Exposes tools for Gmail, Calendar, Drive, Tasks.

Requires: google_workspace_access_token in .env

Run:
    python -m backend.mcp.server_google
"""
import json
from mcp.server.fastmcp import FastMCP
from backend.services.workspace_integrations import google_workspace

mcp = FastMCP("luna-google")


def _fmt(result) -> str:
    if hasattr(result, "as_dict"):
        return json.dumps(result.as_dict(), indent=2, default=str)
    return json.dumps(result, indent=2, default=str)


# ── Gmail ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def gmail_search(query: str, max_results: int = 10) -> str:
    """Search Gmail messages.

    Args:
        query: Gmail search query (e.g. 'from:alice subject:invoice')
        max_results: Maximum number of messages to return
    """
    return _fmt(await google_workspace("gmail", "search_messages", {"query": query, "limit": max_results}))


@mcp.tool()
async def gmail_send(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Plain-text email body
    """
    return _fmt(await google_workspace("gmail", "send_message", {"to": to, "subject": subject, "body": body}))


@mcp.tool()
async def gmail_read(message_id: str) -> str:
    """Read the full content of a Gmail message by its ID."""
    return _fmt(await google_workspace("gmail", "get_message", {"message_id": message_id}))


# ── Google Calendar ────────────────────────────────────────────────────────────

@mcp.tool()
async def calendar_list_events(max_results: int = 10, time_min: str = "") -> str:
    """List upcoming Google Calendar events.

    Args:
        max_results: Number of events to return
        time_min: ISO 8601 start time filter (defaults to now)
    """
    args: dict = {"limit": max_results}
    if time_min:
        args["time_min"] = time_min
    return _fmt(await google_workspace("calendar", "list_events", args))


@mcp.tool()
async def calendar_create_event(title: str, start: str, end: str, description: str = "") -> str:
    """Create a Google Calendar event.

    Args:
        title: Event title
        start: ISO 8601 start datetime e.g. '2026-06-01T10:00:00'
        end: ISO 8601 end datetime
        description: Optional event description
    """
    return _fmt(await google_workspace("calendar", "create_event", {
        "title": title, "start": start, "end": end, "description": description,
    }))


# ── Google Drive ───────────────────────────────────────────────────────────────

@mcp.tool()
async def drive_search(query: str, max_results: int = 10) -> str:
    """Search Google Drive for files.

    Args:
        query: Drive search query (e.g. 'name contains "report"')
        max_results: Maximum number of results
    """
    return _fmt(await google_workspace("drive", "search_files", {"query": query, "limit": max_results}))


@mcp.tool()
async def drive_get_file(file_id: str) -> str:
    """Get metadata for a Google Drive file (id, name, mimeType, webViewLink).

    Args:
        file_id: Google Drive file ID
    """
    return _fmt(await google_workspace("drive", "get_file", {"file_id": file_id}))


# ── Google Tasks ───────────────────────────────────────────────────────────────

@mcp.tool()
async def tasks_list() -> str:
    """List tasks in the default Google Tasks list."""
    return _fmt(await google_workspace("tasks", "list_tasks", {}))


@mcp.tool()
async def tasks_create(title: str, notes: str = "", due: str = "") -> str:
    """Create a Google Tasks task.

    Args:
        title: Task title
        notes: Optional task notes
        due: Optional due date in RFC 3339 format
    """
    args: dict = {"title": title}
    if notes:
        args["notes"] = notes
    if due:
        args["due"] = due
    return _fmt(await google_workspace("tasks", "create_task", args))


if __name__ == "__main__":
    mcp.run()

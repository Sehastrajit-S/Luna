"""
dispatch stage — Fast-path regex-based command detection.

If a direct command is detected (Spotify, app launch, face tracking, Gmail, research,
dataset), it is executed immediately and ctx.dispatched is set to True, skipping
the LLM generation stage.
"""
import json
import logging
import re

from backend.config import settings
from backend.services.command_parser import (
    parse_user_launch_request,
    parse_user_spotify_request,
    extract_direct_research_query,
    extract_direct_dataset_query,
)
from backend.services.tool_runner import execute_tool_call, verify_tool_result
from backend.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)

_FACE_ON_RE = re.compile(
    r'face\s*(mode|tracking|detection|cam(?:era)?)?\s*(on|enable|start|activate|open)\b',
    re.IGNORECASE,
)
_FACE_OFF_RE = re.compile(
    r'face\s*(mode|tracking|detection|cam(?:era)?)?\s*(off|disable|stop|deactivate|close)\b',
    re.IGNORECASE,
)
_GMAIL_INTENT_RE = re.compile(
    r"\bany\s+mail\b"
    r"|\b(check|show|get|list|read|do i have|what('s| are| is))\b.{0,40}\b(email[s]?|mail[s]?|inbox|gmail)\b"
    r"|\b(email[s]?|mail[s]?|inbox|gmail)\b.{0,20}\b(today|unread|new|recent|latest)\b",
    re.IGNORECASE,
)
_GITHUB_INTENT_RE = re.compile(
    r"\b(github|repo|repository|pr|prs|pull request|pull requests|issue|issues|commit|commits|branch|changed files|updated|changed)\b",
    re.IGNORECASE,
)
_OWNER_REPO_RE = re.compile(r"\b([\w.-]+/[\w.-]+)\b")
_PR_NUMBER_RE = re.compile(r"(?:\bpr\b|\bpull request\b|#)\s*#?(\d+)", re.IGNORECASE)


async def dispatch_direct_commands(ctx: ChatContext) -> None:
    """
    Detect and handle direct commands that bypass LLM generation.
    Sets ctx.dispatched = True if handled.
    """
    msg = ctx.user_message

    # ── Spotify ───────────────────────────────────────────────────────────────
    if not ctx.is_business:
        from backend.services.spotify import spotify_service
        spotify_track = None if ctx.cli else spotify_service.get_current()
        direct_spotify_cmd = parse_user_spotify_request(msg, spotify_track)

        if direct_spotify_cmd:
            ctx.dispatched = True
            ctx.direct_command_type = "spotify"
            ctx.full_response = await _handle_spotify(direct_spotify_cmd, ctx)
            ctx.full_response_parts = [ctx.full_response]
            return

    # ── App Launch ────────────────────────────────────────────────────────────
    if not ctx.is_business:
        direct_launch_app = parse_user_launch_request(msg)
        if direct_launch_app:
            ctx.dispatched = True
            ctx.direct_command_type = "launch"
            from backend.services.app_launcher import launch_app
            success, launch_message = launch_app(direct_launch_app)
            ctx.full_response = f"Opening {direct_launch_app}." if success else launch_message
            ctx.tool_succeeded = success
            ctx.full_response_parts = [ctx.full_response]
            return

    # ── Face tracking ─────────────────────────────────────────────────────────
    if bool(_FACE_ON_RE.search(msg)):
        ctx.dispatched = True
        ctx.direct_command_type = "face"
        ctx.full_response = "[FACE:on] Face tracking activated."
        ctx.full_response_parts = [ctx.full_response]
        return

    if bool(_FACE_OFF_RE.search(msg)) and not bool(_FACE_ON_RE.search(msg)):
        ctx.dispatched = True
        ctx.direct_command_type = "face"
        ctx.full_response = "[FACE:off] Face tracking off."
        ctx.full_response_parts = [ctx.full_response]
        return

    # ── Gmail ─────────────────────────────────────────────────────────────────
    if bool(_GMAIL_INTENT_RE.search(msg)):
        ctx.dispatched = True
        ctx.direct_command_type = "gmail"
        ctx.had_tool_call = True
        await _handle_gmail(ctx)
        return

    # ── GitHub ────────────────────────────────────────────────────────────────
    if bool(_GITHUB_INTENT_RE.search(msg)) and _looks_like_github_question(msg):
        ctx.dispatched = True
        ctx.direct_command_type = "github"
        ctx.had_tool_call = True
        await _handle_github(ctx)
        return

    # ── Research ──────────────────────────────────────────────────────────────
    direct_research_query = extract_direct_research_query(msg)
    if direct_research_query and not bool(_GMAIL_INTENT_RE.search(msg)):
        ctx.dispatched = True
        ctx.direct_command_type = "research"
        ctx.had_tool_call = True
        tc = {"tool": "web_research", "args": {"query": direct_research_query}, "speak": ""}
        result = await execute_tool_call(tc, ctx.db, ctx.conv.id)
        ctx.tool_succeeded = "fail" not in result and "error" not in result
        ctx.full_response = await verify_tool_result("web_research", {"query": direct_research_query}, result, msg)
        ctx.full_response_parts = [ctx.full_response]
        return

    # ── Dataset ───────────────────────────────────────────────────────────────
    direct_dataset_query = extract_direct_dataset_query(msg)
    if direct_dataset_query:
        ctx.dispatched = True
        ctx.direct_command_type = "dataset"
        ctx.had_tool_call = True
        tc = {"tool": "dataset_search", "args": {"query": direct_dataset_query}, "speak": ""}
        result = await execute_tool_call(tc, ctx.db, ctx.conv.id)
        ctx.tool_succeeded = "fail" not in result and "error" not in result
        ctx.full_response = await verify_tool_result("dataset_search", {"query": direct_dataset_query}, result, msg)
        ctx.full_response_parts = [ctx.full_response]
        return


async def _handle_spotify(cmd: dict, ctx: ChatContext) -> str:
    """Execute a Spotify command and return the response text."""
    from backend.services.spotify import spotify_service

    action = cmd["action"]
    if action == "play":
        ok = spotify_service.play(cmd.get("query"))
        if ok:
            ctx.tool_succeeded = True
            return "Playing."
        elif spotify_service.needs_auth:
            import webbrowser
            auth_url = spotify_service.get_auth_url()
            if auth_url:
                webbrowser.open(auth_url)
            return "Spotify needs to be connected first. I opened the authorization page in your browser."
        elif not spotify_service._ready:
            return "Spotify isn't configured. Add spotify_client_id and spotify_client_secret to your .env file."
        else:
            return "Spotify is configured, but playback is not available. Open Spotify on a device, then try again."
    elif action == "queue":
        ok = spotify_service.queue(cmd.get("query") or "")
        ctx.tool_succeeded = ok
        return "Queued." if ok else "I couldn't queue that."
    elif action == "pause":
        ok = spotify_service.pause()
        ctx.tool_succeeded = ok
        return "Paused." if ok else "I couldn't pause Spotify."
    elif action == "next":
        ok = spotify_service.next_track()
        ctx.tool_succeeded = ok
        return "Skipping." if ok else "I couldn't skip tracks."
    elif action == "prev":
        ok = spotify_service.prev_track()
        ctx.tool_succeeded = ok
        return "Going back." if ok else "I couldn't go back."
    return "I couldn't handle that Spotify command."


async def _handle_gmail(ctx: ChatContext) -> None:
    """Fetch Gmail and build a widget command."""
    _q = "is:unread" if re.search(r"\bunread\b", ctx.user_message, re.IGNORECASE) else ""
    tc = {
        "tool": "google_workspace",
        "args": {"service": "gmail", "action": "search_messages", "args": {"q": _q, "maxResults": 5}},
        "speak": "",
    }
    result = await execute_tool_call(tc, ctx.db, ctx.conv.id)
    ctx.tool_succeeded = "fail" not in result and "error" not in result

    try:
        _res = json.loads(result)
        _msgs = _res.get("data", {}).get("messages", [])
        if _msgs:
            ctx.gmail_widget_cmd = {
                "type": "widget",
                "kind": "emails",
                "title": "Your Emails",
                "body": json.dumps([{
                    "from": m.get("from", ""),
                    "subject": m.get("subject", "(no subject)"),
                    "date": m.get("date", ""),
                    "snippet": m.get("snippet", ""),
                } for m in _msgs]),
            }
            ctx.full_response = (
                f"Here {'are' if len(_msgs) != 1 else 'is'} "
                f"{len(_msgs)} email{'s' if len(_msgs) != 1 else ''} — opening in the panel."
            )
        else:
            ctx.full_response = "No emails found in your inbox."
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Gmail response parsing failed: %s", e)
        ctx.full_response = "Couldn't fetch your emails right now."
    ctx.full_response_parts = [ctx.full_response]


def _looks_like_github_question(msg: str) -> bool:
    low = msg.lower()
    return (
        "github" in low
        or "repo" in low
        or "repository" in low
        or "pull request" in low
        or re.search(r"\bprs?\b", low) is not None
        or (("issue" in low or "commit" in low or "changed files" in low) and ("my" in low or _OWNER_REPO_RE.search(msg)))
        or (("updated" in low or "changed" in low) and re.search(r"\b(his|her|their|user|author|by)\b", low))
    )


def _extract_repo(msg: str) -> str:
    match = _OWNER_REPO_RE.search(msg)
    return match.group(1) if match else ""


def _extract_pr_author(msg: str) -> str:
    patterns = [
        r"\buser\s+@?([\w.-]+)\b",
        r"\bauthor\s+@?([\w.-]+)\b",
        r"\bby\s+@?([\w.-]+)\b",
        r"\bwhat\s+did\s+@?([\w.-]+)\s+(?:update|change)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, msg, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


async def _handle_github(ctx: ChatContext) -> None:
    msg = ctx.user_message
    low = msg.lower()
    repo = _extract_repo(msg)
    author = _extract_pr_author(msg)
    pr_number_match = _PR_NUMBER_RE.search(msg)

    if author and ("pr" in low or "pull request" in low or "updated" in low or "changed" in low):
        tc = {"tool": "github_summarize_user_pr", "args": {"repo": repo, "user": author, "state": "all"}, "speak": ""}
    elif pr_number_match:
        tc = {"tool": "github_get_pr", "args": {"repo": repo, "number": int(pr_number_match.group(1))}, "speak": ""}
    elif "issue" in low:
        tc = {"tool": "github_list_issues", "args": {"repo": repo}, "speak": ""}
    elif "repo" in low and not ("pr" in low or "pull request" in low):
        tc = {"tool": "github_list_repos", "args": {}, "speak": ""}
    else:
        tc = {"tool": "github_list_prs", "args": {"repo": repo}, "speak": ""}

    result = await execute_tool_call(tc, ctx.db, ctx.conv.id)
    ctx.tool_succeeded = "fail" not in result and "error" not in result
    ctx.full_response = await verify_tool_result(tc["tool"], tc["args"], result, msg)
    ctx.full_response_parts = [ctx.full_response]

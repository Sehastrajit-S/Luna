"""
tools stage — Parse and execute tool calls from the LLM response.

Handles JSON tool_call detection, bracket-format fallbacks, permission checks,
and tool execution.
"""
import asyncio
import json
import logging
import re

from backend.services.tool_runner import (
    execute_tool_call,
    verify_tool_result,
    parse_tool_call_json,
    strip_tool_call_json,
)
from backend.services.permission_manager import permission_manager
from backend.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)


async def process_tools(ctx: ChatContext) -> None:
    """
    Detect tool calls in ctx.full_response, execute them, and update the response.
    Only runs if the dispatch stage didn't handle the request.
    """
    if ctx.dispatched:
        return

    full_response = ctx.full_response

    # ── JSON tool call detection ──────────────────────────────────────────────
    tc = parse_tool_call_json(full_response)

    # ── Bracket-format fallbacks (legacy, to be deprecated) ───────────────────
    if not tc:
        tc = _try_bracket_formats(full_response)

    if tc is None:
        return

    ctx.had_tool_call = True
    tool_name = tc.get("tool", "")
    args = tc.get("args", {})
    speak = tc.get("speak", "")

    # ── Permission check ──────────────────────────────────────────────────────
    decision, msg, confirm_id = permission_manager.check(tool_name, args)

    if decision == "block":
        ctx.full_response = strip_tool_call_json(full_response) or (msg or "I can't do that.")
        return

    if decision == "confirm":
        ctx.emit_sse({
            "type": "confirmation_required",
            "confirm_id": confirm_id,
            "message": msg,
            "tool": tool_name,
            "args": args,
        })
        # Wait for user confirmation (up to 30 seconds)
        approved = await _wait_for_confirmation(confirm_id)
        if not approved:
            ctx.full_response = "Okay, I'll skip that."
            return

    # ── Execute the tool ──────────────────────────────────────────────────────
    result = await execute_tool_call(tc, ctx.db, ctx.conv.id)
    ctx.tool_succeeded = "fail" not in result and "error" not in result

    # ── Process result based on tool type ─────────────────────────────────────
    _info_tools = {
        "web_search", "web_research", "web_fetch", "dataset_search",
        "workspace_read", "workspace_read_base64", "browser_read",
        "github_list_repos", "github_list_issues", "github_list_prs",
        "github_get_pr", "slack_search_messages", "slack_channel_history",
        "jira_search_issues", "jira_get_issue", "get_system_info", "get_volume",
        "get_brightness", "get_clipboard",
    }

    if tool_name in _info_tools:
        verified = await verify_tool_result(tool_name, args, result, ctx.user_message)
        ctx.full_response = verified or strip_tool_call_json(full_response)

    elif tool_name == "google_workspace" and args.get("service") == "gmail":
        _handle_gmail_tool_result(ctx, result, full_response)

    elif speak:
        ctx.full_response = speak
    else:
        ctx.full_response = strip_tool_call_json(full_response) or result[:300]


def _try_bracket_formats(response: str) -> dict | None:
    """
    Try legacy bracket-format tool calls: [WEB_SEARCH:...], [WEB_RESEARCH:...], etc.
    Returns a tool call dict or None.
    """
    patterns = [
        (r'\[WEB_SEARCH:([^\]]+)\]', "web_search", lambda m: {"query": m.group(1).strip()}),
        (r'\[WEB_RESEARCH:([^\]]+)\]', "web_research", lambda m: {"query": m.group(1).strip()}),
        (r'\[WEB_FETCH:([^\]]+)\]', "web_fetch", lambda m: {"url": m.group(1).strip()}),
        (r'\[DATASET_SEARCH:([^\]]+)\]', "dataset_search", lambda m: {"query": m.group(1).strip()}),
        (r'\[WORKSPACE_WRITE:([^|]+)\|([^\]]+)\]', "workspace_write",
         lambda m: {"path": m.group(1).strip(), "content": m.group(2)}),
        (r'\[WORKSPACE_READ:([^\]]+)\]', "workspace_read", lambda m: {"path": m.group(1).strip()}),
        (r'\[GMAIL(?:_CHECK)?\]', "google_workspace",
         lambda m: {"service": "gmail", "action": "search_messages", "args": {"q": "is:unread", "maxResults": 10}}),
    ]

    for pattern, tool, args_fn in patterns:
        match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
        if match:
            return {"tool": tool, "args": args_fn(match), "speak": ""}

    return None


async def _wait_for_confirmation(confirm_id: str, timeout_seconds: float = 30.0) -> bool:
    """Poll for user confirmation. Returns True if approved, False otherwise."""
    iterations = int(timeout_seconds / 0.5)
    for _ in range(iterations):
        await asyncio.sleep(0.5)
        approved = permission_manager.pop_answer(confirm_id)
        if approved is not None:
            return approved
    return False


def _handle_gmail_tool_result(ctx: ChatContext, result: str, full_response: str) -> None:
    """Parse Gmail tool result and build widget command."""
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
            ctx.full_response = "No emails found."
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Gmail tool result parsing failed: %s", e)
        ctx.full_response = strip_tool_call_json(full_response) or result[:300]

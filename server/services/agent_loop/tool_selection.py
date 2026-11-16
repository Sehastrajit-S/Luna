"""Which tool schemas the model sees on a turn.

Sending all ~70 schemas costs ~5k tokens of a 16k window and makes a small
model pick worse. Like Claude Code's deferred tools, a core set is always
loaded, topic groups load when the conversation mentions them, and
`tool_search` loads anything else on demand.
"""
from __future__ import annotations

import re

from server.services.tool_registry import TOOL_REGISTRY

TOOL_SEARCH = "tool_search"

CORE_TOOLS = (
    "web_search", "use_skill", "web_fetch", "browse_url",
    "launch_app", "close_app", "spotify_play", "spotify_pause", "spotify_next", "spotify_queue",
    "search_conversation",
)

# (pattern over the recent conversation, tools it loads)
TOOL_GROUPS: tuple[tuple[re.Pattern, tuple[str, ...]], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), tools) for pattern, tools in (
        # Saving tasks/events only when the conversation is about scheduling —
        # with them always loaded, "add a DELETE endpoint" became a calendar event.
        (r"\b(?:remind(?:er|ers)?|remember|to-?dos?|tasks?|my\s+list|calendar|schedule|meetings?|appointments?"
         r"|deadlines?|due|tonight|tomorrow|today|this\s+(?:morning|afternoon|evening|week)|next\s+week"
         r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday|o'?clock)\b"
         r"|\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b|\bat\s+\d{1,2}(?::\d{2})?\b",
         ("create_task", "create_event")),
        (r"\b(?:volume|mute|unmute|louder|quieter|brightness|dim|brighter|lock|screen|display|monitor|"
         r"clipboard|copy|paste|sleep|battery|ram|memory|cpu|system\s+info|specs?)\b",
         ("get_volume", "set_volume", "mute_audio", "unmute_audio", "get_brightness", "set_brightness",
          "lock_screen", "turn_off_display", "sleep_system", "get_clipboard", "set_clipboard", "get_system_info")),
        (r"\b(?:audio|speakers?|headphones?|headset|realtek|output\s+device|bathroom)\b", ("switch_audio",)),
        (r"\b(?:previous|last)\s+(?:song|track)\b|\bgo\s+back\b", ("spotify_prev",)),
        (r"\bapps?\b|\bapplications?\b|\bprograms?\b", ("list_apps",)),
        (r"\b(?:github|repos?|repository|pull\s+requests?|prs?|issues?|commits?|branch)\b",
         ("github_list_repos", "github_list_issues", "github_list_prs", "github_get_pr",
          "github_summarize_user_pr", "github_create_issue", "github_comment", "github_create_pr")),
        (r"\bslack\b", ("slack_search_messages", "slack_channel_history")),
        (r"\b(?:jira|ticket)\b", ("jira_search_issues", "jira_get_issue")),
        (r"\b(?:bug|bugfix|fix)\b.{0,60}\b(?:jira|pr|pull\s+request|slack|ticket)\b", ("enterprise_bugfix_workflow",)),
        (r"\b(?:gmail|e-?mails?|mails?|inbox|google|drive|docs|sheets|slides|contacts)\b", ("google_workspace",)),
        (r"\b(?:outlook|onedrive|teams|excel|microsoft|office\s*365|m365|to\s*do)\b", ("microsoft_workspace",)),
        (r"\b(?:datasets?|training\s+data|csv\s+data)\b", ("dataset_search",)),
        (r"\b(?:download|save\s+(?:the|this)\s+(?:file|pdf|image))\b", ("web_download_file",)),
        (r"\b(?:skills?|capabilit(?:y|ies))\b", ("list_skills",)),
        (r"\b(?:news|headlines?|what'?s\s+happening|current\s+events|briefing)\b", ("daily_news",)),
        (r"\b(?:remember|memor(?:y|ies)|keep\s+in\s+mind|note\s+that|don'?t\s+forget)\b", ("save_memory",)),
        (r"\b(?:forget|erase|wipe|delete|remove)\b.{0,40}\b(?:know|remember|memor(?:y|ies)|about\s+me|about\s+my)\b"
         r"|^\s*(?:please\s+)?forget\b", ("forget_memory",)),
        # Arithmetic: small models multiply wrong with full confidence.
        (r"\d\s*(?:[-+*/^x×÷]|times|plus|minus|divided\s+by|multiplied\s+by|over)\s*\(?\d"
         r"|\d\s*(?:squared|cubed)\b|\b(?:calculate|compute|square\s+root|sqrt)\b|\d+(?:\.\d+)?\s*(?:%|percent)\s*of\b",
         ("calculate",)),
        # Files only when the user talks about files: "save it", "create notes.md", "read my workspace".
        (r"\b(?:save|store)\s+(?:it|this|that|them)\b|\b(?:files?|workspace|folder)\b"
         r"|\b[\w-]+\.(?:txt|md|csv|json|py|js|ts|html|sql|yaml|yml)\b",
         ("workspace_read", "workspace_write")),
    )
)

# Never offered in chat: deep research is /research only; code_* belong to the coding agent.
EXCLUDED = frozenset({"web_research"}) | {n for n in TOOL_REGISTRY if n.startswith("code_")}


def _recent_text(user_message: str, history: list[dict] | None) -> str:
    """This message plus the last couple of user turns ("yes, do it" follow-ups)."""
    earlier = [m.get("content", "") for m in (history or []) if m.get("role") == "user"][-2:]
    return "\n".join([*earlier, user_message or ""])


def select_tools(user_message: str, history: list[dict] | None = None) -> list[str]:
    text = _recent_text(user_message, history)
    chosen = [t for t in CORE_TOOLS if t in TOOL_REGISTRY]
    for pattern, tools in TOOL_GROUPS:
        if pattern.search(text):
            chosen.extend(t for t in tools if t in TOOL_REGISTRY and t not in chosen)
    return chosen


def deferred_tools(active: list[str]) -> list[str]:
    return [n for n in TOOL_REGISTRY if n not in active and n not in EXCLUDED]


def tool_search_spec(active: list[str]) -> dict | None:
    deferred = deferred_tools(active)
    if not deferred:
        return None
    return {"type": "function", "function": {
        "name": TOOL_SEARCH,
        "description": "Load more tools by keyword so you can call them next. Not loaded yet: " + ", ".join(deferred),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Tool names or keywords, e.g. 'volume' or 'github_create_pr'"},
        }, "required": ["query"]},
    }}


def search_tools(query: str, active: list[str], among: list[str] | None = None) -> list[str]:
    """Deferred tools (or the tools in `among`) matching the query by name or description."""
    words = [w for w in re.findall(r"[a-z0-9_]+", (query or "").lower()) if len(w) > 1]
    found = []
    for name in (among if among is not None else deferred_tools(active)):
        if name not in TOOL_REGISTRY:
            continue
        haystack = f"{name} {TOOL_REGISTRY[name].description}".lower()
        if any(w in haystack for w in words):
            found.append(name)
    return found[:12]

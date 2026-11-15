"""JSON Schemas for Luna's tools.

Each tool's input is a JSON Schema object, the same shape Claude Code, the
Anthropic/OpenAI APIs and Ollama use for native tool calling. The registry
attaches these to its ToolDefs; the agent loop sends them to the model and
validates every call against them before running it.
"""
from __future__ import annotations


def _s(description: str, **extra) -> dict:
    return {"type": "string", "description": description, **extra}


def _i(description: str, **extra) -> dict:
    return {"type": "integer", "description": description, **extra}


def _b(description: str) -> dict:
    return {"type": "boolean", "description": description}


def _obj(properties: dict | None = None, required: tuple[str, ...] = ()) -> dict:
    return {"type": "object", "properties": properties or {}, "required": list(required)}


_LOCAL_DT = "Local date and time, format YYYY-MM-DDTHH:MM (e.g. 2026-09-23T18:00)"
_REPO = "GitHub repo as owner/name. Empty string uses the user's default repo"
_PATH = "Path relative to the workspace root"

TOOL_SCHEMAS: dict[str, dict] = {
    # Apps and media
    "launch_app": _obj({"app": _s("App name, e.g. 'spotify', 'vs code', 'chrome'")}, ("app",)),
    "close_app": _obj({"app": _s("Name of the running app to close")}, ("app",)),
    "list_apps": _obj(),
    "spotify_play": _obj({"query": _s("Song, artist, album or playlist. Empty resumes playback")}),
    "spotify_pause": _obj(),
    "spotify_next": _obj(),
    "spotify_prev": _obj(),
    "spotify_queue": _obj({"query": _s("Song to add to the queue")}, ("query",)),
    "switch_audio": _obj({"device_name": _s("Output device, e.g. 'headphones', 'speaker 1', 'realtek'")}, ("device_name",)),
    # Tasks and calendar
    "create_task": _obj({
        "title": _s("Short task title"),
        "due": _s(f"When it is due. {_LOCAL_DT}. Omit when no time was given"),
        "priority": _s("Priority", enum=["low", "medium", "high"]),
    }, ("title",)),
    "create_event": _obj({
        "title": _s("Short event title"),
        "datetime": _s(f"Start time. {_LOCAL_DT}"),
        "duration": _i("Length in minutes", minimum=1, maximum=1440),
    }, ("title", "datetime")),
    # Web
    "browse_url": _obj({"url": _s("http(s) URL to open in the browser")}, ("url",)),
    "web_search": _obj({"query": _s("Search query")}, ("query",)),
    "use_skill": _obj({
        "skill": _s("Skill id from the Skills section, e.g. 'job-search', 'paper-search', 'product-search'"),
        "request": _s("The user's request in their own words"),
    }, ("skill", "request")),
    "web_research": _obj({"query": _s("Research topic")}, ("query",)),
    "dataset_search": _obj({"query": _s("What data is needed")}, ("query",)),
    "web_fetch": _obj({"url": _s("http(s) URL to read")}, ("url",)),
    "web_download_file": _obj({"url": _s("http(s) URL of the file"), "path": _s(f"Where to save it. {_PATH}")}, ("url", "path")),
    "browser_open": _obj({"url": _s("http(s) URL")}, ("url",)),
    "browser_read": _obj({"url": _s("http(s) URL of a public page")}, ("url",)),
    # Workspace files
    "workspace_read": _obj({"path": _s(_PATH)}, ("path",)),
    "workspace_write": _obj({"path": _s(_PATH), "content": _s("Full file content")}, ("path", "content")),
    "workspace_read_base64": _obj({"path": _s(_PATH)}, ("path",)),
    "workspace_write_base64": _obj({"path": _s(_PATH), "content_base64": _s("File bytes, base64-encoded")}, ("path", "content_base64")),
    "list_skills": _obj(),
    "search_conversation": _obj({
        "query": _s("Keywords to find in this conversation: names, topics, numbers, e.g. 'base62 encoder alphabet'"),
    }, ("query",)),
    "create_agent_task": _obj({"description": _s("What the long-running task should achieve")}, ("description",)),
    # System controls
    "get_volume": _obj(),
    "set_volume": _obj({"level": _i("Volume 0-100", minimum=0, maximum=100)}, ("level",)),
    "mute_audio": _obj(),
    "unmute_audio": _obj(),
    "get_brightness": _obj(),
    "set_brightness": _obj({"level": _i("Brightness 0-100", minimum=0, maximum=100)}, ("level",)),
    "lock_screen": _obj(),
    "turn_off_display": _obj(),
    "sleep_system": _obj(),
    "get_clipboard": _obj(),
    "set_clipboard": _obj({"text": _s("Text to copy")}, ("text",)),
    "get_system_info": _obj(),
    "save_memory": _obj({
        "fact": _s("One standalone sentence about the user with every detail they gave, "
                   "e.g. \"User's dog Quillon is a 3-year-old border collie\""),
        "category": _s("personal, preference, relationship, event, goal or health", enum=[
            "personal", "preference", "relationship", "event", "goal", "health"]),
    }, ("fact",)),
    "forget_memory": _obj({"about": _s("The subject to forget, e.g. \"my dog\" or \"my old job\"")}, ("about",)),
    "daily_news": _obj({
        "topic": _s("Only headlines about this, e.g. \"technology\" or \"India\". Empty for the top stories"),
        "limit": _i("How many headlines, 1-20 (default 8)", minimum=1, maximum=20),
    }),
    "calculate": _obj({"expression": _s("Arithmetic expression, e.g. 17*23 or (1200*0.15)+40")}, ("expression",)),
    # GitHub
    "github_list_repos": _obj(),
    "github_list_issues": _obj({"repo": _s(_REPO)}),
    "github_create_issue": _obj({
        "repo": _s(_REPO), "title": _s("Issue title"), "body": _s("Issue body (Markdown)"),
        "labels": {"type": "array", "items": {"type": "string"}, "description": "Label names"},
    }, ("title",)),
    "github_comment": _obj({"repo": _s(_REPO), "number": _i("Issue or PR number"), "body": _s("Comment (Markdown)")}, ("number", "body")),
    "github_list_prs": _obj({"repo": _s(_REPO)}),
    "github_get_pr": _obj({"repo": _s(_REPO), "number": _i("PR number")}, ("number",)),
    "github_summarize_user_pr": _obj({
        "repo": _s(_REPO), "user": _s("GitHub username"),
        "state": _s("Which PRs to consider", enum=["open", "closed", "all"]),
    }, ("user",)),
    "github_create_pr": _obj({
        "repo": _s(_REPO), "title": _s("PR title"), "head": _s("Branch with the changes (already pushed)"),
        "base": _s("Branch to merge into, usually main"), "body": _s("PR description (Markdown)"),
        "draft": _b("Open as a draft"),
    }, ("title", "head")),
    # Slack and Jira
    "slack_search_messages": _obj({"query": _s("Slack search query"), "count": _i("Max results", minimum=1, maximum=50)}, ("query",)),
    "slack_channel_history": _obj({
        "channel_id": _s("Slack channel id, e.g. C0123456"),
        "oldest": {"type": "number", "description": "Only messages after this Unix timestamp"},
        "limit": _i("Max messages", minimum=1, maximum=200),
    }, ("channel_id",)),
    "jira_search_issues": _obj({"jql": _s("JQL query"), "max_results": _i("Max issues", minimum=1, maximum=50)}, ("jql",)),
    "jira_get_issue": _obj({"issue_key": _s("Issue key, e.g. PROJ-123")}, ("issue_key",)),
    "enterprise_bugfix_workflow": _obj({
        "bug_query": _s("The bug to fix, in the user's words"), "repo": _s(_REPO),
        "jira_key": _s("Related Jira issue key"), "pr_number": _i("Related PR number"),
        "slack_query": _s("Slack search for the discussion"), "slack_channel": _s("Slack channel id"),
        "test_command": _s("Command that runs the tests"),
    }, ("bug_query",)),
    # Google / Microsoft
    "google_workspace": _obj({
        "service": _s("Google service", enum=["gmail", "calendar", "drive", "docs", "sheets", "slides", "tasks", "people"]),
        "action": _s("Action, e.g. search_messages, send_message, list_events, create_event, search_files, get_values, create_document"),
        "args": {"type": "object", "description": "Arguments for the action, e.g. {\"q\": \"is:unread\", \"maxResults\": 5}"},
    }, ("service", "action")),
    "microsoft_workspace": _obj({
        "service": _s("Microsoft 365 service", enum=["mail", "calendar", "drive", "excel", "todo", "teams"]),
        "action": _s("Action, e.g. search_messages, list_events, search_files, get_values, list_tasks"),
        "args": {"type": "object", "description": "Arguments for the action"},
    }, ("service", "action")),
    # Coding workspace
    "code_read_file": _obj({"path": _s(_PATH)}, ("path",)),
    "code_edit_file": _obj({
        "path": _s(_PATH), "old_string": _s("Exact text to replace (must be unique in the file)"),
        "new_string": _s("Replacement text"),
    }, ("path", "old_string", "new_string")),
    "code_write_file": _obj({"path": _s(_PATH), "content": _s("Full file content")}, ("path", "content")),
    "code_list_files": _obj({"path": _s(f"Directory. {_PATH}. Empty for the root")}),
    "code_search": _obj({"pattern": _s("Text or regex to find"), "path": _s(f"Directory to search. {_PATH}")}, ("pattern",)),
    "code_delete_file": _obj({"path": _s(_PATH)}, ("path",)),
    "code_rename_file": _obj({"old_path": _s(_PATH), "new_path": _s(_PATH)}, ("old_path", "new_path")),
    "code_web_search": _obj({"query": _s("Search query")}, ("query",)),
    "code_web_fetch": _obj({"url": _s("http(s) URL")}, ("url",)),
    "code_run_shell": _obj({"command": _s("Shell command to run in the workspace")}, ("command",)),
}

# Tools with no side effects: safe to run concurrently and to repeat.
READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "list_apps", "web_search", "use_skill", "web_research", "dataset_search", "web_fetch", "browser_read",
    "workspace_read", "workspace_read_base64", "list_skills", "search_conversation",
    "get_volume", "get_brightness", "get_clipboard", "get_system_info", "calculate", "daily_news",
    "github_list_repos", "github_list_issues", "github_list_prs", "github_get_pr", "github_summarize_user_pr",
    "slack_search_messages", "slack_channel_history", "jira_search_issues", "jira_get_issue",
    "code_read_file", "code_list_files", "code_search", "code_web_search", "code_web_fetch",
})

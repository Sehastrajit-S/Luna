"""Luna tool registry."""
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    RISKY = "risky"
    DANGEROUS = "dangerous"


@dataclass
class ToolDef:
    name: str
    description: str
    risk: RiskLevel
    params: list[str] = field(default_factory=list)
    confirm_template: str = ""


TOOL_REGISTRY: dict[str, ToolDef] = {
    "launch_app": ToolDef("launch_app", "Open an application on the current desktop platform", RiskLevel.SAFE, ["app"]),
    "list_apps": ToolDef("list_apps", "List apps Luna can launch on this platform", RiskLevel.SAFE),
    "spotify_play": ToolDef("spotify_play", "Play music on Spotify", RiskLevel.SAFE, ["query"]),
    "spotify_pause": ToolDef("spotify_pause", "Pause Spotify playback", RiskLevel.SAFE),
    "spotify_next": ToolDef("spotify_next", "Skip to the next track", RiskLevel.SAFE),
    "spotify_prev": ToolDef("spotify_prev", "Go to the previous track", RiskLevel.SAFE),
    "spotify_queue": ToolDef("spotify_queue", "Add a song to the Spotify queue", RiskLevel.SAFE, ["query"]),
    "switch_audio": ToolDef("switch_audio", "Switch the Windows default audio output device", RiskLevel.SAFE, ["device_name"]),
    "create_task": ToolDef("create_task", "Create a task or reminder", RiskLevel.SAFE, ["title", "due", "priority"]),
    "create_event": ToolDef("create_event", "Create a calendar event", RiskLevel.SAFE, ["title", "datetime", "duration"]),
    "take_screenshot": ToolDef("take_screenshot", "Take a screenshot of the current screen", RiskLevel.SAFE),
    "find_text_on_screen": ToolDef("find_text_on_screen", "Use OCR to find text on the screen", RiskLevel.SAFE, ["query"]),
    "get_active_window": ToolDef("get_active_window", "Get the name of the currently focused window", RiskLevel.SAFE),
    "browse_url": ToolDef("browse_url", "Open a URL in the system browser", RiskLevel.SAFE, ["url"]),
    "click_at": ToolDef("click_at", "Click at screen coordinates", RiskLevel.RISKY, ["x", "y"], "Click at position ({x}, {y})?"),
    "type_text": ToolDef("type_text", "Type text into the focused window", RiskLevel.RISKY, ["text"], 'Type "{text}" into the current window?'),
    "web_search": ToolDef("web_search", "Search the web via DuckDuckGo and return results", RiskLevel.SAFE, ["query"]),
    "web_research": ToolDef("web_research", "Search the web, fetch top readable sources, and return cited research context", RiskLevel.SAFE, ["query"]),
    "dataset_search": ToolDef("dataset_search", "Search dataset portals and primary data publishers such as Kaggle, UCI, Hugging Face, data.gov, NOAA/NCEI, and World Bank", RiskLevel.SAFE, ["query"]),
    "web_fetch": ToolDef("web_fetch", "Fetch a URL and return readable text content", RiskLevel.SAFE, ["url"]),
    "web_download_file": ToolDef("web_download_file", "Download any HTTP(S) file into Luna's workspace with source metadata", RiskLevel.RISKY, ["url", "path"], "Download {url} to workspace file {path}?"),
    "browser_open": ToolDef("browser_open", "Open a URL in the browser through Luna's browser layer", RiskLevel.SAFE, ["url"]),
    "browser_read": ToolDef("browser_read", "Read a public webpage into clean text", RiskLevel.SAFE, ["url"]),
    "workspace_read": ToolDef("workspace_read", "Read a file from Luna's controlled workspace", RiskLevel.SAFE, ["path"]),
    "workspace_write": ToolDef("workspace_write", "Write a file inside Luna's controlled workspace", RiskLevel.RISKY, ["path", "content"], "Write {path} in Luna's workspace?"),
    "workspace_read_base64": ToolDef("workspace_read_base64", "Read any binary file from Luna's controlled workspace as base64", RiskLevel.SAFE, ["path"]),
    "workspace_write_base64": ToolDef("workspace_write_base64", "Write any binary file type inside Luna's controlled workspace from base64", RiskLevel.RISKY, ["path", "content_base64"], "Write binary file {path} in Luna's workspace?"),
    "list_skills": ToolDef("list_skills", "List installed Luna skills", RiskLevel.SAFE),
    "create_agent_task": ToolDef("create_agent_task", "Create a persistent multi-step agent task", RiskLevel.SAFE, ["description"]),
    # ── System controls ──────────────────────────────────────────────────────────
    "get_volume":       ToolDef("get_volume", "Get current system volume level (0–100)", RiskLevel.SAFE),
    "set_volume":       ToolDef("set_volume", "Set system volume to a level 0–100", RiskLevel.SAFE, ["level"]),
    "mute_audio":       ToolDef("mute_audio", "Mute system audio output", RiskLevel.SAFE),
    "unmute_audio":     ToolDef("unmute_audio", "Unmute system audio output", RiskLevel.SAFE),
    "get_brightness":   ToolDef("get_brightness", "Get current display brightness (0–100)", RiskLevel.SAFE),
    "set_brightness":   ToolDef("set_brightness", "Set display brightness to a level 0–100", RiskLevel.SAFE, ["level"]),
    "lock_screen":      ToolDef("lock_screen", "Lock the workstation / screen immediately", RiskLevel.SAFE),
    "turn_off_display": ToolDef("turn_off_display", "Turn off the display without sleeping", RiskLevel.SAFE),
    "sleep_system":     ToolDef("sleep_system", "Put the computer to sleep / suspend", RiskLevel.RISKY, [], "Put the system to sleep?"),
    "get_clipboard":    ToolDef("get_clipboard", "Read current clipboard text content", RiskLevel.SAFE),
    "set_clipboard":    ToolDef("set_clipboard", "Write text to the system clipboard", RiskLevel.SAFE, ["text"]),
    "get_system_info":  ToolDef("get_system_info", "Get OS, RAM, battery and machine info", RiskLevel.SAFE),
    # ── GitHub ──────────────────────────────────────────────────────────────────
    "github_list_repos": ToolDef("github_list_repos", "List your GitHub repositories sorted by last updated", RiskLevel.SAFE),
    "github_list_issues": ToolDef("github_list_issues", "List open issues in a GitHub repository", RiskLevel.SAFE, ["repo"]),
    "github_create_issue": ToolDef("github_create_issue", "Create a new GitHub issue", RiskLevel.RISKY, ["repo", "title", "body"], "Create GitHub issue '{title}' in {repo}?"),
    "github_comment": ToolDef("github_comment", "Post a comment on a GitHub issue or pull request", RiskLevel.RISKY, ["repo", "number", "body"], "Post comment on {repo}#{number}?"),
    "github_list_prs": ToolDef("github_list_prs", "List open pull requests in a GitHub repository", RiskLevel.SAFE, ["repo"]),
    "github_get_pr": ToolDef("github_get_pr", "Get details about a specific pull request", RiskLevel.SAFE, ["repo", "number"]),
    "github_create_pr": ToolDef("github_create_pr", "Open a GitHub pull request from an already-pushed branch", RiskLevel.RISKY, ["repo", "title", "head", "base", "body", "draft"], "Open GitHub PR '{title}' in {repo}?"),
    "slack_search_messages": ToolDef("slack_search_messages", "Search Slack messages using Slack Web API", RiskLevel.SAFE, ["query", "count"]),
    "slack_channel_history": ToolDef("slack_channel_history", "Read recent Slack messages from a channel", RiskLevel.SAFE, ["channel_id", "oldest", "limit"]),
    "jira_search_issues": ToolDef("jira_search_issues", "Search Jira issues with JQL", RiskLevel.SAFE, ["jql", "max_results"]),
    "jira_get_issue": ToolDef("jira_get_issue", "Read a Jira issue by key", RiskLevel.SAFE, ["issue_key"]),
    "enterprise_bugfix_workflow": ToolDef("enterprise_bugfix_workflow", "Gather Jira/GitHub/Slack context, run the coding agent, run tests, and open a draft PR", RiskLevel.RISKY, ["bug_query", "repo", "jira_key", "pr_number", "slack_query", "slack_channel", "test_command"], "Run enterprise bugfix workflow for '{bug_query}'?"),
    # Google Workspace / Microsoft 365
    "google_workspace": ToolDef("google_workspace", "Call Google Workspace services such as Gmail, Calendar, Drive, Docs, Sheets, Slides, Tasks, and People", RiskLevel.RISKY, ["service", "action", "args"], "Run Google Workspace action {service}.{action}?"),
    "microsoft_workspace": ToolDef("microsoft_workspace", "Call Microsoft 365 services through Microsoft Graph such as Outlook, Calendar, OneDrive, Excel, To Do, and Teams", RiskLevel.RISKY, ["service", "action", "args"], "Run Microsoft 365 action {service}.{action}?"),
    # ── Coding agent ─────────────────────────────────────────────────────────────
    "code_read_file":   ToolDef("code_read_file",   "Read a file from the coding workspace",                                RiskLevel.SAFE,      ["path"]),
    "code_edit_file":   ToolDef("code_edit_file",   "Replace an exact string in a coding workspace file (patch semantics)", RiskLevel.RISKY,     ["path", "old_string", "new_string"], "Edit {path} in coding workspace?"),
    "code_write_file":  ToolDef("code_write_file",  "Write or overwrite a file in the coding workspace",                    RiskLevel.RISKY,     ["path", "content"],  "Write workspace file {path}?"),
    "code_list_files":  ToolDef("code_list_files",  "List files in a coding workspace directory",                           RiskLevel.SAFE,      ["path"]),
    "code_search":      ToolDef("code_search",      "Search for a text/regex pattern across coding workspace files",        RiskLevel.SAFE,      ["pattern", "path"]),
    "code_delete_file": ToolDef("code_delete_file", "Permanently delete a file from the coding workspace",                  RiskLevel.RISKY,     ["path"],             "Delete workspace file {path}?"),
    "code_rename_file": ToolDef("code_rename_file", "Move or rename a file within the coding workspace",                    RiskLevel.RISKY,     ["old_path", "new_path"], "Rename {old_path} → {new_path}?"),
    "code_web_search":  ToolDef("code_web_search",  "Search the web for docs, answers, or packages from within the coding agent", RiskLevel.SAFE, ["query"]),
    "code_web_fetch":   ToolDef("code_web_fetch",   "Fetch a URL and return readable text from within the coding agent",   RiskLevel.SAFE,      ["url"]),
    "code_run_shell":   ToolDef("code_run_shell",   "Run a shell command inside the coding workspace (needs approval)",     RiskLevel.DANGEROUS, ["command"],          "Run shell command: {command}?"),
}


def get_tool(name: str) -> ToolDef | None:
    return TOOL_REGISTRY.get(name)


def get_tools_for_prompt() -> str:
    """Return a compact tool list for inclusion in Luna's system prompt."""
    lines = [
        "## Tool calling — MANDATORY rules",
        "",
        "To call a tool, emit this JSON anywhere in your reply (the parser extracts it):",
        '  {"tool_call": {"tool": "<name>", "args": {<key:value>}, "speak": "<one-line confirmation>"}}',
        "",
        "RULES — you MUST call a tool (not just describe it) when:",
        "  - User asks to SEARCH the web, find current info, news, or prices → web_research",
        "  - User asks for a DATASET, data file, or training data → dataset_search",
        "  - User asks to CREATE or SAVE a file in the workspace → workspace_write",
        "  - User asks to READ a file from the workspace → workspace_read",
        "  - User asks to check/read/fetch/search mail, mails, email, emails, inbox, messages, or anything in Gmail → google_workspace",
        "  - User asks about calendar, Drive, Docs, Sheets, Slides, Tasks, or any Google service → google_workspace",
        "  - User asks about Outlook, OneDrive, Teams, Excel, To Do, or any Microsoft service → microsoft_workspace",
        "  - User asks to SWITCH audio device → switch_audio",
        "  - User asks to TAKE a screenshot → take_screenshot",
        "  - User asks to CREATE a task or calendar event → create_task / create_event",
        "",
        "DO NOT describe what you would do — DO IT by emitting the tool_call JSON.",
        "DO NOT say 'Sure, checking your Gmail' without also emitting the tool_call JSON.",
        "",
        "Examples:",
        '  User: "search for latest AI news"',
        '  → {"tool_call": {"tool": "web_research", "args": {"query": "latest AI news 2025"}, "speak": "Searching now."}}',
        "",
        '  User: "save a CSV with employee data"',
        '  → {"tool_call": {"tool": "workspace_write", "args": {"path": "employees.csv", "content": "id,name,role\\n1,Jane,Engineer"}, "speak": "Saved employees.csv."}}',
        "",
        '  User: "check my Gmail" / "check my mails" / "get my emails" / "get me most recent 5 mail"',
        '  → {"tool_call": {"tool": "google_workspace", "args": {"service": "gmail", "action": "search_messages", "args": {"q": "", "maxResults": 5}}, "speak": "Fetching your recent emails."}}',
        "",
        '  User: "find a climate dataset"',
        '  → {"tool_call": {"tool": "dataset_search", "args": {"query": "global climate temperature dataset"}, "speak": "Searching dataset portals."}}',
        "",
        "Available tools:",
    ]
    for name, tool in TOOL_REGISTRY.items():
        params = ", ".join(tool.params) if tool.params else "-"
        lines.append(f"  {name}({params}) — {tool.description}")
    lines.append("")
    lines.append("Bracket tags (for map, Spotify, launches, simple URL): use as instructed in the behavior section.")
    lines.append("Google Workspace service/action pairs: gmail/search_messages, gmail/send_message, calendar/list_events, calendar/create_event, drive/search_files, sheets/get_values, docs/create_document.")
    lines.append("Microsoft Workspace service/action pairs: mail/search_messages, calendar/list_events, drive/search_files, excel/get_values, todo/list_tasks.")
    lines.append("Enterprise workflow: enterprise_bugfix_workflow can gather Jira/GitHub/Slack context, edit code, run tests, and open a draft PR after confirmation.")
    return "\n".join(lines)

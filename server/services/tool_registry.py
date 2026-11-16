"""Luna tool registry.

Every tool has a JSON Schema for its input (tool_schemas.py). The agent loop
sends those schemas to the model for native tool calling and validates each
call against them before it runs.
"""
from dataclasses import dataclass, field
from enum import Enum

from server.services.tool_schemas import READ_ONLY_TOOLS, TOOL_SCHEMAS


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
    input_schema: dict = field(default_factory=dict)
    read_only: bool = False

    def __post_init__(self) -> None:
        if not self.input_schema:
            self.input_schema = TOOL_SCHEMAS.get(self.name) or {"type": "object", "properties": {}, "required": []}
        self.read_only = self.read_only or self.name in READ_ONLY_TOOLS


TOOL_REGISTRY: dict[str, ToolDef] = {
    "launch_app": ToolDef("launch_app", "Open an application on the current desktop platform", RiskLevel.SAFE, ["app"]),
    "close_app": ToolDef("close_app", "Close/quit a running application by name", RiskLevel.RISKY, ["app"], "Close {app}? Any unsaved work in it may be lost."),
    "list_apps": ToolDef("list_apps", "List apps Luna can launch on this platform", RiskLevel.SAFE),
    "spotify_play": ToolDef("spotify_play", "Play music on Spotify", RiskLevel.SAFE, ["query"]),
    "spotify_pause": ToolDef("spotify_pause", "Pause Spotify playback", RiskLevel.SAFE),
    "spotify_next": ToolDef("spotify_next", "Skip to the next track", RiskLevel.SAFE),
    "spotify_prev": ToolDef("spotify_prev", "Go to the previous track", RiskLevel.SAFE),
    "spotify_queue": ToolDef("spotify_queue", "Add a song to the Spotify queue", RiskLevel.SAFE, ["query"]),
    "switch_audio": ToolDef("switch_audio", "Switch the Windows default audio output device", RiskLevel.SAFE, ["device_name"]),
    "create_task": ToolDef("create_task", "Save a to-do or reminder the user asked for (never for steps of your own answer)", RiskLevel.SAFE, ["title", "due", "priority"]),
    "create_event": ToolDef("create_event", "Put a meeting or appointment on the user's calendar when they ask for it", RiskLevel.SAFE, ["title", "datetime", "duration"]),
    "browse_url": ToolDef("browse_url", "Open a URL in the system browser", RiskLevel.SAFE, ["url"]),
    "web_search": ToolDef("web_search", "Search the web via DuckDuckGo and return results", RiskLevel.SAFE, ["query"]),
    "use_skill": ToolDef("use_skill", "Web lookup with a specialised search: job postings, research papers, products to buy, local places, news, or official docs. Only for finding current information online, never for writing, designing or explaining", RiskLevel.SAFE, ["skill", "request"]),
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
    "search_conversation": ToolDef("search_conversation", "Search this whole conversation, including older turns no longer in view: earlier decisions, code you wrote, numbers the user gave", RiskLevel.SAFE, ["query"]),
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
    "save_memory":      ToolDef("save_memory", "Save something the user asks you to remember about them, with every detail they gave", RiskLevel.SAFE, ["fact"]),
    "forget_memory":    ToolDef("forget_memory", "Forget what you remember about a subject when the user asks you to", RiskLevel.SAFE, ["about"]),
    "daily_news":       ToolDef("daily_news", "Today's top news headlines with sources and links, optionally about one topic", RiskLevel.SAFE, ["topic"]),
    "calculate":        ToolDef("calculate", "Work out arithmetic exactly. Use it for any calculation instead of doing math in your head", RiskLevel.SAFE, ["expression"]),
    # ── GitHub ──────────────────────────────────────────────────────────────────
    "github_list_repos": ToolDef("github_list_repos", "List your GitHub repositories sorted by last updated", RiskLevel.SAFE),
    "github_list_issues": ToolDef("github_list_issues", "List open issues in a GitHub repository", RiskLevel.SAFE, ["repo"]),
    "github_create_issue": ToolDef("github_create_issue", "Create a new GitHub issue", RiskLevel.RISKY, ["repo", "title", "body"], "Create GitHub issue '{title}' in {repo}?"),
    "github_comment": ToolDef("github_comment", "Post a comment on a GitHub issue or pull request", RiskLevel.RISKY, ["repo", "number", "body"], "Post comment on {repo}#{number}?"),
    "github_list_prs": ToolDef("github_list_prs", "List open pull requests in a GitHub repository", RiskLevel.SAFE, ["repo"]),
    "github_get_pr": ToolDef("github_get_pr", "Get details about a specific pull request", RiskLevel.SAFE, ["repo", "number"]),
    "github_summarize_user_pr": ToolDef("github_summarize_user_pr", "Find the latest pull request by a GitHub user in a repository and summarize changed files", RiskLevel.SAFE, ["repo", "user", "state"]),
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


def model_tool_spec(name: str) -> dict | None:
    """The tool in the function-calling format Ollama and OpenAI-style APIs take."""
    tool = get_tool(name)
    if tool is None:
        return None
    return {"type": "function", "function": {
        "name": tool.name, "description": tool.description, "parameters": tool.input_schema,
    }}


_TRUE = {"true", "yes", "1"}
_FALSE = {"false", "no", "0"}


def _coerce(value, schema: dict):
    """Small models send "60" for 60 and "true" for true; accept those."""
    kind = schema.get("type")
    if isinstance(value, str):
        text = value.strip()
        if kind == "integer" and text.lstrip("-").isdigit():
            return int(text)
        if kind == "number":
            try:
                return float(text)
            except ValueError:
                return value
        if kind == "boolean" and text.lower() in _TRUE | _FALSE:
            return text.lower() in _TRUE
        if kind == "object" and text.startswith("{"):
            import json
            try:
                return json.loads(text)
            except ValueError:
                return value
    if kind == "integer" and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def validate_tool_args(name: str, args) -> tuple[dict, str | None]:
    """Check a call against the tool's schema. Returns (clean_args, error_or_None).

    Unknown keys are dropped and empty optional values removed rather than
    rejected; wrong types and missing required fields are errors the model sees.
    """
    import jsonschema

    tool = get_tool(name)
    if tool is None:
        return {}, f"unknown tool '{name}'"
    if not isinstance(args, dict):
        return {}, "arguments must be a JSON object"
    props = tool.input_schema.get("properties", {})
    required = set(tool.input_schema.get("required", []))
    clean = {}
    for key, value in args.items():
        if key not in props:
            continue
        if key not in required and (value is None or value == ""):
            continue
        clean[key] = _coerce(value, props[key])
    try:
        jsonschema.validate(clean, tool.input_schema)
    except jsonschema.ValidationError as e:
        where = ".".join(str(p) for p in e.absolute_path)
        return clean, f"invalid arguments{f' for {where}' if where else ''}: {e.message}"
    return clean, None


def get_tool_rules_for_prompt() -> str:
    """How to use tools when the model calls them natively (schemas travel separately)."""
    return "\n".join([
        "## Tools",
        "You have tools (native function calling) for things you can't do from your own knowledge.",
        "- Answer directly, without tools, whenever your own knowledge is enough: explanations, recipes, writing, "
        "advice, code, math, ideas. Never refuse because \"there's no tool\" for something you can just answer.",
        "- Call a tool when the request needs live or current data, the user's accounts, this computer, or saving "
        "something. Then do it; never describe an action instead of doing it.",
        "- Code, schemas, designs and drafts go in your reply as text. Write a file only when the user asks you to "
        "save or create a file.",
        "- Don't search the web for general knowledge you already have (how things work, design patterns, "
        "standard libraries). Search for current events, prices, specific pages, or things you don't know.",
        "- Never say something is done (saved, sent, opened, closed, scheduled) unless a tool result says it happened.",
        "- Call several tools in one step when they don't depend on each other; they run in parallel. "
        "You see every result before you answer, and you can keep calling tools until the job is done.",
        "- Never answer from memory about the current state of this computer or the user's accounts "
        "(volume, brightness, files, mail, repos): call the tool each time.",
        "- After the results, answer briefly but say what happened: what you found, and what was saved or changed "
        "with its exact day and time as the tool reported it. Only use links that appear in tool results.",
        "- Dates and times in tool arguments are the user's local time, format YYYY-MM-DDTHH:MM.",
        "- Never use a tool for today's date, the day of the week, or the local time: read them from 'Right now'.",
        "- For lookups, use use_skill with a skill id from the Skills section when one fits; otherwise web_search.",
        "- Deep research runs only when the user types /research <topic>.",
        "- If a tool you need is not loaded, call tool_search to load it.",
        "- When the user refers to something earlier in this chat that isn't in view (a decision, a number, code "
        "you wrote), call search_conversation instead of guessing. Stay consistent with what was decided.",
        "- If a tool fails, say what failed. Don't retry the same call with the same arguments.",
    ])


def get_tools_for_prompt() -> str:
    """Return a compact tool list for inclusion in Luna's system prompt."""
    lines = [
        "## Tool calling — MANDATORY rules",
        "",
        "To call a tool, emit this JSON anywhere in your reply (the parser extracts it):",
        '  {"tool_call": {"tool": "<name>", "args": {<key:value>}, "speak": "<one-line confirmation>"}}',
        "",
        "RULES — you MUST call a tool (not just describe it) when:",
        "  - User asks to SEARCH the web, find current info, news, or prices → web_search",
        "  - NEVER call web_research yourself — deep research only runs when the user types /research <topic>",
        "  - A request matches one of the lookup skills listed under Skills (e.g. finding postings, papers, products, places) "
        "→ use_skill with that skill's id and the user's request; for anything else that needs the web → web_search",
        "  - NEVER search the web for today's date, day of the week, or the local time — read them from the 'Right now' section",
        "  - User asks for a DATASET, data file, or training data → dataset_search",
        "  - User asks to CREATE or SAVE a file in the workspace → workspace_write",
        "  - User asks to READ a file from the workspace → workspace_read",
        "  - User asks to check/read/fetch/search mail, mails, email, emails, inbox, messages, or anything in Gmail → google_workspace",
        "  - User asks about GitHub repos, PRs, pull requests, issues, commits, changed files, or what a user updated in a PR → github_* tools",
        "  - User says 'my repo' or 'my Luna repo' with a GitHub/PR/issue question → use github_default_repo or the local GitHub origin, not web_search",
        "  - User asks about calendar, Drive, Docs, Sheets, Slides, Tasks, or any Google service → google_workspace",
        "  - User asks about Outlook, OneDrive, Teams, Excel, To Do, or any Microsoft service → microsoft_workspace",
        "  - User asks to SWITCH audio device → switch_audio",
        "  - User asks to CLOSE, QUIT, or KILL a running app → close_app (never claim it's closed without calling this)",
        "  - User asks to CREATE a task or calendar event → create_task / create_event",
        "",
        "DO NOT describe what you would do — DO IT by emitting the tool_call JSON.",
        "DO NOT say 'Sure, checking your Gmail' without also emitting the tool_call JSON.",
        "If the user says a vague follow-up like 'do it now', 'go ahead', 'try again', or 'yes' after you already "
        "described an action — that means: actually run that SAME action now via its tool_call/bracket command. "
        "Never respond with 'I'm trying to...' or 'please wait while I...' as filler text with no tool_call attached — "
        "that is a lie. Either call the tool for real, or say plainly that you can't and why.",
        "",
        "Examples:",
        '  User: "search for latest AI news"',
        '  → {"tool_call": {"tool": "web_search", "args": {"query": "latest AI news 2025"}, "speak": "Searching now."}}',
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
        '  User: "what did alice update in her PR in my repo"',
        '  → {"tool_call": {"tool": "github_summarize_user_pr", "args": {"repo": "", "user": "alice", "state": "all"}, "speak": "Checking GitHub PRs."}}',
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

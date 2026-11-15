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
from backend.services.search_query import resolve_search_query
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

    # ── Promise without action ────────────────────────────────────────────────
    # "Sure, let's check that out." with no tool call is the local model
    # narrating a search it never ran. Run it, with the query resolved from the
    # conversation so follow-ups deep into a chat still search the right thing.
    # Not when files are attached: "let me check the document" is about the file.
    if tc is None and not getattr(ctx, "attachment_ids", None) and _promises_lookup(full_response, ctx.user_message):
        query = await resolve_search_query(ctx.user_message, getattr(ctx, "history", None))
        logger.info("Model promised a lookup without a tool call — running web_search(%r)", query)
        tc = {"tool": "web_search", "args": {"query": query}, "speak": ""}

    if tc is None:
        await finish_plain_reply(ctx)
        return

    # Deep research is opt-in via /research (handled in the dispatch stage). If
    # the model reaches for it on its own, fall back to a plain web search.
    if tc.get("tool") == "web_research":
        logger.info("Model requested web_research without /research — downgrading to web_search")
        tc = {**tc, "tool": "web_search"}

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

    # ── Lookups go through the skill runtime ──────────────────────────────────
    # use_skill names a skill; a plain web_search is matched to the best skill
    # (skills/*) or runs as a grounded general search.
    if tool_name in ("use_skill", "web_search"):
        await _run_lookup(ctx, tool_name, args)
        return

    # ── Execute the tool ──────────────────────────────────────────────────────
    result = await execute_tool_call(tc, ctx.db, ctx.conv.id)
    ctx.tool_succeeded = "fail" not in result and "error" not in result

    # ── Process result based on tool type ─────────────────────────────────────
    _info_tools = {
        "web_search", "web_research", "web_fetch", "dataset_search",
        "workspace_read", "workspace_read_base64", "browser_read",
        "github_list_repos", "github_list_issues", "github_list_prs",
        "github_get_pr", "github_summarize_user_pr", "slack_search_messages", "slack_channel_history",
        "jira_search_issues", "jira_get_issue", "get_system_info", "get_volume",
        "get_brightness", "get_clipboard",
    }

    if tool_name in _info_tools:
        verified = await verify_tool_result(tool_name, args, result, ctx.user_message)
        ctx.full_response = verified or strip_tool_call_json(full_response)

    elif tool_name in ("create_task", "create_event"):
        # The model's "your meeting is scheduled" was written before anything
        # was saved; the result is read back from the database.
        ctx.full_response = result

    elif tool_name == "google_workspace" and args.get("service") == "gmail":
        _handle_gmail_tool_result(ctx, result, full_response)

    elif speak:
        ctx.full_response = speak
    else:
        ctx.full_response = strip_tool_call_json(full_response) or result[:300]


async def finish_plain_reply(ctx: ChatContext) -> None:
    """Checks on a final model answer (from the single-shot path or the agent loop)."""
    # Links must come from something the model was actually given (conversation,
    # files, tool results), not its memory — invented URLs look real.
    # After a real lookup, offering to "search and find real ones" makes no
    # sense: drop invented links quietly.
    searched = bool({"web_search", "use_skill", "web_fetch", "browser_read"} & set(getattr(ctx, "tools_used", None) or []))
    ctx.full_response = strip_unverified_links(ctx.full_response, _known_sources(ctx), notice=not searched)
    # The agent loop saves tasks/events through tools. The model had those tools
    # and chose; only correct a reply that *claims* a save that never happened.
    # (Acting on the user's wording alone replaced a recall answer — "remind me:
    # what's the project called?" — with a junk task.)
    from backend.services.command_parser.schedule import claims_saved
    if not {"create_task", "create_event"} & set(getattr(ctx, "tools_used", None) or []):
        if getattr(ctx, "route", "") != "agent_loop" or claims_saved(ctx.full_response):
            await _ensure_promised_action(ctx)
    _save_schedule_now(ctx)
    _confirm_bare_actions(ctx)


_ACTION_TAG_RE = re.compile(r"\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET|FACE|AWAY)(?::[^\]]*)?\]")


async def _ensure_promised_action(ctx: ChatContext) -> None:
    """Never let "your reminder's set" stand when nothing was saved: create the
    task/event from the conversation, or say plainly that it isn't saved yet."""
    from backend.services.command_parser.schedule import extract_item, to_command, wants_saved

    if not wants_saved(ctx.user_message, ctx.full_response):
        return
    item = await extract_item(ctx.user_message, getattr(ctx, "history", None) or [])
    command = to_command(item) if item else None
    from backend.services.command_parser.schedule import MAX_CLAIM_CHARS, claims_saved, reply_prose
    if command:
        logger.info("Reply promised a %s without a command — creating it: %s", item["kind"], command)
        if len(reply_prose(ctx.full_response)) > MAX_CLAIM_CHARS:
            ctx.full_response = f"{ctx.full_response.rstrip()}\n{command}"   # keep a real answer; save beside it
        else:
            ctx.full_response = command      # _confirm_bare_actions turns this into the confirmation text
        return
    if claims_saved(ctx.full_response):
        missing = "when it is" if item and item.get("title") else "what to call it and when it is"
        ctx.full_response = f"I haven't saved that yet — tell me {missing} and I'll add it."


_SCHEDULE_TAG_RE = re.compile(r"\[(?:TASK|EVENT):[^\]]*\]", re.IGNORECASE)


def _save_schedule_now(ctx: ChatContext) -> None:
    """Save [TASK]/[EVENT] tags before the reply is shown, verify each against the
    database, and let the reply say what is actually stored (or what failed)."""
    from backend.services.command_parser import parse_commands
    from backend.services.command_parser.commands import save_and_verify
    from backend.services.command_parser.schedule import CLAIM_RE

    reply = ctx.full_response or ""
    if not _SCHEDULE_TAG_RE.search(reply):
        return
    commands = [c for c in parse_commands(reply, user_message=ctx.user_message) if c["type"] in ("task", "event")]
    lines = [save_and_verify(ctx.db, c) for c in commands]
    rest = _SCHEDULE_TAG_RE.sub("", reply).strip()
    # The model's own "it's on your calendar" is dropped — the verified lines say it.
    if rest and not CLAIM_RE.search(rest):
        ctx.full_response = "\n".join([rest, *lines])
    else:
        ctx.full_response = "\n".join(lines)


def _confirm_bare_actions(ctx: ChatContext) -> None:
    """The model sometimes replies with only a command tag ("[TASK:…]"), which
    shows the user nothing. Say what is being done, from the tag itself."""
    if _ACTION_TAG_RE.sub("", ctx.full_response or "").strip():
        return
    from backend.services.command_parser import parse_commands
    from backend.services.command_parser.commands import describe_commands

    try:
        summary = describe_commands(parse_commands(ctx.full_response, user_message=ctx.user_message), ctx.db)
    except Exception as e:
        logger.warning("Could not describe actions: %s", e)
        return
    if summary:
        # Keep the tags after the text — finalize still executes them.
        ctx.full_response = f"{summary}\n{ctx.full_response.strip()}"


async def _run_lookup(ctx: ChatContext, tool_name: str, args: dict) -> None:
    from backend.services.chat_pipeline.stage_dispatch import _search_answer_context
    from backend.services.skill_runtime import get_search_skill, pick_search_skill, run_search_skill, run_web_search

    model_request = str(args.get("request") or args.get("query") or "").strip()
    user_request = ctx.user_message
    skill = get_search_skill(str(args.get("skill", ""))) if tool_name == "use_skill" else None
    if skill is None:
        skill = pick_search_skill(f"{user_request} {model_request}")
    history = getattr(ctx, "history", None) or []
    context, documents = await _search_answer_context(ctx, history, user_request)
    if skill:
        # The skill extracts what it needs from the user's own words; the
        # model's paraphrase is only a hint.
        run = await run_search_skill(skill, user_request, history, documents=documents, context=context)
    else:
        run = await run_web_search(user_request, history, context=context, candidate=model_request or None)
    logger.info("Lookup via %s (model called %s)", run.skill_id, tool_name)
    ctx.tool_succeeded = bool(run.results_text) and not run.results_text.startswith("No ")
    ctx.full_response = run.answer


_PROMISE_RE = re.compile(
    r"\b(?:let(?:'s|\s+me|\s+us)\s+(?:check|look|search|find|see|dig|pull)"
    r"|i(?:'ll|\s+will)\s+(?:check|look|search|find|dig|pull\s+up)"
    r"|(?:checking|searching|looking)\s+(?:that|it|this|now|for|into|up)"
    r"|one\s+(?:moment|sec(?:ond)?)|give\s+me\s+a\s+(?:moment|sec(?:ond)?))\b",
    re.IGNORECASE,
)
# Promises about the user's own data belong to other tools, never a web search.
_PERSONAL_DATA_RE = re.compile(
    r"\b(?:e-?mails?|inbox|gmail|outlook|calendar|meetings?|schedule|drive|onedrive|files?|folders?|"
    r"tasks?|reminders?|spotify|playlist|song|music|repo|pull\s+requests?|prs?|issues?|screen|"
    r"documents?|pdfs?|attachments?|spreadsheets?|sheets?|slides?|decks?|images?|pictures?|photos?)\b",
    re.IGNORECASE,
)
_WIDGET_TAG_RE = re.compile(r"\[[A-Z_]+:[^\]]*\]")


_MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_BARE_URL_RE = re.compile(r"(?<![(\[\w])https?://[^\s<>()\"'\]]+")


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip(".,;:!?)]}'\"").lower()
    url = re.sub(r"^https?://(www\.)?", "", url)
    return url.rstrip("/")


def _is_homepage(url: str) -> bool:
    return "/" not in _normalize_url(url)


def _known_sources(ctx: ChatContext) -> str:
    parts = [getattr(ctx, "system_prompt", "") or "", getattr(ctx, "document_context", "") or ""]
    parts += [m.get("content", "") for m in (getattr(ctx, "messages", None) or [])]
    parts += list(getattr(ctx, "tool_outputs", None) or [])      # agent-loop tool results
    return "\n".join(parts)


def strip_unverified_links(text: str, known: str, notice: bool = True) -> str:
    """Remove URLs the model wasn't given (conversation, documents, prompt).

    Bare homepages ("python.org") are kept — the problem is invented deep links
    (listings, doc pages, product pages) that look real and 404.
    """
    if not text or "http" not in text:
        return text
    known_urls = {_normalize_url(u) for u in re.findall(r"https?://[^\s<>()\"'\]]+", known or "")}
    removed = 0

    def verified(url: str) -> bool:
        norm = _normalize_url(url)
        return _is_homepage(url) or norm in known_urls or any(k.startswith(norm) for k in known_urls)

    def replace_md(match: re.Match) -> str:
        nonlocal removed
        if verified(match.group(2)):
            return match.group(0)
        removed += 1
        label = match.group(1)
        return label if not re.fullmatch(r"(?i)\s*(?:\w+\s+)*(?:link|here|source|website|url)\s*", label) else "(link removed)"

    def replace_bare(match: re.Match) -> str:
        nonlocal removed
        if verified(match.group(0)):
            return match.group(0)
        removed += 1
        return "(link removed)"

    cleaned = _BARE_URL_RE.sub(replace_bare, _MD_LINK_RE.sub(replace_md, text))
    if removed:
        logger.info("Removed %d unverified link(s) from a model reply", removed)
    if removed and notice:
        cleaned = cleaned.rstrip() + (
            f"\n\n_I removed {removed} link{'s' if removed != 1 else ''} I couldn't verify. "
            "Ask me to search and I'll find real ones._"
        )
    return cleaned


def _promises_lookup(response: str, user_message: str) -> bool:
    """True when the reply only announces a lookup instead of answering."""
    visible = _WIDGET_TAG_RE.sub("", strip_tool_call_json(response or "")).strip()
    if not visible or not _PROMISE_RE.search(visible):
        return False
    if _PERSONAL_DATA_RE.search(visible) or _PERSONAL_DATA_RE.search(user_message or ""):
        return False
    # A real answer that happens to say "let me check" is long; a bare promise is short.
    return len(visible.split()) <= 40


def _try_bracket_formats(response: str) -> dict | None:
    """
    Try legacy bracket-format tool calls: [WEB_SEARCH:...], [WEB_RESEARCH:...], etc.
    Returns a tool call dict or None.
    """
    patterns = [
        (r'\[WEB_SEARCH:([^\]]+)\]', "web_search", lambda m: {"query": m.group(1).strip()}),
        (r'\[WEB_RESEARCH:([^\]]+)\]', "web_research", lambda m: {"query": m.group(1).strip()}),
        (r'\[WEB_FETCH:([^\]]+)\]', "web_fetch", lambda m: {"url": m.group(1).strip()}),
        # The local model sometimes invents a "web_search" widget filled with
        # made-up results instead of calling the tool; search its title for real.
        (r'\[WIDGET:\s*web_(?:search|research)\s*\|([^|\]]+)', "web_search", lambda m: {"query": m.group(1).strip()}),
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


def gmail_widget_from_result(result: str) -> dict | None:
    """The email panel widget for a Gmail search result, or None."""
    try:
        messages = json.loads(result).get("data", {}).get("messages", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None
    if not messages:
        return None
    return {
        "type": "widget",
        "kind": "emails",
        "title": "Your Emails",
        "body": json.dumps([{
            "from": m.get("from", ""),
            "subject": m.get("subject", "(no subject)"),
            "date": m.get("date", ""),
            "snippet": m.get("snippet", ""),
        } for m in messages]),
    }


def _handle_gmail_tool_result(ctx: ChatContext, result: str, full_response: str) -> None:
    """Parse Gmail tool result and build widget command."""
    widget = gmail_widget_from_result(result)
    if widget:
        ctx.gmail_widget_cmd = widget
        count = len(json.loads(widget["body"]))
        ctx.full_response = f"Here {'are' if count != 1 else 'is'} {count} email{'s' if count != 1 else ''} — opening in the panel."
        return
    try:
        json.loads(result)
        ctx.full_response = "No emails found."
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Gmail tool result parsing failed: %s", e)
        ctx.full_response = strip_tool_call_json(full_response) or result[:300]

"""
dispatch stage — Fast-path regex-based command detection.

If a direct command is detected (Spotify, app launch, Gmail, research,
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
from backend.services.command_parser.clock import answer_clock_question, parse_clock_question
from backend.services.command_parser.research import (
    extract_explicit_web_search_query,
    is_search_request,
    refers_to_own_content,
)
from backend.services.files import build_attachment_context
from backend.services.skill_runtime import (
    all_ask_replies,
    choose_skill_with_model,
    pick_search_skill,
    run_search_skill,
    run_web_search,
)
from backend.services.tool_runner import execute_tool_call, verify_tool_result
from backend.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)

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
_SPOTIFY_NOW_PLAYING_RE = re.compile(
    r"\b(?:what|which)\b.{0,15}\b(?:song|track|music)\b.{0,15}\bplay\w*\b"
    r"|\bany\s+song\s+play\w*\b"
    r"|\bwhat'?s\s+play\w*\b"
    r"|\bsong\s+play\w*\s+(?:right\s+now|now|currently)\b",
    re.IGNORECASE,
)


async def dispatch_direct_commands(ctx: ChatContext) -> None:
    """
    Detect and handle direct commands that bypass LLM generation.
    Sets ctx.dispatched = True if handled.
    """
    msg = ctx.user_message

    # ── Research (explicit /research command only) ────────────────────────────
    # Checked first so an explicit command is never captured by a keyword fast
    # path below (e.g. "/research github copilot" → GitHub handler).
    direct_research_query = extract_direct_research_query(msg)
    if direct_research_query:
        ctx.dispatched = True
        ctx.direct_command_type = "research"
        ctx.had_tool_call = True
        tc = {"tool": "web_research", "args": {"query": direct_research_query}, "speak": ""}
        result = await execute_tool_call(tc, ctx.db, ctx.conv.id)
        ctx.tool_succeeded = "fail" not in result and "error" not in result
        ctx.full_response = await verify_tool_result("web_research", {"query": direct_research_query}, result, msg)
        ctx.full_response_parts = [ctx.full_response]
        return

    history = getattr(ctx, "history", None) or []
    has_files = bool(ctx.attachment_ids)

    # ── "I'll upload it, then …" — the file isn't here yet ────────────────────
    # Answering now would mean answering about a file that doesn't exist.
    if _UPLOAD_LATER_RE.search(msg) and not has_files:
        ctx.dispatched = True
        ctx.direct_command_type = "await_upload"
        ctx.full_response = wait_for_upload_reply(msg)
        ctx.full_response_parts = [ctx.full_response]
        return

    # ── A pending request completed by this message ───────────────────────────
    # The promised file arriving ("find me" + PDF) or the answer to a skill's
    # clarifying question: the earlier request is what's being asked now.
    request = _carried_request(msg, history, has_files)
    carried = request != msg
    if carried:
        ctx.user_message = request
        if getattr(ctx, "messages", None):
            ctx.messages[-1] = {**ctx.messages[-1], "content": request}

    # ── Several steps in one request → the agent loop, not a shortcut ─────────
    # A shortcut would answer the first step and silently drop the rest.
    from backend.services.agent_loop.routing import is_multi_step
    from backend.services.llm.tool_calling import native_tools_supported
    if native_tools_supported() and is_multi_step(request):
        return

    # ── Lookups: a matching skill (skills/*) or a grounded web search ─────────
    # Answering these from the model alone produced invented results and URLs.
    # Explicit search phrasing may use any skill; otherwise only "strong"
    # skills (whose intent alone implies a lookup) route here, and not when the
    # message is about the user's own file or data.
    explicit = is_search_request(request) and not _GMAIL_INTENT_RE.search(request)
    about_own_content = refers_to_own_content(request) or (has_files and not carried)
    skill = pick_search_skill(request, strong_only=not explicit) if (explicit or not about_own_content) else None
    # "What's the news today?" has no topic to search for: today's headlines
    # come from the news feeds (daily_news in the agent loop). News *about*
    # something still goes to the news-search skill.
    from backend.services.agent_loop.grounding import is_general_news
    if skill is not None and skill.id == "news-search" and is_general_news(request) and native_tools_supported():
        return
    if explicit and skill is None:
        # No skill's patterns matched ("find me good ramen"): let the model pick
        # from the skills' descriptions before falling back to a plain search.
        skill = await choose_skill_with_model(request, history)
    if explicit or skill:
        ctx.dispatched = True
        context, documents = await _search_answer_context(ctx, history, request)
        if skill:
            run = await run_search_skill(skill, request, history, documents=documents, context=context)
        else:
            run = await run_web_search(request, history, context=context,
                                       candidate=extract_explicit_web_search_query(request))
        ctx.direct_command_type = f"skill:{run.skill_id}"
        ctx.had_tool_call = not run.asked
        ctx.tool_succeeded = bool(run.results_text) and not run.results_text.startswith("No ")
        ctx.full_response = run.answer
        ctx.full_response_parts = [ctx.full_response]
        return

    # A message with files is about the files: "what's the date?" on a contract
    # means the contract's date, not today's. Only the explicit commands above
    # (/research, "web search …") still apply.
    if ctx.attachment_ids:
        return

    # ── Date / time ───────────────────────────────────────────────────────────
    # Answered from the local clock: the model otherwise tends to web-search
    # "what day is it" and trust whatever a random page says.
    clock_query = parse_clock_question(msg)
    if clock_query:
        ctx.dispatched = True
        ctx.direct_command_type = "clock"
        ctx.full_response = answer_clock_question(clock_query)
        ctx.full_response_parts = [ctx.full_response]
        return

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

        if bool(_SPOTIFY_NOW_PLAYING_RE.search(msg)):
            ctx.dispatched = True
            ctx.direct_command_type = "spotify"
            # spotify_track above is skipped in CLI mode — fetch for real here
            # since the user is directly asking, not just implicitly checking.
            now_playing = spotify_track if spotify_track is not None else spotify_service.get_current()
            if now_playing:
                state = "Playing" if now_playing.get("is_playing") else "Paused"
                ctx.full_response = f'{state}: "{now_playing["title"]}" by {now_playing["artist"]}.'
            elif spotify_service.is_connected:
                ctx.full_response = "Nothing's playing on Spotify right now."
            else:
                ctx.full_response = "Spotify isn't connected yet."
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


WAIT_PREFIX = "Sounds good — attach"
_UPLOAD_LATER_RE = re.compile(
    r"\b(?:i'?ll|i\s+will|let\s+me|gonna|going\s+to|about\s+to|i'?m\s+going\s+to)\s+"
    r"(?:upload|attach|send|share|drop|add)\b|\buploading\b",
    re.IGNORECASE,
)
_FILE_NOUN_RE = re.compile(
    r"\b(resume|cv|cover\s+letter|contract|document|doc|file|pdf|paper|report|screenshot|image|photo|picture|"
    r"spreadsheet|sheet|slides?|deck|code|logs?|notes|essay|invoice|statement)\b",
    re.IGNORECASE,
)
# A new instruction of its own ("summarize this" with the file) is not the
# completion of an earlier request.
_OWN_REQUEST_RE = re.compile(
    r"\b(?:summari[sz]e|summary|review|rate|score|explain|translate|proofread|rewrite|improve|fix|"
    r"what\s+(?:is|does|are)|how\s+(?:do|does|can))\b",
    re.IGNORECASE,
)


def wait_for_upload_reply(msg: str) -> str:
    noun = _FILE_NOUN_RE.search(msg)
    what = f"your {noun.group(1).lower()}" if noun else "it"
    return f"{WAIT_PREFIX} {what} (📎 or drag it into the chat) and I'll take it from there."


def _carried_request(msg: str, history: list[dict], has_files: bool) -> str:
    """Merge the user's pending request into the message that completes it:
    the promised file arriving, or the answer to a skill's clarifying
    question. Anything else stands on its own."""
    previous_user = next((m["content"] for m in reversed(history) if m.get("role") == "user"), "")
    previous_reply = next((m["content"] for m in reversed(history) if m.get("role") == "assistant"), "")
    if not previous_user or _OWN_REQUEST_RE.search(msg):
        return msg
    waiting = previous_reply.startswith(WAIT_PREFIX) or previous_reply in all_ask_replies()
    promised_file = has_files and bool(_UPLOAD_LATER_RE.search(previous_user))
    if (waiting or promised_file) and len(msg.split()) <= 12:
        return f"{previous_user} {msg}"
    return msg


async def _search_answer_context(ctx: ChatContext, history: list[dict] | None, query: str) -> tuple[str, str]:
    """(context, documents): recent turns + attached documents, so "rate each
    for my chances" or "links for these" uses what the user actually shared."""
    parts = []
    turns = [m for m in (history or []) if m.get("content")][-6:]
    if turns:
        lines = []
        for m in turns:
            text = re.sub(r"\n\s*References:[\s\S]*$", "", m["content"], flags=re.IGNORECASE)
            text = " ".join(text.split())
            lines.append(f"{'User' if m['role'] == 'user' else 'Luna'}: {text[:600]}")
        parts.append("Recent conversation:\n" + "\n".join(lines))
    try:
        documents = await build_attachment_context(ctx.db, ctx.conv.id, query)
    except Exception as e:
        logger.warning("Attachment context for search answer failed: %s", e)
        documents = ""
    documents = documents.split("</documents>")[0] + "</documents>" if documents else ""
    if documents:
        parts.append(documents)
    return "\n\n".join(parts), documents


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

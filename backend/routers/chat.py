import json
import re
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import get_db, Conversation, Message
from backend.models.schemas import ChatRequest, ConversationOut, ConversationDetail, StatusResponse
from backend.services.llm import ollama
from backend.services.memory_manager import MemoryManager
from backend.services.personality import PersonalityEngine, assess_user_sentiment
from backend.services.activity_tracker import ActivityTracker
from backend.services.media_context import get_watching_context
from backend.services.scheduler import proactive_queue
from backend.services.permission_manager import permission_manager
from backend.services.task_planner import is_complex_task, generate_plan, TaskPlan
from backend.services.state_engine import state_engine
from backend.services.coding_agent import stream_coding_agent
from backend.services.contradiction_store import pop as _pop_contradiction_notes
from backend.services.vision import get_visual_context

# Service modules extracted from this file
from backend.services.prompt_builder import (
    build_system_prompt,
    build_cli_system_prompt,
    build_business_system_prompt,
    get_live_data_section,
)
from backend.services.response_formatter import format_luna_response, ensure_references as _ensure_references
from backend.services.tool_runner import (
    execute_tool_call,
    verify_tool_result,
    parse_tool_call_json,
    strip_tool_call_json,
)
from backend.services.command_parser import (
    is_coding_request,
    parse_user_launch_request,
    parse_user_spotify_request,
    extract_direct_research_query,
    extract_direct_dataset_query,
    parse_commands,
    execute_commands,
)
from backend.services.chat_background import post_conversation_processing, track_activity_bg
from backend.services.shared_context import get_active_conversation_id, set_active_conversation_id

_extract_direct_research_query = extract_direct_research_query

router = APIRouter(prefix="/api/chat", tags=["chat"])

_active_plans: dict[int, TaskPlan] = {}

_FACE_ON_RE  = re.compile(r'face\s*(mode|tracking|detection|cam(?:era)?)?\s*(on|enable|start|activate|open)\b', re.IGNORECASE)
_FACE_OFF_RE = re.compile(r'face\s*(mode|tracking|detection|cam(?:era)?)?\s*(off|disable|stop|deactivate|close)\b', re.IGNORECASE)

_GMAIL_INTENT_RE = re.compile(
    r"\bany\s+mail\b"
    r"|\b(check|show|get|list|read|do i have|what('s| are| is))\b.{0,40}\b(email[s]?|mail[s]?|inbox|gmail)\b"
    r"|\b(email[s]?|mail[s]?|inbox|gmail)\b.{0,20}\b(today|unread|new|recent|latest)\b",
    re.IGNORECASE,
)

_CHAT_LOG = Path("data/chat.log")
_CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)


def _chat_print(line: str):
    print(line, flush=True)
    try:
        with open(_CHAT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


@router.post("/confirm/{confirm_id}")
async def confirm_tool(confirm_id: str, request: Request):
    body = await request.json()
    approved = bool(body.get("approved", False))
    ok = permission_manager.submit_answer(confirm_id, approved)
    return JSONResponse({"ok": ok, "confirm_id": confirm_id, "approved": approved})


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    voice: bool = False,
    cli: bool = False,
):
    """Stream a chat response from Luna with full memory and personality context."""
    voice_emotion  = request.headers.get("X-Voice-Emotion", "neutral")
    _volume        = float(request.headers.get("X-Volume", "0") or 0)
    _speech_speed  = float(request.headers.get("X-Speech-Speed", "0") or 0)
    _speech_dur    = float(request.headers.get("X-Speech-Duration", "0") or 0)

    conversation_id = req.conversation_id or get_active_conversation_id()

    if conversation_id:
        conv = db.query(Conversation).filter_by(id=conversation_id).first()
        if not conv:
            conv = Conversation(started_at=datetime.utcnow(), message_count=0)
            db.add(conv)
            db.commit()
            db.refresh(conv)
    else:
        conv = Conversation(started_at=datetime.utcnow(), message_count=0)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    set_active_conversation_id(conv.id)

    sentiment = assess_user_sentiment(req.message)
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=req.message,
        sentiment_score=sentiment,
    )
    db.add(user_msg)
    conv.message_count += 1
    db.commit()

    _src = "voice" if voice else "cli" if cli else "text"
    _chat_print(f"\n[chat] {settings.user_name} ({_src}): {req.message}")

    _is_business = settings.luna_variant == "business"

    memory = MemoryManager(db)
    personality = PersonalityEngine(db)
    activity_tracker = ActivityTracker(db)

    personality.update_mood(req.message, voice_emotion=voice_emotion if voice_emotion != "neutral" else None)

    current_state = state_engine.update(
        db,
        transcript      = req.message,
        emotion         = voice_emotion if voice_emotion != "neutral" else "neutral",
        volume          = _volume or None,
        speech_speed    = _speech_speed or None,
        speech_duration = _speech_dur or None,
    )
    state_context = state_engine.build_state_context(current_state)

    _SKIP_RETRIEVAL = {"hi", "hey", "hello", "heyy", "yo", "sup", "what's up",
                       "whats up", "good morning", "morning", "good night", "night",
                       "bye", "goodbye", "ok", "okay", "yep", "yup", "mm", "hmm"}
    _msg_lower = req.message.lower().strip(" .,!?")
    _skip = cli or voice or (len(_msg_lower.split()) < 4 and _msg_lower in _SKIP_RETRIEVAL)
    relevant_memories: dict[str, list[str]] = (
        {"short_term": [], "long_term": []} if _skip
        else await memory.retrieve_relevant(req.message)
    )

    recent_context   = memory.get_conversation_context(conv.id, settings.max_conversation_history)
    watching_context = get_watching_context().as_prompt_text()

    direct_launch_app    = None if _is_business else parse_user_launch_request(req.message)
    from backend.services.spotify import spotify_service
    spotify_track        = None if (cli or _is_business) else spotify_service.get_current()
    direct_spotify_cmd   = None if _is_business else parse_user_spotify_request(req.message, spotify_track)
    direct_face_on        = bool(_FACE_ON_RE.search(req.message))
    direct_face_off       = bool(_FACE_OFF_RE.search(req.message)) and not direct_face_on
    direct_gmail_request  = bool(_GMAIL_INTENT_RE.search(req.message))
    direct_research_query = None if direct_gmail_request else extract_direct_research_query(req.message)
    direct_dataset_query  = extract_direct_dataset_query(req.message)

    user_name = settings.user_name

    if cli:
        system_prompt = build_cli_system_prompt(user_name, recent_context)
    elif _is_business:
        system_prompt = build_business_system_prompt(
            user_name, recent_context,
            agenda=memory.get_upcoming_agenda(),
            live_data=get_live_data_section(),
        )
    else:
        _visual = get_visual_context()
        system_prompt = build_system_prompt(
            memory, personality, activity_tracker, relevant_memories,
            user_name, recent_context, watching_context, spotify_track,
            state_context=state_context,
            visual_context=_visual.as_prompt_text() if _visual else "",
        )

    _contradiction_notes = _pop_contradiction_notes(conv.id)
    if _contradiction_notes:
        system_prompt += "\n\n## Memory updates since last turn\n" + "\n".join(
            f"- {n}" for n in _contradiction_notes
        )

    history_limit = min(settings.max_conversation_history, 6) if cli else settings.max_conversation_history
    history = memory.get_recent_conversation(conv.id, history_limit)
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    messages = history + [{"role": "user", "content": req.message}]

    prev_luna = None
    for m in reversed(history):
        if m["role"] == "assistant":
            prev_luna = m["content"]
            break

    proactive = proactive_queue.pop(0) if proactive_queue else None

    full_response_parts: list[str] = []
    _tool_succeeded = False
    _task_completed = False

    async def generate():
        nonlocal full_response_parts, _tool_succeeded, _task_completed
        _voice_streamed = False
        _had_tool_call = False
        _gmail_widget_cmd: dict | None = None
        conv_id_header = json.dumps({"conversation_id": conv.id, "type": "meta"})
        yield f"data: {conv_id_header}\n\n"

        if proactive:
            yield f"data: {json.dumps({'type': 'proactive', 'message': proactive})}\n\n"

        full_response = ""

        # ── Fast-path: direct regex-detected commands ─────────────────────────
        if direct_spotify_cmd:
            action = direct_spotify_cmd["action"]
            if action == "play":
                ok = spotify_service.play(direct_spotify_cmd.get("query"))
                if ok:
                    full_response = "Playing."
                elif spotify_service.needs_auth:
                    auth_url = spotify_service.get_auth_url()
                    if auth_url:
                        import webbrowser
                        webbrowser.open(auth_url)
                    full_response = "Spotify needs to be connected first. I opened the authorization page in your browser. Log in, allow access, then try again."
                elif not spotify_service._ready:
                    full_response = "Spotify isn't configured. Add spotify_client_id and spotify_client_secret to your .env file."
                else:
                    full_response = "Spotify is configured, but playback is not available. Open Spotify on this computer or another active device, then try again."
                _tool_succeeded = ok if action == "play" else False
            elif action == "queue":
                ok = spotify_service.queue(direct_spotify_cmd.get("query") or "")
                full_response = "Queued." if ok else "I couldn't queue that."
                _tool_succeeded = ok
            elif action == "pause":
                ok = spotify_service.pause()
                full_response = "Paused." if ok else "I couldn't pause Spotify."
                _tool_succeeded = ok
            elif action == "next":
                ok = spotify_service.next_track()
                full_response = "Skipping." if ok else "I couldn't skip tracks."
                _tool_succeeded = ok
            elif action == "prev":
                ok = spotify_service.prev_track()
                full_response = "Going back." if ok else "I couldn't go back."
                _tool_succeeded = ok
            else:
                full_response = "I couldn't handle that Spotify command."
            full_response_parts = [full_response]

        elif direct_launch_app:
            from backend.services.app_launcher import launch_app
            success, launch_message = launch_app(direct_launch_app)
            full_response = f"Opening {direct_launch_app}." if success else launch_message
            _tool_succeeded = success
            full_response_parts = [full_response]

        elif direct_face_on:
            full_response = "[FACE:on] Face tracking activated."
            full_response_parts = [full_response]

        elif direct_face_off:
            full_response = "[FACE:off] Face tracking off."
            full_response_parts = [full_response]

        elif direct_gmail_request:
            _had_tool_call = True
            _q = "is:unread" if re.search(r"\bunread\b", req.message, re.IGNORECASE) else ""
            _gmail_tc = {"tool": "google_workspace", "args": {"service": "gmail", "action": "search_messages", "args": {"q": _q, "maxResults": 5}}, "speak": ""}
            result = await execute_tool_call(_gmail_tc, db, conv.id)
            _tool_succeeded = "fail" not in result and "error" not in result
            try:
                _res = json.loads(result)
                _msgs = _res.get("data", {}).get("messages", [])
                if _msgs:
                    _gmail_widget_cmd = {
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
                    full_response = f"Here {'are' if len(_msgs) != 1 else 'is'} {len(_msgs)} email{'s' if len(_msgs) != 1 else ''} — opening in the panel."
                else:
                    full_response = "No emails found in your inbox."
            except Exception:
                full_response = "Couldn't fetch your emails right now."
            full_response_parts = [full_response]

        elif direct_research_query:
            _had_tool_call = True
            tc = {"tool": "web_research", "args": {"query": direct_research_query}, "speak": ""}
            result = await execute_tool_call(tc, db, conv.id)
            _tool_succeeded = "fail" not in result and "error" not in result
            full_response = await verify_tool_result("web_research", {"query": direct_research_query}, result, req.message)
            full_response_parts = [full_response]

        elif direct_dataset_query:
            _had_tool_call = True
            tc = {"tool": "dataset_search", "args": {"query": direct_dataset_query}, "speak": ""}
            result = await execute_tool_call(tc, db, conv.id)
            _tool_succeeded = "fail" not in result and "error" not in result
            full_response = await verify_tool_result("dataset_search", {"query": direct_dataset_query}, result, req.message)
            full_response_parts = [full_response]

        else:
            plan = None
            # ── Coding agent fast-path ────────────────────────────────────────
            if is_coding_request(req.message) and not _is_business:
                _voice_streamed = True
                async for event in stream_coding_agent(messages, auto_confirm_shell=False):
                    etype = event.get("type")
                    if etype == "token":
                        tok = event["content"]
                        full_response_parts.append(tok)
                        yield f"data: {json.dumps({'type': 'message_part', 'content': tok})}\n\n"
                    elif etype == "tool_call":
                        yield f"data: {json.dumps({'type': 'coding_tool_call', 'tool': event['tool'], 'args': event['args']})}\n\n"
                    elif etype == "tool_result":
                        yield f"data: {json.dumps({'type': 'coding_tool_result', 'tool': event['tool'], 'result': event['result']})}\n\n"
                    elif etype == "confirmation_required":
                        _shell_cmd = event["args"].get("command", "")
                        _confirm_payload = {
                            "type": "confirmation_required",
                            "confirm_id": "shell_cmd",
                            "message": f"Run shell: {_shell_cmd}?",
                            "tool": event["tool"],
                            "args": event["args"],
                        }
                        yield f"data: {json.dumps(_confirm_payload)}\n\n"
                    elif etype == "error":
                        yield f"data: {json.dumps({'type': 'error', 'message': event['message']})}\n\n"
                        return
                full_response = "".join(full_response_parts)

            else:
                # ── Planning mode ─────────────────────────────────────────────
                plan = _active_plans.get(conv.id)
                if plan and not plan.done:
                    step_prompt = await plan.next_prompt()
                    step_messages = [{"role": "user", "content": step_prompt}]
                elif is_complex_task(req.message):
                    steps = await generate_plan(req.message)
                    if len(steps) > 1:
                        plan = TaskPlan(req.message, steps)
                        _active_plans[conv.id] = plan
                        yield f"data: {json.dumps({'type': 'plan', 'steps': steps, 'total': plan.total})}\n\n"
                        step_prompt = await plan.next_prompt()
                        step_messages = [{"role": "user", "content": step_prompt}]
                    else:
                        plan = None
                        step_messages = messages
                else:
                    plan = None
                    step_messages = messages

                # ── LLM generation ────────────────────────────────────────────
                try:
                    async for token in ollama.stream_chat(
                        step_messages, system_prompt,
                        num_ctx=None, num_predict=None,
                        temperature=0.5 if cli else 0.7,
                    ):
                        full_response_parts.append(token)
                        if voice or cli:
                            clean = re.sub(r'<think>.*?</think>', '', token, flags=re.DOTALL)
                            if clean:
                                yield f"data: {json.dumps({'type': 'message_part', 'content': clean})}\n\n"
                                _voice_streamed = True
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    return

                full_response = format_luna_response("".join(full_response_parts))

            # ── JSON tool call detection ──────────────────────────────────────
            tc = parse_tool_call_json(full_response)
            if not tc:
                _ws = re.search(r'\[WEB_SEARCH:([^\]]+)\]', full_response, re.IGNORECASE)
                if _ws:
                    tc = {"tool": "web_search", "args": {"query": _ws.group(1).strip()}, "speak": ""}
                    full_response = full_response[:_ws.start()].rstrip() + full_response[_ws.end():]
            if not tc:
                _wr = re.search(r'\[WEB_RESEARCH:([^\]]+)\]', full_response, re.IGNORECASE)
                if _wr:
                    tc = {"tool": "web_research", "args": {"query": _wr.group(1).strip()}, "speak": ""}
                    full_response = full_response[:_wr.start()].rstrip() + full_response[_wr.end():]
            if not tc:
                _wf = re.search(r'\[WEB_FETCH:([^\]]+)\]', full_response, re.IGNORECASE)
                if _wf:
                    tc = {"tool": "web_fetch", "args": {"url": _wf.group(1).strip()}, "speak": ""}
                    full_response = full_response[:_wf.start()].rstrip() + full_response[_wf.end():]
            if not tc:
                _ds = re.search(r'\[DATASET_SEARCH:([^\]]+)\]', full_response, re.IGNORECASE)
                if _ds:
                    tc = {"tool": "dataset_search", "args": {"query": _ds.group(1).strip()}, "speak": ""}
                    full_response = full_response[:_ds.start()].rstrip() + full_response[_ds.end():]
            if not tc:
                _ww = re.search(r'\[WORKSPACE_WRITE:([^|]+)\|([^\]]+)\]', full_response, re.IGNORECASE | re.DOTALL)
                if _ww:
                    tc = {"tool": "workspace_write", "args": {"path": _ww.group(1).strip(), "content": _ww.group(2)}, "speak": ""}
                    full_response = full_response[:_ww.start()].rstrip() + full_response[_ww.end():]
            if not tc:
                _wr2 = re.search(r'\[WORKSPACE_READ:([^\]]+)\]', full_response, re.IGNORECASE)
                if _wr2:
                    tc = {"tool": "workspace_read", "args": {"path": _wr2.group(1).strip()}, "speak": ""}
                    full_response = full_response[:_wr2.start()].rstrip() + full_response[_wr2.end():]
            if not tc:
                _gw = re.search(r'\[GMAIL(?:_CHECK)?\]', full_response, re.IGNORECASE)
                if _gw:
                    tc = {"tool": "google_workspace", "args": {"service": "gmail", "action": "search_messages", "args": {"q": "is:unread", "maxResults": 10}}, "speak": ""}
                    full_response = full_response[:_gw.start()].rstrip() + full_response[_gw.end():]

            _had_tool_call = tc is not None
            if tc:
                tool_name = tc.get("tool", "")
                args = tc.get("args", {})
                speak = tc.get("speak", "")

                decision, msg, confirm_id = permission_manager.check(tool_name, args)

                if decision == "block":
                    full_response = strip_tool_call_json(full_response) or (msg or "I can't do that.")
                elif decision == "confirm":
                    yield f"data: {json.dumps({'type': 'confirmation_required', 'confirm_id': confirm_id, 'message': msg, 'tool': tool_name, 'args': args})}\n\n"
                    for _ in range(60):
                        await asyncio.sleep(0.5)
                        approved = permission_manager.pop_answer(confirm_id)
                        if approved is not None:
                            break
                    else:
                        approved = False
                    if approved:
                        result = await execute_tool_call(tc, db, conv.id)
                        _tool_succeeded = "fail" not in result and "error" not in result
                        verified = await verify_tool_result(tool_name, args, result, req.message)
                        full_response = verified
                    else:
                        full_response = "Okay, I'll skip that."
                else:
                    result = await execute_tool_call(tc, db, conv.id)
                    _tool_succeeded = "fail" not in result and "error" not in result
                    _info_tools = {"web_search", "web_research", "web_fetch", "dataset_search",
                                   "workspace_read", "workspace_read_base64", "browser_read",
                                   "github_list_repos", "github_list_issues", "github_list_prs",
                                   "github_get_pr", "get_system_info", "get_volume",
                                   "get_brightness", "get_clipboard"}
                    if tool_name in _info_tools:
                        verified = await verify_tool_result(tool_name, args, result, req.message)
                        full_response = verified or strip_tool_call_json(full_response)
                    elif tool_name == "google_workspace" and args.get("service") == "gmail":
                        try:
                            _res = json.loads(result)
                            _msgs = _res.get("data", {}).get("messages", [])
                            if _msgs:
                                _gmail_widget_cmd = {
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
                                full_response = f"Here {'are' if len(_msgs) != 1 else 'is'} {len(_msgs)} email{'s' if len(_msgs) != 1 else ''} — opening in the panel."
                            else:
                                full_response = "No emails found."
                        except Exception:
                            full_response = strip_tool_call_json(full_response) or result[:300]
                    elif speak:
                        full_response = speak
                    else:
                        full_response = strip_tool_call_json(full_response) or result[:300]

            # ── Planning progress ─────────────────────────────────────────────
            if plan and not plan.done:
                plan.record_result(full_response[:80])
                if plan.done:
                    _task_completed = True
                    _active_plans.pop(conv.id, None)
                    yield f"data: {json.dumps({'type': 'plan_done', 'summary': plan.progress_summary()})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'plan_progress', 'step': plan.current, 'total': plan.total})}\n\n"

        # ── Stream visible parts ──────────────────────────────────────────────
        STRIP_RE = r"\s*\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET|FACE|WEB_SEARCH|WEB_RESEARCH|WEB_FETCH):[^\]]+\]"
        _cli_text = re.sub(STRIP_RE, "", full_response).strip()
        _cli_text = re.sub(r"<think>.*?</think>", "", _cli_text, flags=re.DOTALL).strip()
        if _cli_text:
            _chat_print(f"[chat] Luna: {_cli_text}")

        visible_text = re.sub(STRIP_RE, "", full_response).strip()
        # Tool responses (research, dataset, etc.) need full content; regular chat capped at 2 parts
        _max_parts = 10 if _had_tool_call else 2
        refs_match = re.search(r"\n\s*References:\s*", visible_text, flags=re.IGNORECASE)
        if refs_match:
            body_text = visible_text[:refs_match.start()].strip()
            refs_text = visible_text[refs_match.start():].strip()
            body_parts = [p.strip() for p in re.split(r"\n{2,}", body_text) if p.strip()]
            visible_parts = body_parts[:_max_parts] + ([refs_text] if refs_text else [])
        else:
            visible_parts = [p.strip() for p in re.split(r"\n{2,}", visible_text) if p.strip()][:_max_parts]

        if not visible_parts:
            visible_parts = [full_response] if full_response else [""]

        if not (_voice_streamed and not _had_tool_call):
            for index, part in enumerate(visible_parts):
                if index > 0 and not voice:
                    await asyncio.sleep(min(2.8, 1.35 + (len(part) * 0.018)))
                content = f"\n\n{part}" if cli and index > 0 else part
                yield f"data: {json.dumps({'type': 'message_part', 'content': content})}\n\n"

        luna_msg = Message(conversation_id=conv.id, role="assistant", content=full_response)
        db.add(luna_msg)
        conv.message_count += 1
        db.commit()

        commands = parse_commands(full_response, user_message=req.message)
        if _gmail_widget_cmd and not any(c.get("kind") == "emails" for c in commands):
            commands.append(_gmail_widget_cmd)
        if commands:
            yield f"data: {json.dumps({'type': 'commands', 'commands': commands})}\n\n"
            execute_commands(commands, db, conv.id)

        background_tasks.add_task(
            post_conversation_processing,
            db, conv.id, full_response, prev_luna or "", req.message,
            _tool_succeeded, _task_completed, False,
        )
        background_tasks.add_task(track_activity_bg, req.message, conv.id)

        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv.id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(Conversation)
        .order_by(Conversation.started_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/context")
def get_shared_context(db: Session = Depends(get_db)):
    conversation_id = get_active_conversation_id()
    conv = (
        db.query(Conversation).filter_by(id=conversation_id).first()
        if conversation_id
        else None
    )
    if conversation_id and not conv:
        set_active_conversation_id(None)
        conversation_id = None
    return {"active_conversation_id": conversation_id}


@router.post("/context")
async def set_shared_context(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    raw_id = body.get("active_conversation_id")
    conversation_id = raw_id if isinstance(raw_id, int) and raw_id > 0 else None
    if conversation_id and not db.query(Conversation).filter_by(id=conversation_id).first():
        conversation_id = None
    return set_active_conversation_id(conversation_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    return db.query(Conversation).filter_by(id=conversation_id).first()


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        db.delete(conv)
        db.commit()
        if get_active_conversation_id() == conversation_id:
            set_active_conversation_id(None)
    return StatusResponse(status="ok")

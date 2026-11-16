"""
context stage — Assemble memory, personality, state, and system prompt.
"""
import logging

from server.config import settings
from server.services.memory_manager import MemoryManager
from server.services.personality import PersonalityEngine
from server.services.activity_tracker import ActivityTracker
from server.services.media_context import get_watching_context
from server.services.state_engine import state_engine
from server.services.scheduler import proactive_queue
from server.services.prompt_builder import (
    build_system_prompt,
    build_cli_system_prompt,
    build_business_system_prompt,
    get_live_data_section,
)
from server.services.contradiction_store import pop as _pop_contradiction_notes
from server.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)

_SKIP_RETRIEVAL = {
    "hi", "hey", "hello", "heyy", "yo", "sup", "what's up",
    "whats up", "good morning", "morning", "good night", "night",
    "bye", "goodbye", "ok", "okay", "yep", "yup", "mm", "hmm",
}


async def build_context(ctx: ChatContext) -> None:
    """Retrieve memories, update personality/state, assemble the system prompt."""
    db = ctx.db
    ctx.is_business = settings.luna_variant == "business"

    memory = MemoryManager(db)
    personality = PersonalityEngine(db)
    activity_tracker = ActivityTracker(db)

    # Update mood/state
    personality.update_mood(
        ctx.user_message,
        voice_emotion=ctx.voice_emotion if ctx.voice_emotion != "neutral" else None,
    )
    current_state = state_engine.update(
        db,
        transcript=ctx.user_message,
        emotion=ctx.voice_emotion if ctx.voice_emotion != "neutral" else "neutral",
        volume=ctx.volume or None,
        speech_speed=ctx.speech_speed or None,
        speech_duration=ctx.speech_duration or None,
    )
    ctx.state_context = state_engine.build_state_context(current_state)

    # Memory retrieval (skip for trivial messages)
    _msg_lower = ctx.user_message.lower().strip(" .,!?")
    _skip = ctx.cli or ctx.voice or (len(_msg_lower.split()) < 4 and _msg_lower in _SKIP_RETRIEVAL)
    if _skip:
        ctx.relevant_memories = {"short_term": [], "long_term": []}
    else:
        ctx.relevant_memories = await memory.retrieve_relevant(ctx.user_message)

    # The transcript itself is sent as chat messages and fitted to the context
    # window at generation time; repeating it here only doubled its cost.
    ctx.conversation_summary = (getattr(ctx.conv, "summary", None) or "").strip()
    recent_context = (
        "- The conversation so far is in the chat messages. "
        "Older turns are summarized at the end of this prompt when they no longer fit."
    )
    watching_context = get_watching_context().as_prompt_text()

    user_name = settings.user_name

    # Skills load their full instructions only when relevant; include the last
    # couple of user turns so follow-ups ("do the same for X") keep the skill.
    _recent_user_turns = [
        m["content"] for m in memory.get_recent_conversation(ctx.conv.id, 5) if m["role"] == "user"
    ][-3:]
    skill_hint = " ".join(_recent_user_turns + [ctx.user_message])

    # Build system prompt based on variant/mode
    if ctx.cli:
        ctx.system_prompt = build_cli_system_prompt(user_name, recent_context, skill_hint=skill_hint)
    elif ctx.is_business:
        ctx.system_prompt = build_business_system_prompt(
            user_name, recent_context,
            agenda=memory.get_upcoming_agenda(),
            live_data=get_live_data_section(),
        )
    else:
        from server.services.spotify import spotify_service
        spotify_track = None if ctx.cli else spotify_service.get_current()
        ctx.system_prompt = build_system_prompt(
            memory, personality, activity_tracker, ctx.relevant_memories,
            user_name, recent_context, watching_context, spotify_track,
            state_context=ctx.state_context,
            skill_hint=skill_hint,
        )

    # Working state (code written, files attached) re-read every turn, so it
    # survives context fitting and summaries.
    try:
        from server.services.session_state import session_state_block
        _state = session_state_block(ctx.db, ctx.conv.id, ctx.user_message)
        if _state:
            ctx.system_prompt += "\n\n" + _state
    except Exception as e:
        logger.warning("Session state unavailable: %s", e)

    # Append contradiction notes if any
    _contradiction_notes = _pop_contradiction_notes(ctx.conv.id)
    if _contradiction_notes:
        ctx.system_prompt += "\n\n## Memory updates since last turn\n" + "\n".join(
            f"- {n}" for n in _contradiction_notes
        )

    # Build message history
    history_limit = min(settings.max_conversation_history, 6) if ctx.cli else settings.max_conversation_history
    history = memory.get_recent_conversation(ctx.conv.id, history_limit)
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    ctx.history = history
    ctx.messages = history + [{"role": "user", "content": ctx.user_message}]

    # Find previous Luna response for RL reward calculation
    for m in reversed(history):
        if m["role"] == "assistant":
            ctx.prev_luna = m["content"]
            break

    # Pop proactive message if any
    ctx.proactive_message = proactive_queue.pop(0) if proactive_queue else None

    logger.debug(
        "Context built: memories=%d, history=%d msgs, proactive=%s",
        sum(len(v) for v in ctx.relevant_memories.values()),
        len(ctx.history),
        bool(ctx.proactive_message),
    )

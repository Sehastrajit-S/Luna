"""Background processing tasks run after each chat turn."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from server.config import DATA_DIR, settings
from server.models.database import Conversation, Message, get_db
from server.services.memory_manager import MemoryManager
from server.services.personality import PersonalityEngine, compute_implicit_reward
from server.services.activity_tracker import ActivityTracker
from server.services.fact_extractor import (
    extract_facts_from_conversation,
    extract_emotional_arc,
    extract_session_facts,
    summarize_conversation,
    extract_user_name,
    format_conversation_for_extraction,
    _should_trigger_extraction,
)

logger = logging.getLogger(__name__)

# Rolling summary (compaction) every this many new messages. Last summarized
# message count per conversation; after a restart the first check re-summarizes.
SUMMARY_EVERY = 10
_summarized_at: dict[int, int] = {}


_NOT_A_STYLE_EXAMPLE_RE = re.compile(
    # Replies about live state or failures are facts of one moment, not style:
    # saved as "preferred examples" they get parroted instead of calling tools.
    r"\b(?:can(?:'|no)?t|couldn'?t|unable|not able|failed|error|doesn'?t support|not available)\b"
    r"|\b(?:volume|brightness|battery|clipboard|inbox|e-?mails?|calendar|tasks?|reminders?|repos?|files?)\b"
    r"|\d+\s?%|https?://|<!--luna-cards",
    re.IGNORECASE,
)
MAX_EXAMPLE_MESSAGE_CHARS = 300


def _is_style_example(user_message: str, luna_response: str) -> bool:
    return (len(user_message) <= MAX_EXAMPLE_MESSAGE_CHARS
            and not _NOT_A_STYLE_EXAMPLE_RE.search(user_message)
            and not _NOT_A_STYLE_EXAMPLE_RE.search(luna_response))


def _auto_save_rlhf_pair(user_message: str, luna_response: str, mood: str) -> None:
    """Persist a high-reward (message, response) pair to the RLHF training file."""
    if not _is_style_example(user_message, luna_response):
        return
    try:
        path = DATA_DIR / "rlhf_pairs.json"
        pairs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

        for p in pairs:
            if p.get("message", "")[:60].lower() == user_message[:60].lower():
                return

        auto_pairs = [i for i, p in enumerate(pairs) if p.get("auto_generated")]
        if len(auto_pairs) >= 100:
            pairs.pop(auto_pairs[0])

        pairs.append({
            "message": user_message[:300],
            "chosen": luna_response[:400],
            "mode": "response",
            "luna_tone": mood,
            "auto_generated": True,
        })
        path.write_text(json.dumps(pairs, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to save RLHF pair: %s", e)


async def track_activity_bg(message: str, conversation_id: int) -> None:
    """Background: track user activity after response is sent."""
    db = next(get_db())
    try:
        tracker = ActivityTracker(db)
        await tracker.process_message(message, conversation_id)
        active = tracker.get_current_activities()
        for act in active:
            await tracker.check_progress(message, act)
        tracker.sync_spotify_activity()
    except (OSError, RuntimeError) as e:
        logger.warning("Activity tracking failed for conv %d: %s", conversation_id, e)
    except Exception as e:
        logger.error("Unexpected error in track_activity_bg: %s", e, exc_info=True)
    finally:
        db.close()                               # also on errors: a failed run used to keep its connection


async def post_conversation_processing(
    db: Session,
    conversation_id: int,
    luna_response: str,
    prev_luna_response: str,
    last_user_message: str,
    tool_succeeded: bool = False,
    task_completed: bool = False,
    user_interrupted_tts: bool = False,
    skip_llm_work: bool = False,
) -> None:
    """Background: extract facts, compute RL reward, update personality.

    skip_llm_work: for small talk ("hi", "thanks") only the heuristic reward
    runs — there is nothing to extract, summarize, or classify.
    """
    try:
        memory = MemoryManager(db)
        personality = PersonalityEngine(db)

        if prev_luna_response:
            history = memory.get_recent_conversation(conversation_id, 6)
            user_msgs = [m["content"].lower() for m in history if m["role"] == "user"]
            is_repeat = (
                len(user_msgs) >= 2 and user_msgs[-1] == user_msgs[-2]
            ) if len(user_msgs) >= 2 else False

            low = last_user_message.lower()
            manual_correction = any(p in low for p in [
                "that's wrong", "you're wrong", "not what i said", "i didn't say",
                "you misunderstood", "that's not right", "wrong answer",
            ])

            reward = compute_implicit_reward(
                prev_luna_response,
                last_user_message,
                tool_succeeded=tool_succeeded,
                task_completed=task_completed,
                user_interrupted_tts=user_interrupted_tts,
                is_repeat_request=is_repeat,
                manual_correction=manual_correction,
            )
            response_features = personality.get_response_features(prev_luna_response)
            personality.apply_rl_reward(reward, response_features, conversation_id)

            if reward > 0.6:
                history = memory.get_recent_conversation(conversation_id, 8)
                trigger_msg = None
                for i, msg in enumerate(history):
                    if msg["role"] == "assistant" and prev_luna_response[:40] in msg["content"]:
                        if i > 0 and history[i - 1]["role"] == "user":
                            trigger_msg = history[i - 1]["content"]
                        break
                if trigger_msg:
                    _auto_save_rlhf_pair(trigger_msg, prev_luna_response, personality.get_state().current_mood)

        if skip_llm_work:
            return

        conv = db.query(Conversation).filter_by(id=conversation_id).first()
        if conv:
            on_interval = (conv.message_count % settings.fact_extraction_interval == 0)
            on_trigger  = (not on_interval and _should_trigger_extraction(last_user_message))

            if on_interval:
                msgs = memory.get_recent_conversation(conversation_id, 20)
                conv_text = format_conversation_for_extraction(msgs)
                await extract_facts_from_conversation(conv_text, db, conversation_id, memory)

                if settings.user_name == "friend":
                    name = await extract_user_name(conv_text)
                    if name:
                        await memory.store_fact(f"User's name is {name}", "personal", conversation_id)
                        settings.user_name = name

            elif on_trigger:
                msgs = memory.get_recent_conversation(conversation_id, 4)
                quick_text = format_conversation_for_extraction(msgs)
                await extract_facts_from_conversation(quick_text, db, conversation_id, memory)

            # Count stored messages, not conv.message_count: that counter races with
            # the next turn and could skip every multiple of 10 (no summary ever).
            total = db.query(Message).filter(Message.conversation_id == conversation_id).count()
            if total - _summarized_at.get(conversation_id, 0) >= SUMMARY_EVERY and total >= SUMMARY_EVERY:
                _summarized_at[conversation_id] = total
                msgs = memory.get_recent_conversation(conversation_id, 20)
                conv_text = format_conversation_for_extraction(msgs)
                # Rolling summary (compaction): fold the previous summary in so
                # it keeps covering turns that have left the context window.
                if conv.summary:
                    conv_text = f"Earlier summary: {conv.summary}\n\nRecent messages:\n{conv_text}"
                summary = await summarize_conversation(conv_text)
                if summary:
                    conv.summary = summary
                    db.commit()
                    await memory.store_conversation_summary(summary, conversation_id)

                # Decisions go into the append-only working state as well: a
                # summary rewritten every 10 messages drops old facts, this doesn't.
                recent_text = format_conversation_for_extraction(msgs)
                facts = await extract_session_facts(recent_text)
                if facts:
                    from server.services.session_state import add_session_facts
                    add_session_facts(db, conversation_id, facts)

                arc = await extract_emotional_arc(conv_text)
                if arc:
                    await memory.store_fact(
                        arc, "context",
                        conversation_id=conversation_id,
                        memory_type="short",
                        importance=0.6,
                        expires_in_days=7,
                    )

    except Exception as e:
        logger.error(
            "post_conversation_processing failed for conv %d: %s",
            conversation_id, e, exc_info=True,
        )
    finally:
        # This runs after the response, on the request's session, which the
        # request already closed; our queries reopened a connection. Release it,
        # or each turn leaks one and the pool (5 + 10) eventually times out.
        db.close()

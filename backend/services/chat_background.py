"""Background processing tasks run after each chat turn."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import Conversation, get_db
from backend.services.memory_manager import MemoryManager
from backend.services.personality import PersonalityEngine, compute_implicit_reward
from backend.services.activity_tracker import ActivityTracker
from backend.services.fact_extractor import (
    extract_facts_from_conversation,
    extract_emotional_arc,
    summarize_conversation,
    extract_user_name,
    format_conversation_for_extraction,
    _should_trigger_extraction,
)

logger = logging.getLogger(__name__)


def _auto_save_rlhf_pair(user_message: str, luna_response: str, mood: str) -> None:
    """Persist a high-reward (message, response) pair to the RLHF training file."""
    try:
        path = Path("data/rlhf_pairs.json")
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
    try:
        db = next(get_db())
        tracker = ActivityTracker(db)
        await tracker.process_message(message, conversation_id)
        active = tracker.get_current_activities()
        for act in active:
            await tracker.check_progress(message, act)
        db.close()
    except (OSError, RuntimeError) as e:
        logger.warning("Activity tracking failed for conv %d: %s", conversation_id, e)
    except Exception as e:
        logger.error("Unexpected error in track_activity_bg: %s", e, exc_info=True)


async def post_conversation_processing(
    db: Session,
    conversation_id: int,
    luna_response: str,
    prev_luna_response: str,
    last_user_message: str,
    tool_succeeded: bool = False,
    task_completed: bool = False,
    user_interrupted_tts: bool = False,
) -> None:
    """Background: extract facts, compute RL reward, update personality."""
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

            if conv.message_count > 0 and conv.message_count % 10 == 0:
                msgs = memory.get_recent_conversation(conversation_id, 20)
                conv_text = format_conversation_for_extraction(msgs)
                summary = await summarize_conversation(conv_text)
                if summary:
                    conv.summary = summary
                    db.commit()
                    await memory.store_conversation_summary(summary, conversation_id)

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

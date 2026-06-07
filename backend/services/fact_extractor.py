"""
Extracts facts, calendar events, and tasks about the user from conversations.
Runs after every N messages (interval) and on-demand when correction signals detected.
"""
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from backend.services.llm import ollama
from backend.services.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

_RLHF_PATH = Path(__file__).parent.parent.parent / "data" / "rlhf_pairs.json"

# Signals that the user is stating new/corrected personal info mid-conversation
_EXTRACTION_TRIGGER_RE = re.compile(
    r'\b(i\'m|i am|my name is|i like|i prefer|i hate|i don\'t like|i love|'
    r'i work|i study|i live|i have a|i\'ve been|i switched|i changed|'
    r'i stopped|i started|i quit|i gave up|actually|no,?\s+i|wait,?\s+i|'
    r'i meant|correction|i said|i\'m actually|i am actually)\b',
    re.IGNORECASE,
)


def _should_trigger_extraction(message: str) -> bool:
    """Return True when the message likely contains new/corrected personal info."""
    return (
        len(message.split()) > 4
        and bool(_EXTRACTION_TRIGGER_RE.search(message))
    )


def _build_extraction_examples(n: int = 20) -> str:
    """Sample a balanced mix of extraction RLHF pairs as few-shot examples."""
    import random
    try:
        pairs = json.loads(_RLHF_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Could not load RLHF examples: %s", e)
        return ""
    extraction = [p for p in pairs if p.get("mode") == "extraction"]
    if not extraction:
        return ""

    noise  = [p for p in extraction if p.get("chosen", "[]").strip() in ("[]", "[ ]", "")]
    signal = [p for p in extraction if p.get("chosen", "[]").strip() not in ("[]", "[ ]", "")]

    n_noise  = max(1, int(n * 0.6))
    n_signal = max(1, n - n_noise)
    selected = (
        random.sample(noise,  min(n_noise,  len(noise)))  +
        random.sample(signal, min(n_signal, len(signal)))
    )
    random.shuffle(selected)

    lines = ["\n--- FEW-SHOT EXAMPLES ---"]
    for p in selected:
        lines.append(f"\nConversation:\n{p['conversation']}\nOutput: {p['chosen']}")
        if p.get("note"):
            lines.append(f"# {p['note']}")
    lines.append("\n--- END EXAMPLES ---")
    return "\n".join(lines)


EXTRACTION_SYSTEM = """You extract factual information about the USER from conversations.
Return ONLY a JSON array of objects. No explanation, no markdown, just the JSON.

Fact categories:
- personal: name, age, location, job, education, nationality
- preference: likes, dislikes, hobbies, habits, favorites
- relationship: family members, friends, partner, pets
- event: past events, experiences, milestones
- goal: aspirations, current projects, plans
- health: fitness, diet, medical (only if clearly stated)

Memory type — classify by how long the fact remains relevant:
- "persistent": active task or project currently being worked on — e.g. building an app, studying for exams.
- "short": relevant for weeks or a month — a show they are watching, an upcoming trip, a temporary phase.
- "long": stable indefinitely — name, job, preferences, hobbies, relationships, recurring habits.

Rules:
- Only extract clearly stated facts, not inferences
- Each fact should be a complete, standalone sentence about the user
- Omit anything vague or uncertain
- Return [] if nothing new was learned
- Max 8 fact items per extraction

NEVER extract:
- One-time UI actions (user asked to open/close map, pull up something, play a song)
- Transient physical states (eating X right now, currently drinking Y, felt tired tonight)
- Momentary moods or one-night states (bored, can't sleep, up late tonight)
- Specific dated to-dos unless they reveal a recurring habit
- Location unless it is the user's established home/city/country
- Anything Luna did — only extract facts about the USER
- Vague project references without substance ("working on a project")

For "persistent" and "short" facts, include "expires_in_days": <number>.
For "long" facts, omit expires_in_days.

Fact format: {"category": "personal", "content": "User's name is Alex", "confidence": 0.95, "memory_type": "long"}

--- CALENDAR & TASK ACTIONS ---
If the user mentions a SPECIFIC upcoming appointment or meeting with an explicit date AND time,
include one action item in the array:
{"action": "create_event", "title": "<short title>", "datetime": "<YYYY-MM-DDTHH:MM:00>", "duration_minutes": 60}

If a task or to-do with a SPECIFIC deadline is mentioned, include:
{"action": "create_task", "title": "<short title>", "due": "<YYYY-MM-DDTHH:MM:00>", "priority": "medium"}

ONLY create event/task actions when a specific date+time is clearly stated.
NEVER create them for vague mentions like "later", "soon", "sometime this week".
Today's date is provided in the prompt — use it to resolve "tomorrow", "this Friday", etc.

{_extraction_examples}"""

SUMMARIZE_SYSTEM = """Summarize this conversation between Luna and the user in 2-3 sentences.
Focus on: what the user shared, what was decided or discussed, any emotional moments.
Write in third person. Be concise and factual."""

EMOTIONAL_ARC_SYSTEM = """In one sentence, describe the user's emotional state and primary focus from this conversation.
Format: "User felt [emotion] about [topic/situation]."
If emotionally neutral or purely task-based, return an empty string exactly: \"\""""

USER_NAME_SYSTEM = """Extract the user's name from this conversation if they clearly stated it.
Return ONLY the name as plain text, or "unknown" if no name was given."""


async def extract_facts_from_conversation(
    conversation_text: str,
    db: Session,
    conversation_id: int,
    memory: MemoryManager,
) -> list[dict]:
    from backend.models.database import CalendarEvent, Task
    try:
        system = EXTRACTION_SYSTEM.replace(
            "{_extraction_examples}", _build_extraction_examples()
        )
        today = datetime.now().strftime("%A, %B %d, %Y")
        raw = await ollama.complete(
            prompt=f"Today is {today}. Extract facts from this conversation:\n\n{conversation_text}",
            system=system,
            temperature=0.1,
        )
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group())
        if not isinstance(items, list):
            return []

        stored = []
        events_created = []
        tasks_created = []

        for item in items:
            if not isinstance(item, dict):
                continue

            action = item.get("action")

            # ── Calendar event creation ──────────────────────────────────────
            if action == "create_event":
                try:
                    title = item.get("title", "").strip()
                    dt_str = item.get("datetime", "")
                    duration = int(item.get("duration_minutes") or 60)
                    if not title or not dt_str:
                        continue
                    dt = datetime.fromisoformat(dt_str)
                    if dt <= datetime.now():
                        continue  # skip past events
                    # Deduplicate: skip if same title already exists
                    existing = (
                        db.query(CalendarEvent)
                        .filter(CalendarEvent.title == title)
                        .first()
                    )
                    if not existing:
                        end_dt = dt + timedelta(minutes=duration)
                        db.add(CalendarEvent(
                            title=title,
                            start_datetime=dt,
                            end_datetime=end_dt,
                        ))
                        db.commit()
                        events_created.append(title)
                        stored.append(item)
                except (ValueError, TypeError, KeyError) as e:
                    logger.debug("Skipping invalid calendar event item: %s", e)
                continue

            # ── Task creation ────────────────────────────────────────────────
            if action == "create_task":
                try:
                    title = item.get("title", "").strip()
                    due_str = item.get("due", "")
                    priority = item.get("priority", "medium")
                    if not title:
                        continue
                    due = datetime.fromisoformat(due_str) if due_str else None
                    existing = (
                        db.query(Task)
                        .filter(Task.title == title, Task.completed == False)
                        .first()
                    )
                    if not existing:
                        db.add(Task(title=title, due_date=due, priority=priority))
                        db.commit()
                        tasks_created.append(title)
                        stored.append(item)
                except (ValueError, TypeError, KeyError) as e:
                    logger.debug("Skipping invalid task item: %s", e)
                continue

            # ── Regular fact ─────────────────────────────────────────────────
            content = item.get("content", "").strip()
            category = item.get("category", "personal")
            confidence = float(item.get("confidence", 0.9))
            memory_type = item.get("memory_type", "long")
            if memory_type not in ("short", "long", "persistent"):
                memory_type = "long"
            expires_in_days = item.get("expires_in_days")
            if expires_in_days is not None:
                try:
                    expires_in_days = float(expires_in_days)
                except (TypeError, ValueError):
                    expires_in_days = None
            if len(content) > 10:
                await memory.store_fact(
                    content, category, conversation_id, confidence,
                    memory_type=memory_type,
                    expires_in_days=expires_in_days,
                )
                stored.append(item)

        # Queue proactive notes for auto-created calendar/task items
        if events_created or tasks_created:
            from backend.services.scheduler import proactive_queue
            if events_created:
                for title in events_created:
                    proactive_queue.append(f"Added to your calendar: {title}.")
            if tasks_created:
                for title in tasks_created:
                    proactive_queue.append(f"Added to your tasks: {title}.")

        return stored
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Fact extraction parsing failed: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error in fact extraction: %s", e, exc_info=True)
        return []


async def extract_emotional_arc(conversation_text: str) -> str:
    """Extract the user's emotional state from the conversation. Returns empty if neutral."""
    try:
        result = await ollama.complete(
            prompt=conversation_text,
            system=EMOTIONAL_ARC_SYSTEM,
            temperature=0.1,
        )
        result = result.strip().strip('"')
        if result and len(result) > 8 and "empty" not in result.lower():
            return result
    except (httpx.HTTPError, OSError, ValueError) as e:
        logger.warning("Emotional arc extraction failed: %s", e)
    return ""


async def summarize_conversation(conversation_text: str) -> str:
    try:
        return await ollama.complete(
            prompt=conversation_text,
            system=SUMMARIZE_SYSTEM,
            temperature=0.2,
        )
    except (httpx.HTTPError, OSError, ValueError) as e:
        logger.warning("Conversation summarization failed: %s", e)
        return ""


async def extract_user_name(conversation_text: str) -> Optional[str]:
    try:
        name = await ollama.complete(
            prompt=conversation_text,
            system=USER_NAME_SYSTEM,
            temperature=0.0,
        )
        name = name.strip().strip('"').strip("'")
        if name and name.lower() != "unknown" and len(name) < 50:
            return name
    except (httpx.HTTPError, OSError, ValueError) as e:
        logger.warning("User name extraction failed: %s", e)
    return None


def format_conversation_for_extraction(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        role = "User" if m["role"] == "user" else "Luna"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)

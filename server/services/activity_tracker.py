"""
Activity tracker — understands what the user is currently doing,
tracks progress, and maintains a live "what's happening now" context.
Luna uses this to ask smart follow-ups and tie tasks to ongoing work.
"""
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float
from backend.models.database import Base, SessionLocal
from backend.services.llm import ollama

# How long an activity can run before it's auto-completed (hours).
# Applies when no estimated_duration_minutes is set.
_CATEGORY_MAX_HOURS: dict[str | None, float] = {
    "entertainment": 3,
    "personal":      2,
    "social":        3,
    "health":        2,
    "work":          6,
    "study":         6,
    "creative":      6,
    None:            3,   # default
}

# Marker in Activity.description identifying rows created from real Spotify
# playback state (as opposed to a text-guessed "the user said 'play X'").
SPOTIFY_ACTIVITY_MARKER = "spotify_playback"


class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="in_progress")  # in_progress|done|paused|abandoned
    category = Column(String, nullable=True)  # work|study|personal|creative|health|social
    progress_notes = Column(JSON, default=list)  # list of {note, ts} dicts
    started_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)
    source_conversation_id = Column(Integer, nullable=True)
    confidence = Column(Float, default=0.8)


ACTIVITY_EXTRACT_SYSTEM = """You extract the user's current activity from their message.
Return a JSON object or null if no activity is mentioned.

Detect:
- What they are currently doing or working on
- Whether it's ongoing, just started, or just finished
- Category: work|study|personal|creative|health|social|errands|entertainment

Output format:
{
  "title": "short activity title",
  "description": "more detail if available",
  "status": "in_progress" | "done" | "paused",
  "category": "work",
  "estimated_duration_minutes": null or number
}

Only return the JSON object or null. No other text."""

PROGRESS_CHECK_SYSTEM = """You are checking if the user's message contains an update about an ongoing activity.
Given the current activity context, does the message indicate:
- Progress was made?
- The activity is done?
- The activity is paused or abandoned?
- No update about the activity?

Return JSON: {"update": "progress"|"done"|"paused"|"abandoned"|"none", "note": "brief note about what changed"}"""


class ActivityTracker:
    def __init__(self, db: Session):
        self.db = db

    def get_current_activities(self) -> list[Activity]:
        now = datetime.utcnow()
        candidates = (
            self.db.query(Activity)
            .filter(Activity.status == "in_progress")
            .order_by(Activity.last_updated.desc())
            .limit(20)
            .all()
        )
        live: list[Activity] = []
        for act in candidates:
            elapsed_h = (now - act.started_at).total_seconds() / 3600
            # Activities that started on a previous calendar day are always done.
            if act.started_at.date() < now.date():
                act.status = "done"
                act.completed_at = act.last_updated
                self.db.commit()
                continue
            # Expire based on how long ago it started — last_updated can be bumped
            # by background processing, so always use started_at as ground truth.
            if act.estimated_duration_minutes:
                max_h = act.estimated_duration_minutes / 60 * 2
            else:
                max_h = _CATEGORY_MAX_HOURS.get(act.category, 3)
            if elapsed_h > max_h:
                act.status = "done"
                act.completed_at = now
                self.db.commit()
                continue
            live.append(act)
        return live[:5]

    def get_recent_activities(self, limit: int = 10) -> list[Activity]:
        return (
            self.db.query(Activity)
            .order_by(Activity.last_updated.desc())
            .limit(limit)
            .all()
        )

    async def process_message(self, message: str, conversation_id: int) -> Optional[Activity]:
        """Detect if the user is describing a new activity."""
        try:
            raw = await ollama.complete(
                prompt=f"User said: {message}",
                system=ACTIVITY_EXTRACT_SYSTEM,
                temperature=0.1,
            )
            raw = raw.strip()
            if not raw or raw.lower() == "null":
                return None

            match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            if not data or not data.get("title"):
                return None

            # Check if we already have this activity
            existing = self._find_similar_activity(data["title"])
            if existing:
                await self._update_activity_from_data(existing, data, message)
                return existing

            activity = Activity(
                title=data.get("title", "Activity"),
                description=data.get("description"),
                status=data.get("status", "in_progress"),
                category=data.get("category"),
                estimated_duration_minutes=data.get("estimated_duration_minutes"),
                progress_notes=[{"note": message[:200], "ts": datetime.utcnow().isoformat()}],
                source_conversation_id=conversation_id,
            )
            self.db.add(activity)
            self.db.commit()
            self.db.refresh(activity)
            return activity
        except Exception:
            return None

    async def check_progress(self, message: str, activity: Activity) -> str:
        """Check if a message updates an existing activity."""
        try:
            context = f"Activity: {activity.title}\nUser message: {message}"
            raw = await ollama.complete(
                prompt=context,
                system=PROGRESS_CHECK_SYSTEM,
                temperature=0.1,
            )
            match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if not match:
                return "none"
            data = json.loads(match.group())
            update_type = data.get("update", "none")
            note = data.get("note", "")

            if update_type in ("done", "paused", "abandoned"):
                activity.status = update_type
                if update_type == "done":
                    activity.completed_at = datetime.utcnow()

            if note and update_type != "none":
                # Build a new list object — a plain JSON column won't detect
                # an in-place mutation reassigned to the same list reference.
                notes = list(activity.progress_notes or [])
                notes.append({"note": note, "ts": datetime.utcnow().isoformat()})
                activity.progress_notes = notes

            activity.last_updated = datetime.utcnow()
            self.db.commit()
            return update_type
        except Exception:
            return "none"

    def sync_spotify_activity(self) -> Optional[Activity]:
        """
        Reconcile the tracked 'listening' activity with actual Spotify
        playback state — unlike process_message/check_progress, this doesn't
        guess from chat text, it reads what's really playing right now and
        opens/updates/closes the activity to match.
        """
        from backend.services.spotify import spotify_service

        if not spotify_service.is_connected:
            return None

        current = spotify_service.get_current()
        existing = (
            self.db.query(Activity)
            .filter(
                Activity.status == "in_progress",
                Activity.description == SPOTIFY_ACTIVITY_MARKER,
            )
            .order_by(Activity.last_updated.desc())
            .first()
        )

        if not current or not current.get("is_playing"):
            if existing:
                existing.status = "done"
                existing.completed_at = datetime.utcnow()
                existing.last_updated = datetime.utcnow()
                notes = list(existing.progress_notes or [])
                notes.append({"note": "Playback stopped.", "ts": datetime.utcnow().isoformat()})
                existing.progress_notes = notes
                self.db.commit()
            return None

        title = f"Listening to {current['title']} by {current['artist']}"

        if existing and existing.title == title:
            existing.last_updated = datetime.utcnow()
            self.db.commit()
            return existing

        if existing:
            existing.status = "done"
            existing.completed_at = datetime.utcnow()
            notes = list(existing.progress_notes or [])
            notes.append({"note": "Song changed.", "ts": datetime.utcnow().isoformat()})
            existing.progress_notes = notes

        duration_ms = current.get("duration_ms") or 0
        activity = Activity(
            title=title,
            description=SPOTIFY_ACTIVITY_MARKER,
            status="in_progress",
            category="entertainment",
            estimated_duration_minutes=round(duration_ms / 60000) if duration_ms else None,
            progress_notes=[{
                "note": f"Started playing {current['title']} by {current['artist']}",
                "ts": datetime.utcnow().isoformat(),
            }],
        )
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def _find_similar_activity(self, title: str) -> Optional[Activity]:
        title_lower = title.lower()
        actives = self.get_current_activities()
        for act in actives:
            if title_lower in act.title.lower() or act.title.lower() in title_lower:
                return act
        return None

    async def _update_activity_from_data(self, activity: Activity, data: dict, message: str):
        if data.get("status") in ("done", "paused", "abandoned"):
            activity.status = data["status"]
            if data["status"] == "done":
                activity.completed_at = datetime.utcnow()
        notes = list(activity.progress_notes or [])
        notes.append({"note": message[:200], "ts": datetime.utcnow().isoformat()})
        activity.progress_notes = notes
        activity.last_updated = datetime.utcnow()
        self.db.commit()

    def format_for_prompt(self) -> str:
        actives = self.get_current_activities()
        if not actives:
            return "No ongoing activities."
        now = datetime.utcnow()
        lines = []
        for act in actives:
            elapsed_min = (now - act.started_at).total_seconds() / 60
            mentioned_min = (now - act.last_updated).total_seconds() / 60
            if elapsed_min < 60:
                time_str = f"started ~{int(elapsed_min)}m ago"
            else:
                time_str = f"started ~{elapsed_min/60:.1f}h ago"
            if mentioned_min < elapsed_min - 1:
                # last_updated is meaningfully more recent than started_at
                if mentioned_min < 60:
                    time_str += f", last mentioned ~{int(mentioned_min)}m ago"
                else:
                    time_str += f", last mentioned ~{mentioned_min/60:.1f}h ago"

            end_str = ""
            if act.estimated_duration_minutes:
                remaining = act.estimated_duration_minutes - elapsed_min
                if remaining > 0:
                    end_str = f", ~{int(remaining)}m left"
                else:
                    end_str = ", should be done by now"

            lines.append(
                f"- [{act.category or 'general'}] {act.title} ({time_str}{end_str})"
            )
            if act.progress_notes:
                last = act.progress_notes[-1]
                lines.append(f"  Last note: {last['note'][:100]}")
        return "\n".join(lines)

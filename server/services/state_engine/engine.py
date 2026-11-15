"""StateEngine: rule-based + pattern-learned user state classifier."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.database import StateEvent
from backend.services.state_engine.states import (
    UserState, STATE_POLICIES, _FOCUS_APPS, _WORK_WORDS,
)
from backend.services.state_engine.pc import get_pc_idle_seconds, get_active_app


class StateEngine:
    AWAY_THRESHOLD_MIN = 20
    LOW_VOL_THRESHOLD  = 0.20
    LOW_SPEED_WPM      = 90
    LEARNED_MIN_EVENTS = 3

    def __init__(self):
        self._last_seen: Optional[datetime] = None
        self._current_state: UserState = UserState.NORMAL
        self._state_since: datetime = datetime.now()

    def update(
        self,
        db: Session,
        transcript: str = "",
        emotion: str = "neutral",
        volume: Optional[float] = None,
        speech_speed: Optional[float] = None,
        speech_duration: Optional[float] = None,
    ) -> UserState:
        now = datetime.now()
        idle  = get_pc_idle_seconds()
        app   = get_active_app()
        pc_on = idle < 300

        self._mark_seen(now)
        state = self._classify(now, transcript, emotion, volume, speech_speed, pc_on, app, idle, db)

        if state != self._current_state:
            self._current_state = state
            self._state_since   = now

        self._log(db, now, transcript, emotion, volume, speech_speed, speech_duration,
                  pc_on, app, idle, state)
        return state

    def infer_passive(self, db: Session) -> UserState:
        now   = datetime.now()
        idle  = get_pc_idle_seconds()
        app   = get_active_app()
        pc_on = idle < 300
        state = self._classify(now, "", "neutral", None, None, pc_on, app, idle, db)
        self._current_state = state
        return state

    @property
    def current_state(self) -> UserState:
        return self._current_state

    @property
    def state_since(self) -> datetime:
        return self._state_since

    def get_response_policy(self, state: Optional[UserState] = None) -> dict:
        return STATE_POLICIES.get(state or self._current_state,
                                  STATE_POLICIES[UserState.NORMAL])

    def build_state_context(self, state: Optional[UserState] = None) -> str:
        s = state or self._current_state
        note = STATE_POLICIES.get(s, STATE_POLICIES[UserState.NORMAL]).get("prompt_note", "")
        if not note:
            return ""
        mins = int((datetime.now() - self._state_since).total_seconds() / 60)
        duration = f" (for ~{mins} min)" if mins >= 2 else ""
        return f"## User state: {s.value}{duration}\n{note}\n"

    def common_state_by_hour(self, db: Session, hour: int) -> str:
        row = self._query_learned(db, hour)
        return row[0] if row else "UNKNOWN"

    def pattern_summary(self, db: Session) -> list[dict]:
        try:
            rows = db.execute(text(
                "SELECT hour, day_of_week, inferred_state, COUNT(*) as cnt "
                "FROM state_events "
                "GROUP BY hour, day_of_week, inferred_state "
                f"HAVING cnt >= {self.LEARNED_MIN_EVENTS} "
                "ORDER BY hour, cnt DESC"
            )).fetchall()
            seen: dict[tuple, dict] = {}
            for h, dow, state, cnt in rows:
                k = (h, dow)
                if k not in seen:
                    seen[k] = {"hour": h, "day_of_week": dow,
                               "state": state, "count": cnt}
            return list(seen.values())
        except Exception:
            return []

    def narrative_summary(self, db: Session) -> str:
        patterns = self.pattern_summary(db)
        if not patterns:
            return "No patterns learned yet — keep chatting and Luna will pick up your habits."

        _DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        _STATE_PHRASES = {
            "SLEEPING":       "usually asleep",
            "JUST_WOKE_UP":   "just waking up",
            "AWAY":           "often away",
            "BACK_FROM_WORK": "back from work",
            "FOCUS_MODE":     "in deep-work mode",
            "RELAXING":       "relaxing",
            "STAYING_UP":     "staying up late",
            "LOW_ENERGY":     "low-energy",
            "NORMAL":         "active and chatting",
        }
        lines = []
        for p in patterns:
            h, dow, state = p["hour"], p["day_of_week"], p["state"]
            day  = _DAYS[dow] if 0 <= dow <= 6 else "weekdays"
            phrase = _STATE_PHRASES.get(state, state.lower())
            lines.append(f"  {day} {h:02d}:00 — {phrase} ({p['count']}×)")
        return "Learned habits:\n" + "\n".join(lines)

    def _mark_seen(self, now: datetime):
        self._last_seen = now

    def _classify(
        self,
        now: datetime,
        transcript: str,
        emotion: str,
        volume: Optional[float],
        speech_speed: Optional[float],
        pc_active: bool,
        active_app: str,
        idle_seconds: int,
        db: Session,
    ) -> UserState:
        hour = now.hour
        text_lower = transcript.lower()

        if 1 <= hour < 7 and (not pc_active or idle_seconds > 1800):
            return UserState.SLEEPING

        if 5 <= hour < 10 and pc_active:
            if (self._current_state == UserState.SLEEPING or
                    self._was_last_state(db, UserState.SLEEPING)):
                return UserState.JUST_WOKE_UP

        from backend.config import settings as _cfg
        if _cfg.luna_variant == "personal" and self._last_seen:
            gone_min = (now - self._last_seen).total_seconds() / 60
            if gone_min > self.AWAY_THRESHOLD_MIN and idle_seconds < 3600:
                return UserState.AWAY

        if 16 <= hour < 21 and any(w in text_lower for w in _WORK_WORDS):
            return UserState.BACK_FROM_WORK

        if (hour >= 23 or hour < 2) and pc_active:
            return UserState.STAYING_UP

        if emotion in ("sad", "angry"):
            return UserState.LOW_ENERGY
        if (speech_speed is not None and speech_speed < self.LOW_SPEED_WPM and
                volume is not None and volume < 0.30):
            return UserState.LOW_ENERGY

        if active_app in _FOCUS_APPS:
            return UserState.FOCUS_MODE

        if hour >= 20 and volume is not None and volume < self.LOW_VOL_THRESHOLD and pc_active:
            return UserState.FOCUS_MODE

        if 20 <= hour < 23 and active_app not in _FOCUS_APPS:
            return UserState.RELAXING

        row = self._query_learned(db, hour)
        if row:
            try:
                return UserState(row[0])
            except ValueError:
                pass

        return UserState.NORMAL

    def _was_last_state(self, db: Session, target: UserState) -> bool:
        try:
            last = (db.query(StateEvent)
                    .order_by(StateEvent.timestamp.desc())
                    .first())
            return last is not None and last.inferred_state == target.value
        except Exception:
            return False

    def _query_learned(self, db: Session, hour: int):
        try:
            return db.execute(text(
                "SELECT inferred_state, COUNT(*) as cnt FROM state_events "
                "WHERE hour = :h GROUP BY inferred_state ORDER BY cnt DESC LIMIT 1"
            ), {"h": hour}).fetchone()
        except Exception:
            return None

    def _log(
        self, db: Session, now: datetime,
        transcript: str, emotion: str,
        volume: Optional[float], speech_speed: Optional[float],
        speech_duration: Optional[float],
        pc_active: bool, active_app: str, idle_seconds: int,
        state: UserState,
    ):
        try:
            db.add(StateEvent(
                timestamp       = now,
                hour            = now.hour,
                day_of_week     = now.weekday(),
                transcript      = transcript[:500] if transcript else None,
                emotion         = emotion or None,
                volume          = round(volume, 4) if volume is not None else None,
                speech_speed    = round(speech_speed, 1) if speech_speed is not None else None,
                speech_duration = round(speech_duration, 2) if speech_duration is not None else None,
                pc_active       = pc_active,
                active_app      = active_app or None,
                idle_seconds    = idle_seconds,
                inferred_state  = state.value,
            ))
            db.commit()
        except Exception:
            db.rollback()


state_engine = StateEngine()

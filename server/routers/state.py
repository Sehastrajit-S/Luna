"""
State engine API endpoints.
Exposes current state, event history, and learned patterns to the frontend.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.models.database import get_db, StateEvent
from backend.services.state_engine import state_engine, STATE_POLICIES, UserState

router = APIRouter(prefix="/api/state", tags=["state"])


@router.get("/current")
def get_current_state(db: Session = Depends(get_db)):
    """Return the current inferred user state and its policy."""
    # Passive inference if user hasn't spoken yet (scheduler / polling use-case)
    state = state_engine.infer_passive(db)
    policy = state_engine.get_response_policy(state)
    return {
        "state":        state.value,
        "since":        state_engine.state_since.isoformat(),
        "tone":         policy.get("tone", ""),
        "behavior":     policy.get("behavior", ""),
        "state_context": state_engine.build_state_context(state),
    }


@router.get("/history")
def get_state_history(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Return raw state events from the last N hours."""
    since = datetime.utcnow() - timedelta(hours=hours)
    events = (
        db.query(StateEvent)
        .filter(StateEvent.timestamp >= since)
        .order_by(StateEvent.timestamp.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id":             e.id,
            "timestamp":      e.timestamp.isoformat(),
            "hour":           e.hour,
            "day_of_week":    e.day_of_week,
            "transcript":     e.transcript,
            "emotion":        e.emotion,
            "volume":         e.volume,
            "speech_speed":   e.speech_speed,
            "speech_duration":e.speech_duration,
            "pc_active":      e.pc_active,
            "active_app":     e.active_app,
            "idle_seconds":   e.idle_seconds,
            "inferred_state": e.inferred_state,
        }
        for e in events
    ]


@router.get("/patterns")
def get_patterns(db: Session = Depends(get_db)):
    """Return learned patterns (dominant state per hour/day)."""
    return {
        "patterns":  state_engine.pattern_summary(db),
        "narrative": state_engine.narrative_summary(db),
    }


@router.get("/policies")
def get_all_policies():
    """Return the response policy for every state."""
    return {
        state.value: {
            "tone":     p.get("tone", ""),
            "behavior": p.get("behavior", ""),
        }
        for state, p in STATE_POLICIES.items()
    }

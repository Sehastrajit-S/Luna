"""Luna state engine: time-aware user state classification and response policies."""
from backend.services.state_engine.states import (
    UserState,
    STATE_POLICIES,
    _FOCUS_APPS,
    _WORK_WORDS,
)
from backend.services.state_engine.pc import get_pc_idle_seconds, get_active_app
from backend.services.state_engine.engine import StateEngine, state_engine

__all__ = [
    "UserState",
    "STATE_POLICIES",
    "_FOCUS_APPS",
    "_WORK_WORDS",
    "get_pc_idle_seconds",
    "get_active_app",
    "StateEngine",
    "state_engine",
]

# Backward-compat shim — all logic lives in backend.services.scheduler package
from backend.services.scheduler import *  # noqa: F401, F403
from backend.services.scheduler import (
    send_windows_notification,
    proactive_queue,
    check_upcoming_events,
    check_overdue_tasks,
    daily_memory_compaction,
    daily_personality_decay,
    morning_greeting,
    confidence_decay,
    state_aware_proactive,
    companion_check_in,
    _COMMITMENT_RE,
    mine_behavioral_patterns,
    proactive_commitment_followup,
    LunaScheduler,
    luna_scheduler,
)

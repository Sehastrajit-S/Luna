"""Luna proactive scheduler: background jobs, notifications, companion check-ins."""
from server.services.scheduler.notifications import send_windows_notification, proactive_queue
from server.services.scheduler.jobs import (
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
    vision_aware_checkin,
    sync_spotify_activity,
)
from server.services.scheduler.service import LunaScheduler, luna_scheduler

__all__ = [
    "send_windows_notification",
    "proactive_queue",
    "check_upcoming_events",
    "check_overdue_tasks",
    "daily_memory_compaction",
    "daily_personality_decay",
    "morning_greeting",
    "confidence_decay",
    "state_aware_proactive",
    "companion_check_in",
    "_COMMITMENT_RE",
    "mine_behavioral_patterns",
    "proactive_commitment_followup",
    "vision_aware_checkin",
    "sync_spotify_activity",
    "LunaScheduler",
    "luna_scheduler",
]

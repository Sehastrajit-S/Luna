"""
Per-conversation store for pending contradiction notes.
Notes are injected into Luna's system prompt on the next turn
so she can acknowledge memory updates naturally in her response.
"""
from typing import Optional

# conversation_id → list of pending notes
_pending: dict[int, list[str]] = {}

# Fallback bucket for facts stored without a conversation_id
_global: list[str] = []


def add(note: str, conversation_id: Optional[int] = None) -> None:
    if conversation_id:
        _pending.setdefault(conversation_id, []).append(note)
    else:
        _global.append(note)


def pop(conversation_id: int) -> list[str]:
    notes = _pending.pop(conversation_id, [])
    if _global:
        notes = _global[:] + notes
        _global.clear()
    return notes

"""
Scratchpad — shared, ordered, in-memory state for one crew run.

All agents in a crew can read all entries.  Writes are append-only and tagged
with the agent that produced them so the orchestrator/critic can attribute
findings back to specific roles.

The scratchpad is intentionally simple (no persistence, no vector search).
For long-term memory across crews, agents should call MemoryManager.store_fact.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScratchpadEntry:
    """One entry written by an agent during the crew run."""

    agent_role: str
    label: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_role": self.agent_role,
            "label": self.label,
            "content": self.content,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class Scratchpad:
    """Thread-safe append-only log of findings + a small key/value side-store."""

    def __init__(self) -> None:
        self._entries: list[ScratchpadEntry] = []
        self._kv: dict[str, Any] = {}
        self._lock = threading.Lock()

    # ── append-only log ──────────────────────────────────────────────────────

    def write(self, agent_role: str, label: str, content: str, **metadata: Any) -> ScratchpadEntry:
        entry = ScratchpadEntry(
            agent_role=agent_role,
            label=label,
            content=content,
            metadata=dict(metadata),
        )
        with self._lock:
            self._entries.append(entry)
        return entry

    def entries(self) -> list[ScratchpadEntry]:
        with self._lock:
            return list(self._entries)

    def by_role(self, role: str) -> list[ScratchpadEntry]:
        with self._lock:
            return [e for e in self._entries if e.agent_role == role]

    # ── small key/value side store ──────────────────────────────────────────
    # Useful when one agent needs to share a structured object with another
    # (a parsed plan, a list of URLs, etc.).

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._kv[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._kv.get(key, default)

    # ── Rendered context for inclusion in agent prompts ─────────────────────

    def render(self, max_chars: int = 4000) -> str:
        """
        Produce a compact text rendering of the scratchpad for inclusion in
        downstream agent prompts. Newest entries kept, oldest dropped if needed.
        """
        with self._lock:
            entries = list(self._entries)
        if not entries:
            return "(scratchpad is empty)"

        lines = []
        for e in entries:
            block = f"[{e.agent_role}::{e.label}] {e.content}"
            lines.append(block)

        rendered = "\n\n".join(lines)
        if len(rendered) <= max_chars:
            return rendered

        # Truncate from the front, keep most recent entries
        truncated = []
        running_size = 0
        for block in reversed(lines):
            running_size += len(block) + 2
            if running_size > max_chars:
                break
            truncated.append(block)
        return "(earlier entries truncated)\n\n" + "\n\n".join(reversed(truncated))

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entries": [e.to_dict() for e in self._entries],
                "kv": dict(self._kv),
            }

"""
CrewEvent — typed events emitted during a multi-agent crew run.

Consumers (UI, SSE streams, loggers) react to these events to render
agent status, scratchpad updates, and final outputs in real time.

Event lifecycle for a typical run:
  CREW_START          → user task accepted, decomposition starting
  PLAN_READY          → list of subtasks per role finalized
  AGENT_START         → an agent begins working on a subtask
  AGENT_TOKEN         → a streamed token of an agent's response
  AGENT_TOOL_CALL     → an agent invoked a tool (web_search, etc.)
  AGENT_RESULT        → agent finished its subtask (full text)
  SCRATCHPAD_WRITE    → a note was added to the shared scratchpad
  CRITIC_REVIEW       → critic agent provided feedback
  REVISION_REQUEST    → orchestrator asked an agent to revise
  CREW_DONE           → final synthesized answer ready
  ERROR               — fatal error, crew aborted
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CrewEventType(str, Enum):
    CREW_START = "crew_start"
    PLAN_READY = "plan_ready"
    AGENT_START = "agent_start"
    AGENT_TOKEN = "agent_token"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_RESULT = "agent_result"
    SCRATCHPAD_WRITE = "scratchpad_write"
    CRITIC_REVIEW = "critic_review"
    REVISION_REQUEST = "revision_request"
    CREW_DONE = "crew_done"
    ERROR = "error"


@dataclass
class CrewEvent:
    """One event from a crew run.  Always serializable to JSON."""

    type: CrewEventType
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type.value, **self.payload}

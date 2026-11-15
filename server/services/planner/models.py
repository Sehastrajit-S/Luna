"""Planner data model: enums and dataclasses."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class StepStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    SKIPPED  = "skipped"


class PlanStatus(str, Enum):
    PLANNING  = "planning"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    CRITIQUED = "critiqued"


@dataclass
class Step:
    id: str
    action: str                            # tool | llm | wait | branch
    description: str
    tool_name: str        = ""
    tool_args: dict       = field(default_factory=dict)
    llm_prompt: str       = ""             # for action=llm; supports {stepId.result}
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus    = StepStatus.PENDING
    result: Any           = None
    error: str            = ""
    retries: int          = 0
    max_retries: int      = 2
    started_at: float     = 0.0
    ended_at: float       = 0.0

    @property
    def latency_ms(self) -> float:
        if self.started_at and self.ended_at:
            return max(0.0, (self.ended_at - self.started_at) * 1000)
        return 0.0


@dataclass
class CritiqueResult:
    verdict: str                           # success | partial | failure
    reasoning: str
    score: float               = 0.0       # 0–1
    retry_step_ids: list[str]  = field(default_factory=list)


@dataclass
class Plan:
    id: str                            = field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: str                          = ""
    conversation_id: Optional[int]     = None
    steps: list[Step]                  = field(default_factory=list)
    status: PlanStatus                 = PlanStatus.PLANNING
    critique: Optional[CritiqueResult] = None
    created_at: float                  = field(default_factory=time.monotonic)
    completed_at: Optional[float]      = None

    def step_by_id(self, sid: str) -> Optional[Step]:
        return next((s for s in self.steps if s.id == sid), None)

    def ready_steps(self) -> list[Step]:
        done = {s.id for s in self.steps if s.status == StepStatus.DONE}
        return [
            s for s in self.steps
            if s.status == StepStatus.PENDING
            and all(dep in done for dep in s.depends_on)
        ]

    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.DONE, StepStatus.FAILED, StepStatus.SKIPPED)
            for s in self.steps
        )

    def summary(self) -> dict:
        return {
            "id":     self.id,
            "goal":   self.goal,
            "status": self.status.value,
            "steps":  [
                {"id": s.id, "description": s.description,
                 "status": s.status.value, "latency_ms": round(s.latency_ms)}
                for s in self.steps
            ],
            "critique": asdict(self.critique) if self.critique else None,
        }

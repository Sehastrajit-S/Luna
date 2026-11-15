"""PlannerService: create, execute, critique, recover plans."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from typing import Any, AsyncGenerator, Callable, Coroutine, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.planner.models import (
    CritiqueResult,
    Plan,
    PlanStatus,
    Step,
    StepStatus,
)
from backend.services.planner.prompts import _CRITIC_SCHEMA, _PLAN_SCHEMA

ToolExecutorT = Callable[[str, dict], Coroutine[Any, Any, str]]
LLMCompleteT  = Callable[[list[dict], float], Coroutine[Any, Any, str]]


class PlannerService:
    """
    Stateful planner that holds active plans in memory and persists
    completed plans to the plan_records table.

    llm_complete: async (messages: list[dict], temperature: float) -> str
    tool_executor: async (tool_name: str, args: dict) -> str
    """

    def __init__(self, llm_complete: LLMCompleteT, tool_executor: ToolExecutorT) -> None:
        self._llm  = llm_complete
        self._exec = tool_executor
        self._active: dict[str, Plan] = {}

    async def create_plan(
        self,
        goal: str,
        context: str = "",
        conversation_id: Optional[int] = None,
        max_steps: int = 8,
    ) -> Plan:
        prompt = (
            f"You are a planning agent. Decompose the following goal into a "
            f"dependency-aware step DAG (max {max_steps} steps).\n\n"
            f"GOAL: {goal}\n\n"
            f"CONTEXT:\n{context[:800]}\n\n"
            f"Output ONLY valid JSON matching this schema:\n{_PLAN_SCHEMA}\n\n"
            f"Rules:\n"
            f"- Use 'tool' for tool_registry actions, 'llm' for synthesis.\n"
            f"- depends_on must only reference earlier step IDs.\n"
            f"- Use {{stepId.result}} placeholders in llm_prompt.\n"
            f"- Prefer parallelism: steps that don't depend on each other should have empty depends_on.\n"
        )
        try:
            raw   = await self._llm([{"role": "user", "content": prompt}], 0.15)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            data  = json.loads(raw[start:end])
            steps = [
                Step(
                    id          = s.get("id", f"s{i+1}"),
                    action      = s.get("action", "llm"),
                    description = s.get("description", ""),
                    tool_name   = s.get("tool_name", ""),
                    tool_args   = s.get("tool_args", {}),
                    llm_prompt  = s.get("llm_prompt", ""),
                    depends_on  = s.get("depends_on", []),
                )
                for i, s in enumerate(data.get("steps", []))
            ]
            plan = Plan(goal=data.get("goal", goal), steps=steps, conversation_id=conversation_id)
        except Exception:
            plan = Plan(
                goal=goal,
                steps=[Step(id="s1", action="llm", description="Direct response", llm_prompt=goal)],
                conversation_id=conversation_id,
            )

        self._active[plan.id] = plan
        return plan

    async def execute(self, plan: Plan, db: Optional[Session] = None) -> AsyncGenerator[dict, None]:
        plan.status = PlanStatus.RUNNING
        results: dict[str, Any] = {}

        while not plan.is_complete():
            ready = plan.ready_steps()
            if not ready:
                for s in plan.steps:
                    if s.status == StepStatus.PENDING:
                        s.status = StepStatus.SKIPPED
                break

            tasks    = [self._run_step(s, results) for s in ready]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

            for step, outcome in zip(ready, outcomes):
                if isinstance(outcome, Exception):
                    step.status = StepStatus.FAILED
                    step.error  = str(outcome)[:300]
                    yield {"type": "step_failed", "step": step.id, "error": step.error}
                else:
                    results[step.id] = outcome
                    step.result = outcome
                    step.status = StepStatus.DONE
                    yield {
                        "type":   "step_done",
                        "step":   step.id,
                        "result": str(outcome)[:300],
                        "ms":     round(step.latency_ms),
                    }

        plan.completed_at = time.monotonic()
        failed = [s for s in plan.steps if s.status == StepStatus.FAILED]
        plan.status = PlanStatus.FAILED if failed else PlanStatus.DONE

        yield {"type": "plan_complete", "plan_id": plan.id, "status": plan.status.value}

        if db is not None:
            self._persist(plan, db)

    async def _run_step(self, step: Step, results: dict[str, Any]) -> Any:
        step.status     = StepStatus.RUNNING
        step.started_at = time.monotonic()
        last_exc: Optional[Exception] = None

        for attempt in range(step.max_retries + 1):
            try:
                if step.action == "tool":
                    result = await self._exec(step.tool_name, step.tool_args)
                elif step.action == "llm":
                    prompt = self._interpolate(step.llm_prompt, results)
                    result = await self._llm([{"role": "user", "content": prompt}], 0.3)
                elif step.action == "wait":
                    delay = float(step.tool_args.get("seconds", 1))
                    await asyncio.sleep(min(delay, 60))
                    result = f"waited {delay}s"
                else:
                    result = f"[unknown action: {step.action}]"

                step.ended_at = time.monotonic()
                return result

            except Exception as exc:
                last_exc = exc
                step.retries += 1
                if attempt < step.max_retries:
                    await asyncio.sleep(2 ** attempt)

        step.ended_at = time.monotonic()
        raise last_exc or RuntimeError(f"step {step.id} failed")

    @staticmethod
    def _interpolate(template: str, results: dict[str, Any]) -> str:
        for sid, res in results.items():
            template = template.replace(f"{{{sid}.result}}", str(res)[:600])
        return template

    async def critique(self, plan: Plan) -> CritiqueResult:
        step_lines = "\n".join(
            f"  [{s.id}] {s.description}: {s.status.value} "
            f"— {str(s.result or s.error)[:150]}"
            for s in plan.steps
        )
        prompt = (
            f"You are a critic agent evaluating plan execution.\n\n"
            f"GOAL: {plan.goal}\n\n"
            f"STEP RESULTS:\n{step_lines}\n\n"
            f"Output ONLY valid JSON:\n{_CRITIC_SCHEMA}"
        )
        try:
            raw   = await self._llm([{"role": "user", "content": prompt}], 0.1)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            data  = json.loads(raw[start:end])
            result = CritiqueResult(
                verdict        = data.get("verdict", "failure"),
                reasoning      = data.get("reasoning", ""),
                score          = float(data.get("score", 0.0)),
                retry_step_ids = data.get("retry_step_ids", []),
            )
        except Exception:
            result = CritiqueResult(verdict="failure", reasoning="Critique unavailable.")

        plan.critique = result
        plan.status   = PlanStatus.CRITIQUED
        return result

    async def recover(self, plan: Plan, failed_step_id: str) -> Optional[Step]:
        step = plan.step_by_id(failed_step_id)
        if step is None:
            return None

        prompt = (
            f"A planning step failed. Suggest a corrected replacement.\n\n"
            f"GOAL: {plan.goal}\n"
            f"FAILED STEP:\n{json.dumps(asdict(step), default=str)}\n\n"
            f"Output a JSON object for the replacement step with the same 'id': {failed_step_id}"
        )
        try:
            raw   = await self._llm([{"role": "user", "content": prompt}], 0.3)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            data  = json.loads(raw[start:end])
            step.tool_name  = data.get("tool_name",  step.tool_name)
            step.tool_args  = data.get("tool_args",  step.tool_args)
            step.llm_prompt = data.get("llm_prompt", step.llm_prompt)
            step.status     = StepStatus.PENDING
            step.retries    = 0
            step.error      = ""
            return step
        except Exception:
            return None

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self._active.get(plan_id)

    def list_plans(self, limit: int = 20) -> list[dict]:
        plans = sorted(self._active.values(), key=lambda p: p.created_at, reverse=True)
        return [p.summary() for p in plans[:limit]]

    def _persist(self, plan: Plan, db: Session) -> None:
        try:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO plan_records "
                    "(plan_id, goal, conversation_id, status, steps_json, "
                    " critique_json, created_at, completed_at) "
                    "VALUES (:pid, :goal, :cid, :status, :steps, :critique, :created, :completed)"
                ),
                {
                    "pid":       plan.id,
                    "goal":      plan.goal,
                    "cid":       plan.conversation_id,
                    "status":    plan.status.value,
                    "steps":     json.dumps([asdict(s) for s in plan.steps], default=str),
                    "critique":  json.dumps(asdict(plan.critique), default=str) if plan.critique else None,
                    "created":   plan.created_at,
                    "completed": plan.completed_at,
                },
            )
            db.commit()
        except Exception:
            pass

    def load_plan_record(self, plan_id: str, db: Session) -> Optional[dict]:
        row = db.execute(
            text(
                "SELECT plan_id, goal, status, steps_json, critique_json, created_at, completed_at "
                "FROM plan_records WHERE plan_id = :pid"
            ),
            {"pid": plan_id},
        ).fetchone()
        if not row:
            return None
        return {
            "plan_id":      row[0],
            "goal":         row[1],
            "status":       row[2],
            "steps":        json.loads(row[3] or "[]"),
            "critique":     json.loads(row[4]) if row[4] else None,
            "created_at":   row[5],
            "completed_at": row[6],
        }

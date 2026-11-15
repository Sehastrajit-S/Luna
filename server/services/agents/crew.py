"""
Crew — orchestrator that runs multiple RoleAgents to complete one user task.

Lifecycle of a Crew run:
  1. Decompose:  the Planner agent produces a JSON plan of subtasks + roles
  2. Execute:    subtasks are run respecting their dependency graph; siblings
                 (no shared dependencies) run in PARALLEL via asyncio.gather
  3. Critique:   the Critic reviews the synthesized output and may request a
                 single revision pass
  4. Finalize:   the Writer composes the final answer from scratchpad findings

All events stream via an async generator.  Callers decide how to render them
(SSE for the chat UI, plain JSON for the /api/agents/crew endpoint, etc.).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

from backend.services.llm import ollama
from backend.services.agents.events import CrewEvent, CrewEventType
from backend.services.agents.roles import (
    AgentRole,
    ROLE_DEFINITIONS,
    RoleAgent,
)
from backend.services.agents.scratchpad import Scratchpad

logger = logging.getLogger(__name__)

_MAX_SUBTASKS = 6
_MAX_PARALLEL = 3   # cap on concurrent agents to avoid spamming the LLM endpoint


@dataclass
class Subtask:
    """One unit of work assigned to an agent."""

    index: int
    role: AgentRole
    task: str
    depends_on: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "role": self.role.value,
            "task": self.task,
            "depends_on": list(self.depends_on),
        }


# ── Public entry point ───────────────────────────────────────────────────────


async def run_crew(
    user_task: str,
    *,
    enable_critic: bool = True,
    max_revisions: int = 1,
) -> AsyncGenerator[CrewEvent, None]:
    """
    Top-level helper. Construct a Crew and stream its events.

    Args:
        user_task: the high-level user request
        enable_critic: if True, run a Critic pass after synthesis
        max_revisions: maximum number of revision rounds the critic can trigger

    Yields:
        CrewEvent stream
    """
    crew = Crew(user_task, enable_critic=enable_critic, max_revisions=max_revisions)
    async for ev in crew.run():
        yield ev


# ── Crew class ───────────────────────────────────────────────────────────────


class Crew:
    """A single multi-agent run for one user task."""

    def __init__(
        self,
        user_task: str,
        *,
        enable_critic: bool = True,
        max_revisions: int = 1,
    ):
        self.user_task = user_task.strip()
        self.scratchpad = Scratchpad()
        self.enable_critic = enable_critic
        self.max_revisions = max(0, int(max_revisions))
        self.subtasks: list[Subtask] = []

    async def run(self) -> AsyncGenerator[CrewEvent, None]:
        """Drive the crew through decompose → execute → critique → finalize."""
        yield CrewEvent(CrewEventType.CREW_START, {"task": self.user_task})

        # ── 1. Decompose ────────────────────────────────────────────────────
        try:
            self.subtasks = await self._decompose()
        except Exception as e:
            logger.error("Crew decomposition failed: %s", e, exc_info=True)
            yield CrewEvent(CrewEventType.ERROR, {"stage": "decompose", "message": str(e)})
            return

        if not self.subtasks:
            yield CrewEvent(
                CrewEventType.ERROR,
                {"stage": "decompose", "message": "Planner produced no subtasks"},
            )
            return

        yield CrewEvent(
            CrewEventType.PLAN_READY,
            {"subtasks": [s.to_dict() for s in self.subtasks]},
        )

        # ── 2. Execute (with parallelism where dependencies allow) ──────────
        async for ev in self._execute_subtasks():
            yield ev

        # ── 3. Synthesize the final answer ──────────────────────────────────
        async for ev in self._synthesize(label="draft"):
            yield ev

        # ── 4. Critic loop ──────────────────────────────────────────────────
        if self.enable_critic and self.max_revisions > 0:
            for round_n in range(self.max_revisions):
                verdict, reason = await self._critic_review()
                yield CrewEvent(
                    CrewEventType.CRITIC_REVIEW,
                    {"verdict": verdict, "reason": reason, "round": round_n + 1},
                )
                if verdict == "approved":
                    break
                # Revise: ask the writer to redo, with the critic's note in context
                yield CrewEvent(
                    CrewEventType.REVISION_REQUEST,
                    {"reason": reason, "round": round_n + 1},
                )
                self.scratchpad.write(
                    AgentRole.CRITIC.value, "feedback",
                    f"Revise the draft because: {reason}",
                )
                async for ev in self._synthesize(label=f"revision_{round_n + 1}"):
                    yield ev

        # ── 5. Done ─────────────────────────────────────────────────────────
        final_answer = self._latest_synthesis()
        yield CrewEvent(
            CrewEventType.CREW_DONE,
            {"answer": final_answer, "scratchpad": self.scratchpad.to_dict()},
        )

    # ── Stage 1: decomposition ──────────────────────────────────────────────

    async def _decompose(self) -> list[Subtask]:
        planner = RoleAgent(AgentRole.PLANNER, self.scratchpad)
        full_response = ""
        async for ev in planner.run(self.user_task, label="plan"):
            if ev.type == CrewEventType.AGENT_TOKEN:
                full_response += ev.payload.get("content", "")
            elif ev.type == CrewEventType.AGENT_RESULT:
                full_response = ev.payload.get("result", full_response)

        return _parse_plan(full_response)

    # ── Stage 2: execute subtasks (with dependency-aware parallelism) ──────

    async def _execute_subtasks(self) -> AsyncGenerator[CrewEvent, None]:
        completed: set[int] = set()
        sem = asyncio.Semaphore(_MAX_PARALLEL)

        async def run_one(sub: Subtask, queue: asyncio.Queue):
            async with sem:
                agent = RoleAgent(sub.role, self.scratchpad)
                label = f"subtask_{sub.index}"
                try:
                    async for ev in agent.run(sub.task, label=label):
                        await queue.put(ev)
                except Exception as e:
                    logger.error("Subtask %d (%s) failed: %s", sub.index, sub.role.value, e, exc_info=True)
                    await queue.put(CrewEvent(
                        CrewEventType.ERROR,
                        {"role": sub.role.value, "subtask": sub.index, "message": str(e)},
                    ))
                finally:
                    await queue.put(("__done__", sub.index))

        # Run waves of subtasks whose dependencies are already met
        remaining = list(self.subtasks)
        queue: asyncio.Queue = asyncio.Queue()

        while remaining:
            ready = [s for s in remaining if all(d in completed for d in s.depends_on)]
            if not ready:
                # Cycle or invalid plan. Run the rest sequentially as fallback.
                ready = remaining[:1]

            tasks = [asyncio.create_task(run_one(s, queue)) for s in ready]

            pending = {s.index for s in ready}
            while pending:
                ev = await queue.get()
                if isinstance(ev, tuple) and ev and ev[0] == "__done__":
                    pending.discard(ev[1])
                    completed.add(ev[1])
                    continue
                yield ev

            # Wait for all ready tasks to fully finish
            await asyncio.gather(*tasks, return_exceptions=True)

            remaining = [s for s in remaining if s.index not in completed]

    # ── Stage 3: synthesize draft via Writer ────────────────────────────────

    async def _synthesize(self, *, label: str) -> AsyncGenerator[CrewEvent, None]:
        writer = RoleAgent(AgentRole.WRITER, self.scratchpad)
        prompt = (
            f"Original task: {self.user_task}\n\n"
            "Using ONLY the scratchpad findings above, write the final answer for the user."
        )
        async for ev in writer.run(prompt, label=label):
            yield ev

    # ── Stage 4: critic review ──────────────────────────────────────────────

    async def _critic_review(self) -> tuple[str, str]:
        """
        Returns (verdict, reason) where verdict in {"approved", "revise"}.
        """
        draft = self._latest_synthesis()
        if not draft:
            return "approved", "no draft to review"

        critic = RoleAgent(AgentRole.CRITIC, self.scratchpad)
        full = ""
        prompt = f"Draft to review:\n\n{draft}\n\nIs this acceptable?"
        async for ev in critic.run(prompt, label="review"):
            if ev.type == CrewEventType.AGENT_TOKEN:
                full += ev.payload.get("content", "")
            elif ev.type == CrewEventType.AGENT_RESULT:
                full = ev.payload.get("result", full)

        text = full.strip()
        if re.match(r"^\s*APPROVED\b", text, re.IGNORECASE):
            return "approved", ""
        m = re.match(r"^\s*REVISE:\s*(.+)$", text, re.IGNORECASE | re.DOTALL)
        if m:
            return "revise", m.group(1).strip()
        # Default to approved if format wasn't followed (don't loop forever)
        return "approved", ""

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _latest_synthesis(self) -> str:
        """Return the most recent Writer output from the scratchpad."""
        for entry in reversed(self.scratchpad.entries()):
            if entry.agent_role == AgentRole.WRITER.value:
                return entry.content
        return ""


# ── Plan parsing ─────────────────────────────────────────────────────────────


def _parse_plan(raw: str) -> list[Subtask]:
    """Extract a list of Subtasks from the planner's JSON output."""
    if not raw or not raw.strip():
        return []

    # Try the raw text first; planner is instructed to output ONLY JSON
    candidate = raw.strip()

    # If wrapped in code fences, strip them
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        # Find the first {...} block
        brace = re.search(r"\{.*\}", candidate, re.DOTALL)
        if brace:
            candidate = brace.group(0)

    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Could not parse planner output as JSON: %s", e)
        return []

    raw_subs = data.get("subtasks") if isinstance(data, dict) else None
    if not isinstance(raw_subs, list):
        return []

    subs: list[Subtask] = []
    for i, raw_sub in enumerate(raw_subs[:_MAX_SUBTASKS]):
        if not isinstance(raw_sub, dict):
            continue
        role_str = str(raw_sub.get("role", "")).strip().lower()
        task = str(raw_sub.get("task", "")).strip()
        deps = raw_sub.get("depends_on", []) or []

        if not task:
            continue
        try:
            role = AgentRole(role_str)
        except ValueError:
            logger.debug("Unknown role '%s' in plan, defaulting to RESEARCHER", role_str)
            role = AgentRole.RESEARCHER

        if not isinstance(deps, list):
            deps = []
        depends_on = [int(d) for d in deps if isinstance(d, (int, float)) and 0 <= int(d) < i]

        subs.append(Subtask(index=i, role=role, task=task, depends_on=depends_on))

    return subs

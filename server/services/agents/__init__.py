"""
L.U.N.A. Multi-Agent Orchestration ("Crew Mode").

A crew is a coordinated group of specialized agents that collaborate to
complete a complex task.  Where the existing TaskPlan executes a linear
sequence of LLM calls in sequence, a Crew can:

  - Spawn multiple role-specialized sub-agents (Researcher, Coder, Planner, ...)
  - Run independent subtasks in parallel
  - Share intermediate findings via a memory bus / scratchpad
  - Invoke a Critic to review and trigger revisions
  - Stream progress events to the UI in real time

Public API
──────────
  Crew                — orchestrator with stages: decompose → execute → critique → finalize
  AgentRole           — role enum / role config
  RoleAgent           — async worker with a system prompt + role-specific tool list
  Scratchpad          — shared in-memory store accessible to all agents in a crew
  CrewEvent           — typed event yielded to consumers (UI, SSE, logs)
  is_crew_request     — detector that decides if a user message warrants Crew Mode

Each Crew run is a single async generator yielding CrewEvents.  Callers
(typically the chat pipeline or a /api/agents/crew endpoint) consume events
as they arrive.
"""
from server.services.agents.events import CrewEvent, CrewEventType
from server.services.agents.scratchpad import Scratchpad
from server.services.agents.roles import AgentRole, ROLE_DEFINITIONS, RoleAgent
from server.services.agents.crew import Crew, run_crew
from server.services.agents.detector import is_crew_request

__all__ = [
    "AgentRole",
    "ROLE_DEFINITIONS",
    "RoleAgent",
    "Crew",
    "run_crew",
    "Scratchpad",
    "CrewEvent",
    "CrewEventType",
    "is_crew_request",
]

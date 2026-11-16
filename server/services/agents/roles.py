"""
Agent roles and the per-role async worker.

Each role has:
  - A canonical name (the AgentRole enum)
  - A system prompt that defines its specialty
  - An allow-list of tools it may invoke (defense-in-depth: the orchestrator
    will reject tool calls outside this list)
  - A temperature suited to the role (researchers low, planners moderate, etc.)

To add a new role:
  1. Add an enum value below
  2. Add an entry to ROLE_DEFINITIONS
  3. (Optional) update the orchestrator's decompose() to consider it
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator

from server.services.llm import ollama
from server.services.agents.events import CrewEvent, CrewEventType
from server.services.agents.scratchpad import Scratchpad

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    PLANNER = "planner"
    CODER = "coder"
    WRITER = "writer"
    ANALYST = "analyst"
    CRITIC = "critic"


@dataclass
class RoleDefinition:
    """Static configuration for a role."""

    role: AgentRole
    description: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    temperature: float = 0.4

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "description": self.description,
            "allowed_tools": list(self.allowed_tools),
            "temperature": self.temperature,
        }


# ── Role definitions ─────────────────────────────────────────────────────────

ROLE_DEFINITIONS: dict[AgentRole, RoleDefinition] = {
    AgentRole.RESEARCHER: RoleDefinition(
        role=AgentRole.RESEARCHER,
        description="Gathers facts from the web, datasets, and prior memory. Cites sources.",
        system_prompt=(
            "You are the Researcher in a crew of specialized agents. Your job is to "
            "find accurate, current information and produce a concise digest with "
            "source URLs. Prefer primary sources. Never invent facts. If a fact is "
            "uncertain, label it as such. Output 3-7 bullet points followed by a "
            "list of source URLs.  Keep your output under 300 words."
        ),
        allowed_tools=["web_search", "web_research", "web_fetch", "dataset_search"],
        temperature=0.2,
    ),
    AgentRole.PLANNER: RoleDefinition(
        role=AgentRole.PLANNER,
        description="Decomposes complex tasks into ordered steps and assigns roles.",
        system_prompt=(
            "You are the Planner in a crew of specialized agents. Given a high-level "
            "task, break it into 3-6 concrete subtasks. For each subtask, name the "
            "best role to handle it (Researcher, Coder, Writer, Analyst). Output ONLY "
            "valid JSON in this format:\n"
            "{\"subtasks\": [{\"role\": \"researcher\", \"task\": \"...\", \"depends_on\": []}]}\n"
            "Subtasks with the same depends_on can run in parallel. Use 0-indexed "
            "indices in depends_on referring to earlier subtasks."
        ),
        allowed_tools=[],
        temperature=0.3,
    ),
    AgentRole.CODER: RoleDefinition(
        role=AgentRole.CODER,
        description="Writes, edits, debugs, and explains code.",
        system_prompt=(
            "You are the Coder in a crew of specialized agents. Produce production-"
            "quality code with brief inline comments. Include only the code and a "
            "short explanation — no preamble. Use language hints in code blocks. "
            "If a previous Researcher's notes are in the scratchpad, base your "
            "implementation on the facts there."
        ),
        allowed_tools=["workspace_read", "workspace_write"],
        temperature=0.2,
    ),
    AgentRole.WRITER: RoleDefinition(
        role=AgentRole.WRITER,
        description="Synthesizes findings into a clear, well-structured final answer.",
        system_prompt=(
            "You are the Writer in a crew of specialized agents. Combine all "
            "scratchpad findings into one cohesive, well-structured answer for the "
            "user. Use markdown headings, bullet points, and source citations where "
            "appropriate. Be confident and concise. Do not repeat the user's "
            "question back."
        ),
        allowed_tools=[],
        temperature=0.5,
    ),
    AgentRole.ANALYST: RoleDefinition(
        role=AgentRole.ANALYST,
        description="Performs calculations, comparisons, and structured reasoning.",
        system_prompt=(
            "You are the Analyst in a crew of specialized agents. Your job is to "
            "compute, compare, or reason carefully through structured data. Show "
            "your work with brief headers. State the conclusion at the end."
        ),
        allowed_tools=["dataset_search"],
        temperature=0.2,
    ),
    AgentRole.CRITIC: RoleDefinition(
        role=AgentRole.CRITIC,
        description="Reviews other agents' outputs and proposes revisions if needed.",
        system_prompt=(
            "You are the Critic in a crew of specialized agents. Review the "
            "draft below from another agent. Be brief and constructive. If the "
            "draft is acceptable, reply with exactly:  APPROVED\n"
            "Otherwise, reply with:  REVISE: <one-sentence reason>"
        ),
        allowed_tools=[],
        temperature=0.1,
    ),
}


# ── Per-role async worker ────────────────────────────────────────────────────


class RoleAgent:
    """
    A single agent embodying a role for the duration of one subtask.

    Use:
        agent = RoleAgent(AgentRole.RESEARCHER, scratchpad)
        async for event in agent.run("Find recent papers on retrieval augmented generation"):
            ...
    """

    def __init__(self, role: AgentRole, scratchpad: Scratchpad):
        if role not in ROLE_DEFINITIONS:
            raise ValueError(f"Unknown role: {role}")
        self.role = role
        self.definition = ROLE_DEFINITIONS[role]
        self.scratchpad = scratchpad

    async def run(self, task: str, *, label: str = "result") -> AsyncGenerator[CrewEvent, None]:
        """
        Execute one subtask. Yields CrewEvents (tokens, tool calls, final result).
        On completion, the result is appended to the scratchpad.
        """
        yield CrewEvent(
            CrewEventType.AGENT_START,
            {"role": self.role.value, "task": task},
        )

        # Build the per-role messages with scratchpad context
        scratch = self.scratchpad.render(max_chars=2000)
        user_content = (
            f"Task: {task}\n\n"
            f"Shared scratchpad:\n{scratch}"
        )

        full_response = ""
        try:
            async for token in ollama.stream_chat(
                [{"role": "user", "content": user_content}],
                self.definition.system_prompt,
                temperature=self.definition.temperature,
            ):
                full_response += token
                yield CrewEvent(
                    CrewEventType.AGENT_TOKEN,
                    {"role": self.role.value, "content": token},
                )
        except Exception as e:
            logger.error("Agent %s failed during streaming: %s", self.role.value, e, exc_info=True)
            yield CrewEvent(
                CrewEventType.ERROR,
                {"role": self.role.value, "message": str(e)},
            )
            return

        # Strip <think> tags from reasoning models
        cleaned = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL).strip()

        # Persist to scratchpad
        entry = self.scratchpad.write(self.role.value, label, cleaned, task=task)
        yield CrewEvent(
            CrewEventType.SCRATCHPAD_WRITE,
            {"entry": entry.to_dict()},
        )

        yield CrewEvent(
            CrewEventType.AGENT_RESULT,
            {"role": self.role.value, "task": task, "result": cleaned},
        )

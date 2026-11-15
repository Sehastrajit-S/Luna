"""
Luna task planner.
Detects complex multi-step tasks and executes them in a plan → execute → observe loop.
"""
import re
from typing import AsyncGenerator
from backend.services.llm import ollama


# Keywords that suggest a multi-step task needing a plan
_PLAN_TRIGGERS = [
    r"\b(set up|setup|configure|install)\b",
    r"\b(step by step|step-by-step)\b",
    r"\b(and then|after that|followed by|first.*then|once.*then)\b",
    r"\b(plan|organize|arrange|coordinate|schedule)\b.{5,50}\b(and|then|also)\b",
    r"\b(multiple|several|all of|each)\b.{5,50}\b(task|step|thing|file|app)\b",
    r"\b(research|find|compare|summarize).{5,50}\b(and|then)\b.{5,50}(write|send|create)\b",
]

_PLAN_MIN_WORDS = 8  # single short messages are never complex plans


def is_complex_task(message: str) -> bool:
    """Return True if the message looks like a multi-step complex request."""
    words = message.split()
    if len(words) < _PLAN_MIN_WORDS:
        return False
    lower = message.lower()
    return any(re.search(p, lower) for p in _PLAN_TRIGGERS)


async def generate_plan(task_description: str) -> list[str]:
    """Ask the LLM to break the task into numbered steps. Returns step strings."""
    prompt = (
        "You are a planning assistant. "
        "Break the following task into numbered steps (max 6). "
        "Write only the steps, one per line, no preamble, no extra text.\n\n"
        f"Task: {task_description}"
    )
    messages = [{"role": "user", "content": prompt}]
    system = (
        "Output ONLY a numbered list. Example:\n"
        "1. Open the browser\n"
        "2. Search for X\n"
        "3. Copy the result"
    )
    full = ""
    async for token in ollama.stream_chat(messages, system):
        full += token

    steps = []
    for line in full.strip().splitlines():
        line = line.strip()
        m = re.match(r"^\d+[\.\)]\s*(.+)$", line)
        if m:
            steps.append(m.group(1).strip())
    return steps


class TaskPlan:
    """Tracks a running plan with current step and results."""

    def __init__(self, description: str, steps: list[str]):
        self.description = description
        self.steps = steps
        self.current = 0
        self.results: list[str] = []
        self.done = False

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def current_step(self) -> str | None:
        if self.current < len(self.steps):
            return self.steps[self.current]
        return None

    def record_result(self, result: str):
        self.results.append(result)
        self.current += 1
        if self.current >= len(self.steps):
            self.done = True

    def progress_summary(self) -> str:
        done = self.current
        total = self.total
        lines = [f"Plan: {self.description}", f"Progress: {done}/{total} steps"]
        for i, step in enumerate(self.steps):
            if i < done:
                res = self.results[i] if i < len(self.results) else ""
                lines.append(f"  ✓ {step}" + (f" → {res}" if res else ""))
            elif i == done:
                lines.append(f"  → {step} (current)")
            else:
                lines.append(f"  ○ {step}")
        return "\n".join(lines)

    async def next_prompt(self) -> str:
        """Build the LLM prompt for the current step, including prior results."""
        if not self.current_step:
            return ""
        ctx = "\n".join(
            f"Step {i+1} result: {r}" for i, r in enumerate(self.results)
        )
        prior_results = f"Prior results:\n{ctx}" if ctx else ""
        return (
            f"You are executing a plan.\n"
            f"Overall task: {self.description}\n"
            f"{prior_results}\n\n"
            f"Current step ({self.current + 1}/{self.total}): {self.current_step}\n\n"
            "Respond as Luna, completing this step. "
            "If a tool call is needed, include a tool_call JSON. "
            "Be brief — one or two sentences max."
        )

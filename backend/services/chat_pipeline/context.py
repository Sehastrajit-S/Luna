"""ChatContext — shared state that flows through all pipeline stages."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """Mutable context passed through every pipeline stage."""

    # ── Input (set by router before pipeline starts) ──────────────────────────
    db: Session
    user_message: str
    conversation_id: Optional[int] = None
    voice: bool = False
    cli: bool = False
    voice_emotion: str = "neutral"
    volume: float = 0.0
    speech_speed: float = 0.0
    speech_duration: float = 0.0
    attachment_ids: list[str] = field(default_factory=list)  # files attached to this message

    # ── Resolved by persist stage ─────────────────────────────────────────────
    conv: Any = None  # Conversation ORM object
    user_msg_obj: Any = None  # Message ORM object

    # ── Resolved by context stage ─────────────────────────────────────────────
    system_prompt: str = ""
    messages: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    conversation_summary: str = ""  # rolling summary of turns older than history
    small_talk: bool = False  # answered by the small-talk fast path (no LLM)
    document_context: str = ""  # attachment text sent to the model this turn (for link checks)
    prev_luna: Optional[str] = None
    relevant_memories: dict = field(default_factory=lambda: {"short_term": [], "long_term": []})
    state_context: str = ""
    proactive_message: Optional[str] = None

    # ── Resolved by dispatch stage (fast-path commands) ───────────────────────
    dispatched: bool = False  # True if a fast-path handler fully resolved the response
    direct_command_type: Optional[str] = None  # e.g. "spotify", "launch", "gmail"

    # ── Resolved by generate stage ────────────────────────────────────────────
    full_response: str = ""
    full_response_parts: list[str] = field(default_factory=list)
    voice_streamed: bool = False
    had_tool_call: bool = False
    tool_succeeded: bool = False
    task_completed: bool = False
    reply_streamed: bool = False  # the agent loop already streamed the final text (voice/CLI)
    tools_used: list[str] = field(default_factory=list)  # tools the agent loop called, in order
    tool_outputs: list[str] = field(default_factory=list)  # their results (links in them count as verified)
    tool_errors: int = 0          # tool calls in the agent loop that failed or were declined
    route: str = ""               # which path answered: small_talk, shortcut:<type>, agent_loop, crew, coding_agent, single_shot

    # ── SSE events to emit (collected by stages, flushed by finalize) ─────────
    sse_events: list[dict] = field(default_factory=list)

    # ── Metadata ──────────────────────────────────────────────────────────────
    is_business: bool = False
    gmail_widget_cmd: Optional[dict] = None

    def emit_sse(self, event: dict) -> None:
        """Queue an SSE event for streaming to the client."""
        self.sse_events.append(event)

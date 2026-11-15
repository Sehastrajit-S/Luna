"""
Chat Pipeline — decomposes the monolithic chat_stream into discrete stages.

Each stage is an async function that receives a ChatContext dataclass and mutates
or extends it.  The pipeline runner calls stages in order.  This makes each stage
independently testable and the overall flow easy to reason about.

Stages:
1. persist     — Save user message, create/get conversation
2. context     — Build memory, personality, state, visual context
3. dispatch    — Fast-path regex commands (Spotify, launch, Gmail, research)
4. generate    — LLM streaming (with planning + coding agent delegation)
5. tools       — Parse tool calls from LLM output, execute them
6. finalize    — Emit SSE events, persist assistant message, queue background tasks
"""
from server.services.chat_pipeline.context import ChatContext
from server.services.chat_pipeline.stages import run_pipeline

__all__ = ["ChatContext", "run_pipeline"]

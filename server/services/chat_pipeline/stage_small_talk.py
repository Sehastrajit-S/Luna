"""
small-talk stage — answer bare greetings/thanks/sign-offs without the LLM.

Runs right after persist. When it handles a message, the context build (memory
retrieval, system prompt), dispatch, generation, and tool stages are skipped,
and finalize skips the LLM-backed background work.
"""
import logging

from server.config import settings
from server.models.database import Message
from server.services.command_parser.small_talk import classify_small_talk, small_talk_reply
from server.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)


def _previous_assistant_message(ctx: ChatContext) -> str:
    msg = (
        ctx.db.query(Message)
        .filter(Message.conversation_id == ctx.conv.id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .first()
    )
    return msg.content if msg else ""


def answer_small_talk(ctx: ChatContext) -> bool:
    """Handle the message if it is pure small talk. Returns True when handled."""
    if settings.luna_variant == "business" or ctx.attachment_ids or getattr(ctx, "skill", ""):
        return False  # "thanks" + a PDF is about the PDF; a picked skill means the message is its input
    prev = _previous_assistant_message(ctx)
    kind = classify_small_talk(ctx.user_message, prev_assistant=prev, user_name=settings.user_name)
    if not kind:
        return False

    ctx.small_talk = True
    ctx.dispatched = True
    ctx.direct_command_type = f"small_talk:{kind}"
    ctx.prev_luna = prev or None
    ctx.full_response = small_talk_reply(kind, settings.user_name)
    ctx.full_response_parts = [ctx.full_response]
    logger.info("Small talk (%s) answered without the LLM", kind)
    return True

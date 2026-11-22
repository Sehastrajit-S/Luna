"""
persist stage — Save the user message and resolve the conversation object.
"""
import logging
from datetime import datetime

from server.config import settings
from server.models.database import Conversation, Message
from server.services.personality import assess_user_sentiment
from server.services.shared_context import get_active_conversation_id, set_active_conversation_id
from server.services.chat_pipeline.context import ChatContext
from server.services.files import link_to_message

logger = logging.getLogger(__name__)


async def persist(ctx: ChatContext) -> None:
    """Create/resolve conversation, save user message to DB."""
    db = ctx.db
    # A temporary or standalone chat never falls back to (or becomes) the shared
    # active conversation — that one is for chats every Luna surface can continue.
    detached = ctx.temporary or ctx.standalone
    conversation_id = ctx.conversation_id or (None if detached else get_active_conversation_id())

    conv = db.query(Conversation).filter_by(id=conversation_id).first() if conversation_id else None
    if conv is None:
        if ctx.temporary:
            # Starting a new one is a good moment to clear temporary chats left open and idle.
            from server.services.conversations import TEMPORARY_IDLE, purge_temporary
            purge_temporary(db, idle_for=TEMPORARY_IDLE)
        conv = Conversation(started_at=datetime.utcnow(), message_count=0, temporary=ctx.temporary)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    ctx.temporary = bool(conv.temporary)

    if not ctx.temporary and not ctx.standalone:
        set_active_conversation_id(conv.id)
    ctx.conv = conv
    ctx.conversation_id = conv.id

    sentiment = assess_user_sentiment(ctx.user_message)
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=ctx.user_message,
        sentiment_score=sentiment,
    )
    db.add(user_msg)
    conv.message_count += 1
    db.commit()
    ctx.user_msg_obj = user_msg

    if ctx.attachment_ids:
        # Only files that were actually linked count from here on (unknown ids,
        # or files claimed by another conversation, are dropped).
        linked = link_to_message(db, ctx.attachment_ids, conv.id, user_msg.id)
        ctx.attachment_ids = [a.id for a in linked]

    logger.debug("Persisted user message (conv=%d, msg_count=%d)", conv.id, conv.message_count)

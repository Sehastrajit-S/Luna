"""
persist stage — Save the user message and resolve the conversation object.
"""
import logging
from datetime import datetime

from backend.config import settings
from backend.models.database import Conversation, Message
from backend.services.personality import assess_user_sentiment
from backend.services.shared_context import get_active_conversation_id, set_active_conversation_id
from backend.services.chat_pipeline.context import ChatContext

logger = logging.getLogger(__name__)


async def persist(ctx: ChatContext) -> None:
    """Create/resolve conversation, save user message to DB."""
    db = ctx.db
    conversation_id = ctx.conversation_id or get_active_conversation_id()

    if conversation_id:
        conv = db.query(Conversation).filter_by(id=conversation_id).first()
        if not conv:
            conv = Conversation(started_at=datetime.utcnow(), message_count=0)
            db.add(conv)
            db.commit()
            db.refresh(conv)
    else:
        conv = Conversation(started_at=datetime.utcnow(), message_count=0)
        db.add(conv)
        db.commit()
        db.refresh(conv)

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

    logger.debug("Persisted user message (conv=%d, msg_count=%d)", conv.id, conv.message_count)

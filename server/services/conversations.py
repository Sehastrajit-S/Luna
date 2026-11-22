"""Deleting conversations, and cleaning up temporary chats.

A temporary chat keeps its messages only while it's open, so Luna can follow
the thread. It never shows in Recent, isn't mined for memory, and is deleted
(with everything that points at it) when the user leaves it, when it sits idle
too long, or when the server restarts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.models.database import (
    Attachment, Conversation, ConversationArtifact, Episode, Fact, FeedbackLog, Message, PlanRecord, Trace,
)
from server.services.files import delete_attachment_files
from server.services.shared_context import get_active_conversation_id, set_active_conversation_id

logger = logging.getLogger(__name__)

TEMPORARY_IDLE = timedelta(hours=6)


def delete_conversation(db: Session, conv: Conversation, *, forget: bool = False) -> None:
    """Delete a conversation and its messages, files and episode.

    Learned facts, feedback, traces and plans normally outlive the chat and are
    only unlinked. With forget=True (temporary chats) they're deleted too.
    """
    conversation_id = conv.id
    linked = [(Fact, Fact.source_conversation_id)] + [(m, m.conversation_id) for m in (FeedbackLog, Trace, PlanRecord)]
    for model, column in linked:
        rows = db.query(model).filter(column == conversation_id)
        if forget:
            rows.delete(synchronize_session=False)
        else:
            rows.update({column: None}, synchronize_session=False)
    db.query(Episode).filter_by(conversation_id=conversation_id).delete(synchronize_session=False)
    db.query(ConversationArtifact).filter_by(conversation_id=conversation_id).delete(synchronize_session=False)
    attachment_ids = [a.id for a in db.query(Attachment.id).filter_by(conversation_id=conversation_id)]
    db.query(Attachment).filter_by(conversation_id=conversation_id).delete(synchronize_session=False)
    db.delete(conv)
    db.commit()
    for attachment_id in attachment_ids:
        try:
            delete_attachment_files(attachment_id)
        except OSError as e:
            logger.warning("Could not remove files for attachment %s: %s", attachment_id, e)
    if get_active_conversation_id() == conversation_id:
        set_active_conversation_id(None)


def purge_temporary(db: Session, *, idle_for: timedelta | None = None) -> int:
    """Delete temporary chats — all of them, or those idle for at least `idle_for`."""
    query = db.query(Conversation).filter(Conversation.temporary == True)  # noqa: E712
    removed = 0
    cutoff = datetime.utcnow() - idle_for if idle_for else None
    for conv in query.all():
        if cutoff is not None:
            last = db.query(func.max(Message.created_at)).filter(Message.conversation_id == conv.id).scalar()
            last = last or conv.started_at
            if last and last.replace(tzinfo=None) > cutoff:
                continue
        delete_conversation(db, conv, forget=True)
        removed += 1
    if removed:
        logger.info("Removed %d temporary chat(s)", removed)
    return removed


def saved_conversation_ids(db: Session):
    """A subquery of conversations that aren't temporary (for queries over past messages)."""
    return db.query(Conversation.id).filter(Conversation.temporary == False)  # noqa: E712

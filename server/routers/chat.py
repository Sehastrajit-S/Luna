"""
Chat router — thin HTTP layer that delegates to the chat pipeline.

The actual business logic lives in server.services.chat_pipeline.
This router only handles HTTP concerns: request parsing, SSE framing, and response.
"""
import logging

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from server.config import settings
from server.models.database import (
    get_db, Attachment, Conversation, ConversationArtifact, Episode, Fact, FeedbackLog, PlanRecord, Trace,
)
from server.models.schemas import ChatRequest, ConversationOut, ConversationDetail, StatusResponse
from server.services.permission_manager import permission_manager
from server.services.shared_context import get_active_conversation_id, set_active_conversation_id
from server.services.chat_pipeline import ChatContext, run_pipeline
from server.services.files import delete_attachment_files

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/confirm/{confirm_id}")
async def confirm_tool(confirm_id: str, request: Request):
    body = await request.json()
    approved = bool(body.get("approved", False))
    ok = permission_manager.submit_answer(confirm_id, approved)
    return JSONResponse({"ok": ok, "confirm_id": confirm_id, "approved": approved})


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    voice: bool = False,
    cli: bool = False,
):
    """Stream a chat response from Luna with full memory and personality context."""
    voice_emotion = request.headers.get("X-Voice-Emotion", "neutral")
    _volume = float(request.headers.get("X-Volume", "0") or 0)
    _speech_speed = float(request.headers.get("X-Speech-Speed", "0") or 0)
    _speech_dur = float(request.headers.get("X-Speech-Duration", "0") or 0)

    # Build the pipeline context
    ctx = ChatContext(
        db=db,
        user_message=req.message,
        conversation_id=req.conversation_id,
        voice=voice,
        cli=cli,
        voice_emotion=voice_emotion,
        volume=_volume,
        speech_speed=_speech_speed,
        speech_duration=_speech_dur,
        attachment_ids=req.attachment_ids,
        skill=(req.skill or "").strip(),
    )

    # Run the pipeline as an SSE stream
    async def generate():
        async for event in run_pipeline(ctx, background_tasks):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Conversation CRUD endpoints ───────────────────────────────────────────────


@router.get("/activity")
def chat_activity(year: int | None = None, month: int | None = None, db: Session = Depends(get_db)):
    """Messages per local day for the dashboard heatmap, with each day's chat topics."""
    from datetime import datetime as _dt
    from server.services.activity_calendar import month_activity

    now = _dt.now()
    year, month = year or now.year, month or now.month
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        raise HTTPException(status_code=422, detail="Invalid month")
    return month_activity(db, year, month)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(limit: int = 20, db: Session = Depends(get_db)):
    conversations = (
        db.query(Conversation)
        .order_by(Conversation.started_at.desc())
        .limit(limit)
        .all()
    )
    # Older conversations may not have a generated title. Use the first user
    # message as a readable display title without changing stored data.
    for conversation in conversations:
        if not conversation.title:
            first_user_message = next(
                (message for message in conversation.messages if message.role == "user"),
                None,
            )
            if first_user_message:
                title = " ".join(first_user_message.content.split())
                conversation.title = title[:52] + ("…" if len(title) > 52 else "")
    return conversations


@router.get("/context")
def get_shared_context(db: Session = Depends(get_db)):
    conversation_id = get_active_conversation_id()
    conv = (
        db.query(Conversation).filter_by(id=conversation_id).first()
        if conversation_id
        else None
    )
    if conversation_id and not conv:
        set_active_conversation_id(None)
        conversation_id = None
    return {"active_conversation_id": conversation_id}


@router.post("/context")
async def set_shared_context(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    raw_id = body.get("active_conversation_id")
    conversation_id = raw_id if isinstance(raw_id, int) and raw_id > 0 else None
    if conversation_id and not db.query(Conversation).filter_by(id=conversation_id).first():
        conversation_id = None
    return set_active_conversation_id(conversation_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        # Other tables reference the conversation (SQLite enforces the FKs), so
        # deleting it alone failed with an IntegrityError. Learned facts,
        # feedback, traces and plans outlive the chat — just unlink them; the
        # episode summary belongs to this conversation only.
        db.query(Fact).filter_by(source_conversation_id=conversation_id).update(
            {Fact.source_conversation_id: None}, synchronize_session=False)
        for model in (FeedbackLog, Trace, PlanRecord):
            db.query(model).filter_by(conversation_id=conversation_id).update(
                {model.conversation_id: None}, synchronize_session=False)
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
    return StatusResponse(status="ok")

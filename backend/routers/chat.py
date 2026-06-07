"""
Chat router — thin HTTP layer that delegates to the chat pipeline.

The actual business logic lives in backend.services.chat_pipeline.
This router only handles HTTP concerns: request parsing, SSE framing, and response.
"""
import logging

from fastapi import APIRouter, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import get_db, Conversation
from backend.models.schemas import ChatRequest, ConversationOut, ConversationDetail, StatusResponse
from backend.services.permission_manager import permission_manager
from backend.services.shared_context import get_active_conversation_id, set_active_conversation_id
from backend.services.chat_pipeline import ChatContext, run_pipeline

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


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(Conversation)
        .order_by(Conversation.started_at.desc())
        .limit(limit)
        .all()
    )


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
    return db.query(Conversation).filter_by(id=conversation_id).first()


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if conv:
        db.delete(conv)
        db.commit()
        if get_active_conversation_id() == conversation_id:
            set_active_conversation_id(None)
    return StatusResponse(status="ok")

"""Meeting mode API.

POST /api/meetings                      start a meeting {title?}
PUT  /api/meetings/{id}/audio?seq=N     append the next recording chunk (raw bytes)
POST /api/meetings/{id}/finish          stop: transcribe and write minutes in the background
GET  /api/meetings/{id}                 status, progress, transcript and minutes
GET  /api/meetings                      recent meetings
"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Request

from server.services import meetings
from server.services.meetings import MeetingError, MeetingNotFound
from server.services.meetings.service import MAX_CHUNK_BYTES

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

_STATUS = {"bad_request": 400, "out_of_order": 409, "wrong_state": 409, "too_large": 413}


def _fail(e: Exception):
    if isinstance(e, MeetingNotFound):
        raise HTTPException(status_code=404, detail="Meeting not found.") from e
    if isinstance(e, MeetingError):
        raise HTTPException(status_code=_STATUS.get(e.kind, 400), detail={"code": e.kind, "message": e.message}) from e
    raise e


@router.post("")
async def start_meeting(payload: dict = Body(default={})):
    return meetings.start(str((payload or {}).get("title") or ""))


@router.put("/{meeting_id}/audio")
async def append_audio(meeting_id: str, request: Request, seq: int = Query(..., ge=0)):
    declared = int(request.headers.get("content-length") or 0)
    if declared > MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail={"code": "too_large", "message": "Audio chunks must be 8 MB or less."})
    data = await request.body()
    try:
        return meetings.append_audio(meeting_id, seq, data)
    except (MeetingError, MeetingNotFound) as e:
        _fail(e)


@router.post("/{meeting_id}/finish")
async def finish_meeting(meeting_id: str):
    try:
        return meetings.finish(meeting_id)
    except (MeetingError, MeetingNotFound) as e:
        _fail(e)


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str):
    try:
        return meetings.get(meeting_id)
    except MeetingNotFound as e:
        _fail(e)


@router.get("")
async def list_meetings(limit: int = Query(20, ge=1, le=100)):
    return {"meetings": meetings.recent(limit)}

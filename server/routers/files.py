"""Chat file attachments: upload, inspect, download, remove."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.models.database import Attachment, Conversation, get_db
from backend.models.schemas import AttachmentOut
from backend.services.files import (
    MAX_UPLOAD_BYTES, SUPPORTED_EXT, UnsupportedFile, delete_attachment_files, original_path,
    prepare_large_file, save_upload,
)
from backend.services.files.service import sweep_unsent_uploads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

_READ_CHUNK = 1024 * 1024


def _get_or_404(db: Session, attachment_id: str) -> Attachment:
    row = db.query(Attachment).filter_by(id=attachment_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return row


@router.get("/supported")
def supported_types():
    return {"extensions": sorted(SUPPORTED_EXT), "max_bytes": MAX_UPLOAD_BYTES}


@router.post("", response_model=AttachmentOut)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    conversation_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    # Read in chunks so an oversized upload is rejected without buffering it all.
    data = bytearray()
    while chunk := await file.read(_READ_CHUNK):
        data.extend(chunk)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"Files can be up to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    if conversation_id is not None and not db.query(Conversation).filter_by(id=conversation_id).first():
        conversation_id = None
    try:
        attachment = await save_upload(db, file.filename or "file", bytes(data), conversation_id)
    except UnsupportedFile as e:
        raise HTTPException(status_code=415, detail=str(e)) from e
    except Exception as e:
        logger.error("Upload of %r failed: %s", file.filename, e, exc_info=True)
        raise HTTPException(status_code=500, detail="The file couldn't be processed.") from e

    if attachment.status == "ready":
        background_tasks.add_task(prepare_large_file, attachment.id)
    background_tasks.add_task(_sweep_unsent)
    return attachment


def _sweep_unsent() -> None:
    db = next(get_db())
    try:
        sweep_unsent_uploads(db)
    except Exception as e:  # housekeeping must never break uploads
        logger.warning("Sweeping unsent uploads failed: %s", e)
    finally:
        db.close()


@router.get("/{attachment_id}", response_model=AttachmentOut)
def get_file(attachment_id: str, db: Session = Depends(get_db)):
    return _get_or_404(db, attachment_id)


@router.get("/{attachment_id}/raw")
def download_file(attachment_id: str, db: Session = Depends(get_db)):
    row = _get_or_404(db, attachment_id)
    path = original_path(row)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File data is missing")
    return FileResponse(path, media_type=row.mime_type, filename=row.filename)


@router.delete("/{attachment_id}")
def delete_file(attachment_id: str, db: Session = Depends(get_db)):
    row = _get_or_404(db, attachment_id)
    if row.message_id is not None:
        # Part of a sent message — removing it would silently change history.
        raise HTTPException(status_code=409, detail="This file is part of a sent message.")
    db.delete(row)
    db.commit()
    delete_attachment_files(attachment_id)
    return {"status": "ok"}

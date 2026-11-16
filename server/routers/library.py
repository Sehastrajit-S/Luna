"""Library: files you've attached in chats, and files Luna created.

GET /api/library/uploads           attachments from sent messages, newest first
GET /api/library/created           files Luna wrote into its workspace (data/workspace)
GET /api/library/created/raw       download one workspace file (path checked against the workspace root)
"""
from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from server.models.database import Attachment, Conversation, get_db
from server.services.workspace import WORKSPACE_DIR, _resolve_workspace_path

router = APIRouter(prefix="/api/library", tags=["library"])

# Workspace folders that aren't Luna's output: installed marketplace skills
# and internal scratch/test folders.
_SKIP_TOP_LEVEL = {"skills"}
_MAX_CREATED = 500


@router.get("/uploads")
def list_uploads(
    q: str = Query("", max_length=200),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Attachment, Conversation.title)
        .outerjoin(Conversation, Attachment.conversation_id == Conversation.id)
        .filter(Attachment.message_id.isnot(None))   # unsent uploads are still drafts
    )
    if q.strip():
        query = query.filter(Attachment.filename.ilike(f"%{q.strip()}%"))
    rows = query.order_by(Attachment.created_at.desc()).limit(limit).all()
    return {"items": [
        {
            "id": a.id,
            "filename": a.filename,
            "kind": a.kind,
            "size_bytes": a.size_bytes,
            "summary_line": a.summary_line,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "conversation_id": a.conversation_id,
            "conversation_title": title,
        }
        for a, title in rows
    ]}


def _is_hidden(rel: Path) -> bool:
    parts = rel.parts
    return (
        not parts
        or parts[0] in _SKIP_TOP_LEVEL
        or any(p.startswith((".", "_")) for p in parts)
    )


@router.get("/created")
def list_created(q: str = Query("", max_length=200)):
    root = WORKSPACE_DIR.resolve()
    needle = q.strip().lower()
    items = []
    if root.exists():
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            if _is_hidden(rel) or not path.is_file():
                continue
            if needle and needle not in rel.as_posix().lower():
                continue
            stat = path.stat()
            items.append({
                "path": rel.as_posix(),
                "name": path.name,
                "folder": rel.parent.as_posix() if rel.parent != Path(".") else "",
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "ext": path.suffix.lower().lstrip("."),
            })
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return {"items": items[:_MAX_CREATED], "truncated": len(items) > _MAX_CREATED}


@router.get("/created/raw")
def download_created(path: str = Query(..., min_length=1, max_length=1000)):
    try:
        target = _resolve_workspace_path(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    rel = target.relative_to(WORKSPACE_DIR.resolve())
    if _is_hidden(rel) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found in Luna's workspace")
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(target, media_type=media_type, filename=target.name)

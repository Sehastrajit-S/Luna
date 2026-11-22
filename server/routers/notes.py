"""Notes app.

GET    /api/notes?q=        all notes (pinned first, then most recently edited), optional search
GET    /api/notes/{id}
POST   /api/notes           create ({"title", "body", "pinned"} all optional)
PATCH  /api/notes/{id}      edit any field (the app autosaves through this)
DELETE /api/notes/{id}

Errors: {"detail": {"kind", "message"}}.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from server.models.database import Note, get_db

router = APIRouter(prefix="/api/notes", tags=["notes"])

MAX_BODY = 200_000
PREVIEW_CHARS = 140


class NoteIn(BaseModel):
    title: str = Field("", max_length=300)
    body: str = Field("", max_length=MAX_BODY)
    pinned: bool = False


class NotePatch(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    body: Optional[str] = Field(None, max_length=MAX_BODY)
    pinned: Optional[bool] = None


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def heading_and_preview(title: str, body: str) -> tuple[str, str]:
    """What the list shows: the title (or, untitled, the body's first line) and the text after it."""
    lines = body.splitlines()
    if not title.strip():
        first = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first is not None:
            title, lines = lines[first].strip()[:120], lines[first + 1:]
    text = " ".join(" ".join(lines).split())
    return title.strip(), text[:PREVIEW_CHARS] + ("…" if len(text) > PREVIEW_CHARS else "")


def note_dict(n: Note, *, full: bool = True) -> dict:
    heading, preview = heading_and_preview(n.title or "", n.body or "")
    out = {
        "id": n.id, "title": n.title or "", "pinned": bool(n.pinned),
        "heading": heading, "preview": preview,
        "created_at": _iso(n.created_at), "updated_at": _iso(n.updated_at),
    }
    if full:
        out["body"] = n.body or ""
    return out


def _get(db: Session, note_id: int) -> Note:
    n = db.get(Note, note_id)
    if not n:
        raise HTTPException(status_code=404, detail={"kind": "not_found", "message": "That note doesn't exist any more."})
    return n


@router.get("")
def list_notes(q: str = Query("", max_length=200), db: Session = Depends(get_db)):
    query = db.query(Note)
    for word in q.split():
        like = f"%{word}%"
        query = query.filter(or_(Note.title.ilike(like), Note.body.ilike(like)))
    notes = query.order_by(Note.pinned.desc(), Note.updated_at.desc(), Note.id.desc()).all()
    return {"notes": [note_dict(n, full=False) for n in notes]}


@router.get("/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)):
    return note_dict(_get(db, note_id))


@router.post("", status_code=201)
def add_note(body: NoteIn, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    n = Note(title=body.title.strip(), body=body.body, pinned=body.pinned, created_at=now, updated_at=now)
    db.add(n)
    db.commit()
    db.refresh(n)
    return note_dict(n)


@router.patch("/{note_id}")
def edit_note(note_id: int, body: NotePatch, db: Session = Depends(get_db)):
    n = _get(db, note_id)
    changes = body.model_dump(exclude_unset=True)
    edited = False
    if changes.get("title") is not None:
        n.title = changes["title"].strip()
        edited = True
    if changes.get("body") is not None:
        n.body = changes["body"]
        edited = True
    if changes.get("pinned") is not None:
        n.pinned = changes["pinned"]
    # Pinning isn't an edit: it shouldn't move the note to the top of "recent".
    if edited:
        n.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(n)
    return note_dict(n)


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, note_id))
    db.commit()
    return Response(status_code=204)

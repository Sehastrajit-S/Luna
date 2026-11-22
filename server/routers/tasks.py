"""Tasks app: Luna's task list (the same tasks Luna adds from chat and the dashboard shows).

GET    /api/tasks                 open tasks, recently completed ones, and the list names in use
POST   /api/tasks                 add a task
PATCH  /api/tasks/{id}            edit any field; {"completed": true|false} checks it off or reopens it
DELETE /api/tasks/{id}
DELETE /api/tasks/completed       clear every completed task

Due times are stored as naive UTC (see server.services.time_utils); send them with a
UTC offset (ISO 8601) and they come back with "Z". Errors: {"detail": {"kind", "message"}}.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from server.models.database import Task, get_db
from server.services.time_utils import to_utc_naive

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

COMPLETED_SHOWN = 200
Priority = Literal["low", "medium", "high"]


def _clean_list(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip().lstrip("#").strip()[:40]
    return value or None


class TaskIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=5000)
    due_date: Optional[datetime] = None
    priority: Priority = "medium"
    list_name: Optional[str] = Field(None, max_length=60)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Give the task a title.")
        return v.strip()


class TaskPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=5000)
    due_date: Optional[datetime] = None
    priority: Optional[Priority] = None
    list_name: Optional[str] = Field(None, max_length=60)
    completed: Optional[bool] = None


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def task_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description or "",
        "due_date": _iso(t.due_date),
        "priority": t.priority or "medium",
        "list_name": t.list_name,
        "completed": bool(t.completed),
        "completed_at": _iso(t.completed_at),
        "created_at": _iso(t.created_at),
    }


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"kind": "not_found", "message": "That task doesn't exist any more."})


@router.get("")
def list_tasks(db: Session = Depends(get_db)):
    open_tasks = db.query(Task).filter(Task.completed == False).all()  # noqa: E712
    done = (db.query(Task).filter(Task.completed == True)  # noqa: E712
            .order_by(Task.completed_at.desc().nullslast(), Task.id.desc())
            .limit(COMPLETED_SHOWN).all())
    lists = [name for (name,) in db.query(Task.list_name).filter(Task.list_name.isnot(None))
             .group_by(Task.list_name).order_by(func.lower(Task.list_name)).all()]
    return {
        "tasks": [task_dict(t) for t in open_tasks + done],
        "lists": lists,
        "completed_total": db.query(func.count(Task.id)).filter(Task.completed == True).scalar(),  # noqa: E712
    }


@router.post("", status_code=201)
def add_task(body: TaskIn, db: Session = Depends(get_db)):
    t = Task(title=body.title, description=(body.description or "").strip() or None,
             due_date=to_utc_naive(body.due_date), priority=body.priority,
             list_name=_clean_list(body.list_name))
    db.add(t)
    db.commit()
    db.refresh(t)
    return task_dict(t)


# Registered before /{task_id} so "completed" isn't read as an id.
@router.delete("/completed")
def clear_completed(db: Session = Depends(get_db)):
    removed = db.query(Task).filter(Task.completed == True).delete(synchronize_session=False)  # noqa: E712
    db.commit()
    return {"removed": removed}


@router.patch("/{task_id}")
def edit_task(task_id: int, body: TaskPatch, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        raise _not_found()
    changes = body.model_dump(exclude_unset=True)
    if "title" in changes:
        if not (changes["title"] or "").strip():
            raise HTTPException(status_code=400, detail={"kind": "bad_request", "message": "Give the task a title."})
        t.title = changes["title"].strip()
    if "description" in changes:
        t.description = (changes["description"] or "").strip() or None
    if "due_date" in changes:
        t.due_date = to_utc_naive(changes["due_date"])
    if changes.get("priority"):
        t.priority = changes["priority"]
    if "list_name" in changes:
        t.list_name = _clean_list(changes["list_name"])
    if changes.get("completed") is not None and bool(t.completed) != changes["completed"]:
        t.completed = changes["completed"]
        t.completed_at = datetime.utcnow() if changes["completed"] else None
    db.commit()
    db.refresh(t)
    return task_dict(t)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t:
        raise _not_found()
    db.delete(t)
    db.commit()
    return Response(status_code=204)

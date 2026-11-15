from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.services.time_utils import to_utc_naive
from backend.models.database import get_db, Task, CalendarEvent
from backend.models.schemas import (
    TaskOut, TaskCreate, EventOut, EventCreate, StatusResponse
)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(completed: bool = None, db: Session = Depends(get_db)):
    q = db.query(Task)
    if completed is not None:
        q = q.filter(Task.completed == completed)
    return q.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()


@router.post("/tasks", response_model=TaskOut)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    data = task.model_dump()
    data["due_date"] = to_utc_naive(data.get("due_date"))    # stored as UTC
    t = Task(**data)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.patch("/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter_by(id=task_id).first()
    if task:
        task.completed = True
        task.completed_at = datetime.utcnow()
        db.commit()
    return task


@router.delete("/tasks/{task_id}", response_model=StatusResponse)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter_by(id=task_id).first()
    if task:
        db.delete(task)
        db.commit()
    return StatusResponse(status="ok")


def _event_fields(event: EventCreate) -> dict:
    data = event.model_dump()
    for key in ("start_datetime", "end_datetime"):
        if key in data:
            data[key] = to_utc_naive(data[key])   # stored as UTC; naive input = local time
    return data


@router.get("/events", response_model=list[EventOut])
def list_events(upcoming_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(CalendarEvent)
    if upcoming_only:
        q = q.filter(CalendarEvent.start_datetime >= datetime.utcnow())
    return q.order_by(CalendarEvent.start_datetime.asc()).all()


@router.post("/events", response_model=EventOut)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    e = CalendarEvent(**_event_fields(event))
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.put("/events/{event_id}", response_model=EventOut)
def update_event(event_id: int, event: EventCreate, db: Session = Depends(get_db)):
    e = db.query(CalendarEvent).filter_by(id=event_id).first()
    if e:
        for k, v in _event_fields(event).items():
            setattr(e, k, v)
        db.commit()
        db.refresh(e)
    return e


@router.delete("/events/{event_id}", response_model=StatusResponse)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    e = db.query(CalendarEvent).filter_by(id=event_id).first()
    if e:
        db.delete(e)
        db.commit()
    return StatusResponse(status="ok")

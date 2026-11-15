"""Sleep tracking endpoints."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.models.database import get_db, SleepLog

router = APIRouter(prefix="/api/sleep", tags=["sleep"])


@router.get("/logs")
def get_sleep_logs(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    logs = (
        db.query(SleepLog)
        .filter(SleepLog.sleep_start >= since)
        .order_by(SleepLog.sleep_start.desc())
        .all()
    )
    return {"logs": [_serialize(l) for l in logs]}


@router.get("/stats")
def get_sleep_stats(db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    logs = (
        db.query(SleepLog)
        .filter(SleepLog.sleep_start >= since, SleepLog.duration_minutes != None)
        .order_by(SleepLog.sleep_start.desc())
        .all()
    )
    bedtime_logs = [l for l in logs if l.label == "bedtime"]
    durations = [l.duration_minutes for l in bedtime_logs if l.duration_minutes]
    avg = sum(durations) / len(durations) if durations else None
    longest = max(durations) if durations else None
    shortest = min(durations) if durations else None
    return {
        "total_nights": len(bedtime_logs),
        "avg_duration_minutes": round(avg, 1) if avg else None,
        "longest_minutes": round(longest, 1) if longest else None,
        "shortest_minutes": round(shortest, 1) if shortest else None,
        "recent_logs": [_serialize(l) for l in bedtime_logs[:7]],
    }


def _serialize(log: SleepLog) -> dict:
    return {
        "id": log.id,
        "sleep_start": log.sleep_start.isoformat() if log.sleep_start else None,
        "sleep_end": log.sleep_end.isoformat() if log.sleep_end else None,
        "duration_minutes": round(log.duration_minutes, 1) if log.duration_minutes else None,
        "label": log.label,
    }

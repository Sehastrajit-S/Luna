"""Shared away-mode flag + sleep tracking. Thread-safe via dict mutation."""
from datetime import datetime, timezone

_away: dict = {"active": False, "sleep_log_id": None, "sleep_start": None}

_BEDTIME_PHRASES = frozenset({
    "bed", "sleep", "night", "nap", "tired", "sleepy",
})


def set_away(on: bool, label: str = "away") -> None:
    _away["active"] = on
    if on:
        _start_sleep(label)
    else:
        _end_sleep()


def is_away() -> bool:
    return _away["active"]


def _start_sleep(label: str) -> None:
    try:
        from backend.models.database import SessionLocal, SleepLog
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            log = SleepLog(sleep_start=now, label=label)
            db.add(log)
            db.commit()
            db.refresh(log)
            _away["sleep_log_id"] = log.id
            _away["sleep_start"] = now
        finally:
            db.close()
    except Exception:
        pass


def _end_sleep() -> None:
    log_id = _away.get("sleep_log_id")
    start  = _away.get("sleep_start")
    if not log_id or not start:
        return
    try:
        from backend.models.database import SessionLocal, SleepLog
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            log = db.query(SleepLog).filter_by(id=log_id).first()
            if log and not log.sleep_end:
                log.sleep_end = now
                log.duration_minutes = (now - start).total_seconds() / 60
                db.commit()
        finally:
            db.close()
    except Exception:
        pass
    _away["sleep_log_id"] = None
    _away["sleep_start"] = None

"""Time conventions: the database stores naive UTC; people (and the model) speak local time.

Scheduler jobs, the agenda and the API all treat stored datetimes as UTC, so
anything that arrives as a wall-clock time ("10 PM", "2026-09-23T22:00:00")
must be converted on the way in.
"""
from __future__ import annotations

from datetime import datetime, timezone


def to_utc_naive(value: datetime | None) -> datetime | None:
    """Naive values are local wall-clock time; aware values keep their zone. Returns naive UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.astimezone()          # interpret as this machine's local time
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_naive_to_local(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def describe_local(value_utc: datetime | None) -> str:
    """'today at 10:00 PM', 'tomorrow at 9:00 AM', 'Fri, Sep 26 at 3:30 PM'."""
    local = utc_naive_to_local(value_utc)
    if local is None:
        return "with no due time"
    today = datetime.now().date()
    clock = local.strftime("%I:%M %p").lstrip("0")
    delta = (local.date() - today).days
    if delta == 0:
        return f"today at {clock}"
    if delta == 1:
        return f"tomorrow at {clock}"
    if delta == -1:
        return f"yesterday at {clock}"
    return f"{local:%a, %b} {local.day} at {clock}"

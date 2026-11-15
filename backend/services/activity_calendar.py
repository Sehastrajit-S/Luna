"""Chat activity per local calendar day (for the dashboard heatmap).

Message timestamps are stored in UTC; days are counted in the user's local
time so late-evening chats land on the right date.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from backend.models.database import Conversation, Message

# messages/day → level 0–4 (same scale GitHub-style heatmaps use)
LEVEL_THRESHOLDS = (1, 3, 8, 16)


def _local_date(utc_naive: datetime) -> date:
    return utc_naive.replace(tzinfo=timezone.utc).astimezone().date()


def _utc_bounds(first: date, last: date) -> tuple[datetime, datetime]:
    start = datetime.combine(first, time.min).astimezone().astimezone(timezone.utc).replace(tzinfo=None)
    end = datetime.combine(last + timedelta(days=1), time.min).astimezone().astimezone(timezone.utc).replace(tzinfo=None)
    return start, end


def level_for(count: int) -> int:
    return sum(1 for threshold in LEVEL_THRESHOLDS if count >= threshold)


def _title(conv: Conversation | None, fallback: str) -> str:
    title = (conv.title if conv and conv.title else fallback) or "Untitled chat"
    title = " ".join(title.split())
    return title[:60] + ("…" if len(title) > 60 else "")


def month_activity(db: Session, year: int, month: int) -> dict:
    first = date(year, month, 1)
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
    start, end = _utc_bounds(first, last)

    rows = (
        db.query(Message.conversation_id, Message.created_at, Message.content)
        .filter(Message.role == "user", Message.created_at >= start, Message.created_at < end)
        .all()
    )
    counts: Counter = Counter()
    periods: Counter = Counter()
    chats_by_day: dict[date, Counter] = defaultdict(Counter)
    first_line: dict[int, str] = {}
    for conv_id, created, content in rows:
        local = created.replace(tzinfo=timezone.utc).astimezone()
        day = local.date()
        periods[_period(local.hour)] += 1
        counts[day] += 1
        chats_by_day[day][conv_id] += 1
        first_line.setdefault(conv_id, content or "")

    conv_ids = {cid for c in chats_by_day.values() for cid in c}
    convs = {c.id: c for c in db.query(Conversation).filter(Conversation.id.in_(conv_ids)).all()} if conv_ids else {}

    days = []
    for n in range(1, last.day + 1):
        day = date(year, month, n)
        count = counts.get(day, 0)
        top = chats_by_day.get(day, Counter()).most_common(3)
        days.append({
            "day": n,
            "messages": count,
            "chats": len(chats_by_day.get(day, {})),
            "level": level_for(count),
            "topics": [_title(convs.get(cid), first_line.get(cid, "")) for cid, _ in top],
        })

    return {
        "year": year,
        "month": month,
        "days": days,
        "total_messages": sum(counts.values()),
        "active_days": sum(1 for d in days if d["messages"]),
        "streak": current_streak(db),
        "most_active": periods.most_common(1)[0][0] if periods else None,
    }


def _period(hour: int) -> str:
    if 5 <= hour < 12:
        return "Mornings"
    if 12 <= hour < 17:
        return "Afternoons"
    if 17 <= hour < 22:
        return "Evenings"
    return "Late nights"


def current_streak(db: Session, today: date | None = None) -> int:
    """Consecutive days with at least one message, ending today (or yesterday
    if today has none yet — the streak isn't broken until the day is over)."""
    today = today or datetime.now().date()
    start, _ = _utc_bounds(today - timedelta(days=400), today)
    active = {
        _local_date(created)
        for (created,) in db.query(Message.created_at).filter(Message.role == "user", Message.created_at >= start)
    }
    day = today if today in active else today - timedelta(days=1)
    streak = 0
    while day in active:
        streak += 1
        day -= timedelta(days=1)
    return streak

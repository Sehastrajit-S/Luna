"""Bracket command parsing and execution."""
import re
from sqlalchemy.orm import Session
from backend.services.command_parser.away import user_is_leaving, response_is_farewell

_BROWSE_BLOCK = re.compile(
    r"(weather\.com|wttr\.in|open-meteo|wunderground|weather\.gov"
    r"|openweathermap|accuweather|forecast\.io|darksky"
    r"|stooq\.com|finance\.yahoo|marketwatch|bloomberg\.com|cnbc\.com/quotes"
    r"|tradingview\.com|investing\.com|barchart\.com"
    r"|coinmarketcap|coingecko|cryptocompare)", re.IGNORECASE
)


def parse_commands(response: str, user_message: str = "") -> list[dict]:
    """Extract embedded action commands from Luna's response."""
    commands: list[dict] = []

    def _emit_away(msg: str, resp: str):
        _bedtime_words = frozenset({"bed", "sleep", "night", "nap"})
        is_bedtime = any(w in msg.lower() for w in _bedtime_words) or response_is_farewell(resp)
        commands.append({"type": "away", "action": "on", "label": "bedtime" if is_bedtime else "away"})

    from backend.config import settings as _cfg
    if _cfg.luna_variant == "personal":
        has_away_bracket = bool(re.search(r'\[AWAY\]', response))
        has_away_literal = bool(re.search(r'(?<!\[)\bAWAY\b(?!\s*])', response))
        if has_away_bracket or has_away_literal:
            if not user_message or user_is_leaving(user_message) or response_is_farewell(response):
                _emit_away(user_message, response)
        elif user_message and user_is_leaving(user_message):
            _emit_away(user_message, response)

    for match in re.finditer(r"\[BROWSE:([^\]]+)\]", response):
        url = match.group(1).strip()
        if not _BROWSE_BLOCK.search(url):
            commands.append({"type": "browse", "url": url})

    for match in re.finditer(r"\[MAP:([^\]]*)\]", response):
        raw = match.group(1).strip()
        lower = raw.lower()
        if lower.startswith("search:"):
            query = raw[7:].strip()
            if query:
                commands.append({"type": "map", "action": "search", "query": query})
        elif lower.startswith("route:"):
            query = raw[6:].strip()
            if query:
                commands.append({"type": "map", "action": "route", "query": query})
        elif lower == "close":
            commands.append({"type": "map", "action": "close"})
        else:
            commands.append({"type": "map", "action": "open"})

    for match in re.finditer(r"\[SPOTIFY:([^\]]*)\]", response):
        raw_query = match.group(1).strip()
        if raw_query.lower().startswith("queue "):
            commands.append({"type": "spotify_queue", "query": raw_query[6:].strip()})
        else:
            commands.append({"type": "spotify", "query": raw_query})

    for match in re.finditer(r"\[LAUNCH:([^\]]+)\]", response):
        commands.append({"type": "launch", "app": match.group(1).strip()})

    for match in re.finditer(r"\[WIDGET:([^|\]]+)\|([^|\]]+)\|([^\]]+)\]", response):
        commands.append({
            "type": "widget",
            "kind": match.group(1).strip(),
            "title": match.group(2).strip(),
            "body": match.group(3).strip(),
        })

    for match in re.finditer(r"\[TASK:([^|]+)\|?([^|]*)\|?([^\]]*)\]", response):
        commands.append({
            "type": "task",
            "title": match.group(1).strip(),
            "due": match.group(2).strip() or None,
            "priority": match.group(3).strip() or "medium",
        })

    for match in re.finditer(r"\[EVENT:([^|]+)\|([^|]+)\|?([^\]]*)\]", response):
        commands.append({
            "type": "event",
            "title": match.group(1).strip(),
            "datetime": match.group(2).strip(),
            "duration": match.group(3).strip() or "60",
        })

    return commands


def _parse_local(value: str | None):
    """The model writes wall-clock local times; the database stores UTC."""
    from datetime import datetime
    from backend.services.time_utils import to_utc_naive

    if not value:
        return None
    try:
        return to_utc_naive(datetime.fromisoformat(value.strip()))
    except ValueError:
        return None


_TITLE_STOPWORDS = frozenset(
    "the a an my our your for with about of to and at on in meeting call task event reminder".split()
)


def _title_words(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower()) if w not in _TITLE_STOPWORDS}


def _same_title(a: str, b: str) -> bool:
    """"Deep learning project meeting" and "meeting for my deep learning project"
    are the same item — the model rewords titles between turns."""
    if a.strip().lower() == b.strip().lower():
        return True
    wa, wb = _title_words(a), _title_words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.75 and len(wa & wb) >= min(2, len(wa), len(wb))


def find_open_task(db: Session, title: str):
    from backend.models.database import Task
    tasks = db.query(Task).filter(Task.completed == False).order_by(Task.created_at.desc()).all()  # noqa: E712
    return next((t for t in tasks if _same_title(t.title, title)), None)


def find_upcoming_event(db: Session, title: str):
    from datetime import datetime
    from backend.models.database import CalendarEvent
    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.start_datetime >= datetime.utcnow())
        .order_by(CalendarEvent.start_datetime.asc())
        .all()
    )
    return next((e for e in events if _same_title(e.title, title)), None)


def save_task(db: Session, title: str, due: str | None, priority: str | None = None) -> tuple[str, object]:
    """Create or update (same title, still open) a task. Local wall-clock due → UTC.
    Shared by [TASK:…] commands and the create_task tool so both behave the same."""
    from backend.models.database import Task

    due_utc = _parse_local(due)
    existing = find_open_task(db, title)
    if existing:
        if due_utc is not None:
            existing.due_date = due_utc
        existing.priority = priority or existing.priority
        return "Updated", existing
    task = Task(title=title.strip(), due_date=due_utc, priority=priority or "medium")
    db.add(task)
    return "Added", task


def save_event(db: Session, title: str, start: str | None, duration: int | str | None = 60) -> tuple[str, object] | None:
    """Create or move (same title, upcoming) an event. Local wall-clock start → UTC."""
    from datetime import timedelta
    from backend.models.database import CalendarEvent

    start_utc = _parse_local(start)
    if start_utc is None:
        return None
    try:
        minutes = int(duration or 60)
    except (TypeError, ValueError):
        minutes = 60
    end_utc = start_utc + timedelta(minutes=minutes) if minutes > 0 else None
    existing = find_upcoming_event(db, title)
    if existing:
        verb = "Updated" if existing.start_datetime == start_utc else "Moved"
        existing.start_datetime, existing.end_datetime = start_utc, end_utc
        return verb, existing
    event = CalendarEvent(title=title.strip(), start_datetime=start_utc, end_datetime=end_utc)
    db.add(event)
    return "Added", event


def save_and_verify(db: Session, cmd: dict) -> str:
    """Save one task/event command, read it back from the database, and describe
    what is actually stored — the confirmation comes from the row, not the model."""
    from backend.models.database import CalendarEvent, Task
    from backend.services.time_utils import describe_local

    title = (cmd.get("title") or "").strip()
    try:
        if cmd["type"] == "task":
            verb, row = save_task(db, title, cmd.get("due"), cmd.get("priority"))
        else:
            saved = save_event(db, title, cmd.get("datetime"), cmd.get("duration"))
            if saved is None:
                return f"I couldn't save “{title}” — I need a date and time for it."
            verb, row = saved
        db.commit()
        model = Task if cmd["type"] == "task" else CalendarEvent
        stored = db.query(model).filter(model.id == row.id).first()
    except Exception as e:
        db.rollback()
        return f"I couldn't save “{title}”: {e}"
    if stored is None:
        return f"I couldn't save “{title}” — it didn't make it into the database."
    if cmd["type"] == "task":
        when = f"due {describe_local(stored.due_date)}" if stored.due_date else "with no due time"
        return f"{verb} task “{stored.title}” — {when}."
    return f"{verb} “{stored.title}” {'to' if verb == 'Added' else 'on'} your calendar — {describe_local(stored.start_datetime)}."


def describe_commands(commands: list[dict], db: Session) -> str:
    """One line per task/event command, for replies that were only a tag."""
    from backend.services.time_utils import describe_local

    lines = []
    for cmd in commands:
        if cmd.get("type") == "task":
            verb = "Updated" if find_open_task(db, cmd["title"]) else "Added"
            due = _parse_local(cmd.get("due"))
            when = f"due {describe_local(due)}" if due else "with no due time"
            lines.append(f"{verb} task “{cmd['title']}” — {when}.")
        elif cmd.get("type") == "event":
            start = _parse_local(cmd.get("datetime"))
            if start:
                verb = "Moved" if find_upcoming_event(db, cmd["title"]) else "Added"
                lines.append(f"{verb} “{cmd['title']}” to your calendar — {describe_local(start)}.")
    return "\n".join(lines)


def execute_commands(commands: list[dict], db: Session, conversation_id: int) -> None:
    """Execute parsed bracket action commands."""
    import os
    from datetime import timedelta
    from backend.services.app_launcher import launch_app
    from backend.models.database import Task, CalendarEvent

    for cmd in commands:
        try:
            if cmd["type"] == "away":
                from backend.services.away_state import set_away
                set_away(True, label=cmd.get("label", "away"))

            elif cmd["type"] == "browse":
                url = cmd.get("url", "")
                if url.startswith("http"):
                    os.startfile(url)

            elif cmd["type"] == "map":
                pass

            elif cmd["type"] == "spotify":
                from backend.services.spotify import spotify_service
                spotify_service.play(cmd.get("query") or None)

            elif cmd["type"] == "spotify_queue":
                from backend.services.spotify import spotify_service
                spotify_service.queue(cmd.get("query") or "")

            elif cmd["type"] == "launch":
                launch_app(cmd["app"])

            elif cmd["type"] == "task":
                # Same title as an open task = the user is changing it ("make it
                # 10 PM"), not asking for a second copy.
                save_task(db, cmd["title"], cmd.get("due"), cmd.get("priority"))

            elif cmd["type"] == "event":
                save_event(db, cmd["title"], cmd.get("datetime"), cmd.get("duration"))
        except Exception:
            pass

    db.commit()

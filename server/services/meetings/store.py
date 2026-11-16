"""Where meetings live: data/workspace/meetings/<id>/.

Each meeting folder holds the recording, transcript.md and minutes.md, so
they show up in Library → Created by Luna. Bookkeeping is in _meeting.json
(hidden from the Library because of the leading underscore).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from server.services import workspace

ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}(?:-[a-z0-9-]{1,48})?(?:-\d+)?$")
META = "_meeting.json"
AUDIO = "recording.webm"
TRANSCRIPT = "transcript.md"
MINUTES = "minutes.md"


class MeetingNotFound(LookupError):
    pass


def root() -> Path:
    path = workspace.WORKSPACE_DIR / "meetings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:48].strip("-")


def new_id(title: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    base = now.strftime("%Y-%m-%d-%H%M") + (f"-{slug(title)}" if slug(title) else "")
    candidate, n = base, 2
    while (root() / candidate).exists():
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def folder(meeting_id: str) -> Path:
    if not ID_RE.match(meeting_id or ""):
        raise MeetingNotFound(meeting_id)
    path = root() / meeting_id
    if not (path / META).exists():
        raise MeetingNotFound(meeting_id)
    return path


def read(meeting_id: str) -> dict:
    return json.loads((folder(meeting_id) / META).read_text(encoding="utf-8"))


def write(meta: dict) -> dict:
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = root() / meta["id"]
    path.mkdir(parents=True, exist_ok=True)
    tmp = path / (META + ".tmp")
    tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tmp.replace(path / META)
    return meta


def update(meeting_id: str, **changes) -> dict:
    meta = read(meeting_id)
    meta.update(changes)
    return write(meta)


def list_all(limit: int = 30) -> list[dict]:
    metas = []
    for path in root().iterdir():
        meta_file = path / META
        if path.is_dir() and meta_file.exists():
            try:
                metas.append(json.loads(meta_file.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    metas.sort(key=lambda m: m.get("started_at") or "", reverse=True)
    return metas[:limit]

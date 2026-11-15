"""Persistent lightweight agent task records."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR

TASKS_PATH = DATA_DIR / "agent_tasks.json"


def _load() -> list[dict[str, Any]]:
    if not TASKS_PATH.exists():
        return []
    try:
        return json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(tasks: list[dict[str, Any]]) -> None:
    TASKS_PATH.write_text(json.dumps(tasks, indent=2, ensure_ascii=True), encoding="utf-8")


def create_agent_task(description: str, steps: list[str] | None = None) -> dict[str, Any]:
    tasks = _load()
    task = {
        "id": str(uuid.uuid4())[:8],
        "description": description,
        "steps": steps or [],
        "status": "planned" if steps else "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": [],
    }
    tasks.append(task)
    _save(tasks)
    return task


def list_agent_tasks(limit: int = 50) -> list[dict[str, Any]]:
    return list(reversed(_load()[-max(1, min(limit, 200)):]))


def update_agent_task(task_id: str, **updates: Any) -> dict[str, Any] | None:
    tasks = _load()
    for task in tasks:
        if task.get("id") == task_id:
            task.update(updates)
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save(tasks)
            return task
    return None

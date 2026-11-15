"""Shared UI context for all local Luna surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from backend.config import DATA_DIR


_PATH = DATA_DIR / "shared_context.json"
_LOCK = Lock()


def _read() -> dict[str, Any]:
    if not _PATH.exists():
        return {}
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: dict[str, Any]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def get_active_conversation_id() -> int | None:
    with _LOCK:
        value = _read().get("active_conversation_id")
    return value if isinstance(value, int) and value > 0 else None


def set_active_conversation_id(conversation_id: int | None) -> dict[str, int | None]:
    with _LOCK:
        data = _read()
        if conversation_id and conversation_id > 0:
            data["active_conversation_id"] = conversation_id
        else:
            data.pop("active_conversation_id", None)
        _write(data)
    return {"active_conversation_id": conversation_id if conversation_id and conversation_id > 0 else None}

"""Append-only audit log for Luna tool and agent actions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR

AUDIT_PATH = DATA_DIR / "audit.log"
AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)


def record_audit(
    action: str,
    *,
    tool: str | None = None,
    args: dict[str, Any] | None = None,
    result: str | None = None,
    risk: str | None = None,
    status: str = "ok",
    conversation_id: int | None = None,
) -> dict[str, Any]:
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "tool": tool,
        "args": args or {},
        "result": result,
        "risk": risk,
        "status": status,
        "conversation_id": conversation_id,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")
    return event


def list_audit(limit: int = 100) -> list[dict[str, Any]]:
    if not AUDIT_PATH.exists():
        return []
    limit = max(1, min(limit, 500))
    lines = AUDIT_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(events))

"""
Database management service.

Provides health checks, connection pool stats, backend info, and
Alembic migration control for the admin API.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from sqlalchemy import text

from backend.models.database import DB_BACKEND, DB_URL, SessionLocal, engine


def db_backend() -> str:
    return DB_BACKEND


def db_url_redacted() -> str:
    """Return db_url with password hidden — safe to log or return via API."""
    try:
        from sqlalchemy.engine import make_url
        u = make_url(DB_URL)
        return u.render_as_string(hide_password=True)
    except Exception:
        return DB_URL[:40] + "..." if len(DB_URL) > 40 else DB_URL


def db_health() -> dict:
    """Ping the database and return timing + pool stats."""
    t0 = time.monotonic()
    error: Optional[str] = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        error = str(exc)

    pool_info: dict = {}
    try:
        pool = engine.pool
        pool_info = {
            "size": getattr(pool, "size", lambda: None)(),
            "checked_out": getattr(pool, "checkedout", lambda: None)(),
            "overflow": getattr(pool, "overflow", lambda: None)(),
            "invalid": getattr(pool, "invalidated", lambda: None)(),
        }
    except Exception:
        pass

    return {
        "backend": DB_BACKEND,
        "url": db_url_redacted(),
        "status": "error" if error else "ok",
        "latency_ms": latency_ms,
        "error": error,
        "pool": pool_info,
    }


def migration_status() -> dict:
    """Return current Alembic revision and whether migrations are up to date."""
    try:
        from alembic import command
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        alembic_cfg = Config(str(Path(__file__).parent.parent.parent / "alembic.ini"))
        scripts = ScriptDirectory.from_config(alembic_cfg)
        head = scripts.get_current_head()

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current = ctx.get_current_revision()

        pending = []
        if current != head:
            for rev in scripts.iterate_revisions(head, current or "base"):
                pending.append(rev.revision)

        return {
            "current": current,
            "head": head,
            "up_to_date": current == head,
            "pending_count": len(pending),
            "pending": pending,
        }
    except Exception as exc:
        return {"error": str(exc), "current": None, "head": None, "up_to_date": None}


def run_migrations() -> dict:
    """Run `alembic upgrade head` in a subprocess and return the result."""
    alembic_ini = str(Path(__file__).parent.parent.parent / "alembic.ini")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Migration timed out after 120 seconds"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def table_stats(db) -> list[dict]:
    """Return row counts for all Luna tables."""
    tables = [
        "conversations", "messages", "facts", "fact_relationships",
        "tasks", "calendar_events", "personality_state", "feedback_log",
        "proactive_log", "state_events", "sleep_logs", "traces",
        "episodes", "benchmark_results", "plan_records",
        "health_metrics", "health_syncs",
    ]
    rows = []
    for table in tables:
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            rows.append({"table": table, "rows": count})
        except Exception:
            rows.append({"table": table, "rows": None})
    return rows

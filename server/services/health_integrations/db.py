"""Database persistence helpers for health metrics."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.database import HealthMetric, HealthSync
from backend.services.health_integrations.models import HealthMetricPoint

log = logging.getLogger(__name__)


def persist(db: Session, points: list[HealthMetricPoint]) -> int:
    saved = 0
    for p in points:
        existing = (
            db.query(HealthMetric)
            .filter_by(platform=p.platform, metric_type=p.metric_type, date_str=p.date_str)
            .first()
        )
        raw_str = json.dumps(p.raw) if p.raw else None
        if existing:
            existing.value     = p.value
            existing.unit      = p.unit
            existing.timestamp = p.timestamp
            existing.raw_json  = raw_str
        else:
            db.add(HealthMetric(
                platform=p.platform,
                metric_type=p.metric_type,
                value=p.value,
                unit=p.unit,
                date_str=p.date_str,
                timestamp=p.timestamp,
                raw_json=raw_str,
            ))
            saved += 1
    db.commit()
    return saved


def _update_sync(db: Session, platform: str, status: str, count: int = 0, error: str = "") -> None:
    row = db.query(HealthSync).filter_by(platform=platform).first()
    if not row:
        row = HealthSync(platform=platform)
        db.add(row)
    row.last_sync_at     = datetime.now(timezone.utc)
    row.status           = status
    row.metrics_synced   = count
    row.error_message    = error or None
    db.commit()


def get_sync_status(db: Session) -> list[dict]:
    rows = db.query(HealthSync).all()
    return [
        {
            "platform":       r.platform,
            "status":         r.status,
            "last_sync_at":   r.last_sync_at.isoformat() if r.last_sync_at else None,
            "metrics_synced": r.metrics_synced,
            "error_message":  r.error_message,
        }
        for r in rows
    ]


def query_metrics(
    db: Session,
    platform: Optional[str] = None,
    metric_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    q = db.query(HealthMetric)
    if platform:
        q = q.filter(HealthMetric.platform == platform)
    if metric_type:
        q = q.filter(HealthMetric.metric_type == metric_type)
    if from_date:
        q = q.filter(HealthMetric.date_str >= from_date)
    if to_date:
        q = q.filter(HealthMetric.date_str <= to_date)
    rows = q.order_by(HealthMetric.date_str.desc()).limit(limit).all()
    return [
        {
            "id":          r.id,
            "platform":    r.platform,
            "metric_type": r.metric_type,
            "value":       r.value,
            "unit":        r.unit,
            "date_str":    r.date_str,
            "timestamp":   r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


def daily_summary(db: Session, date_str: str) -> dict:
    rows = db.query(HealthMetric).filter(HealthMetric.date_str == date_str).all()
    summary: dict[str, list] = {}
    for r in rows:
        summary.setdefault(r.metric_type, []).append(
            {"platform": r.platform, "value": r.value, "unit": r.unit}
        )
    return {"date": date_str, "metrics": summary}

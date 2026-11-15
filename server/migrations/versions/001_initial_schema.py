"""Initial schema — all Luna tables

Revision ID: 001
Revises:
Create Date: 2026-05-21

Designed to be safe on both fresh databases and existing ones that were
created by SQLAlchemy create_all() before Alembic was introduced.
Tables and indexes that already exist are skipped.
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _create_if_missing(table_name: str, *columns, **kw):
    """Create a table only if it doesn't exist yet (safe for retrofitting Alembic)."""
    if table_name not in _existing_tables():
        op.create_table(table_name, *columns, **kw)


def upgrade() -> None:
    _create_if_missing(
        "conversations",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("ended_at", sa.DateTime, nullable=True),
        sa.Column("message_count", sa.Integer, default=0),
    )

    _create_if_missing(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("sentiment_score", sa.Float, nullable=True),
    )

    _create_if_missing(
        "facts",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, default=1.0),
        sa.Column("source_conversation_id", sa.Integer, sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("importance", sa.Float, default=0.5),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("is_private", sa.Boolean, default=False),
        sa.Column("source", sa.String, default="inferred"),
        sa.Column("superseded_by", sa.Integer, sa.ForeignKey("facts.id"), nullable=True),
        sa.Column("memory_type", sa.String, default="long"),
    )

    _create_if_missing(
        "fact_relationships",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("fact_id_a", sa.Integer, sa.ForeignKey("facts.id"), nullable=False),
        sa.Column("fact_id_b", sa.Integer, sa.ForeignKey("facts.id"), nullable=False),
        sa.Column("relationship", sa.String, nullable=False),
        sa.Column("confidence", sa.Float, default=0.8),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("due_date", sa.DateTime, nullable=True),
        sa.Column("completed", sa.Boolean, default=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("priority", sa.String, default="medium"),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "calendar_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_datetime", sa.DateTime, nullable=False),
        sa.Column("end_datetime", sa.DateTime, nullable=True),
        sa.Column("recurring", sa.String, nullable=True),
        sa.Column("location", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "personality_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("verbosity", sa.Float, default=0.5),
        sa.Column("formality", sa.Float, default=0.35),
        sa.Column("humor", sa.Float, default=0.6),
        sa.Column("depth", sa.Float, default=0.55),
        sa.Column("emotional_support", sa.Float, default=0.7),
        sa.Column("question_frequency", sa.Float, default=0.5),
        sa.Column("current_mood", sa.String, default="neutral"),
        sa.Column("mood_intensity", sa.Float, default=0.5),
        sa.Column("energy_level", sa.Float, default=1.0),
        sa.Column("total_interactions", sa.Integer, default=0),
        sa.Column("positive_signals", sa.Integer, default=0),
        sa.Column("negative_signals", sa.Integer, default=0),
        sa.Column("last_interaction", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "feedback_log",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("reward_signal", sa.Float, nullable=False),
        sa.Column("response_features", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "proactive_log",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("reason", sa.String, nullable=True),
        sa.Column("sent_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "state_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("timestamp", sa.DateTime, nullable=True),
        sa.Column("hour", sa.Integer, nullable=False),
        sa.Column("day_of_week", sa.Integer, nullable=False),
        sa.Column("transcript", sa.Text, nullable=True),
        sa.Column("emotion", sa.String, nullable=True),
        sa.Column("volume", sa.Float, nullable=True),
        sa.Column("speech_speed", sa.Float, nullable=True),
        sa.Column("speech_duration", sa.Float, nullable=True),
        sa.Column("pc_active", sa.Boolean, nullable=True),
        sa.Column("active_app", sa.String, nullable=True),
        sa.Column("idle_seconds", sa.Integer, nullable=True),
        sa.Column("inferred_state", sa.String, nullable=False),
    )

    _create_if_missing(
        "sleep_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("sleep_start", sa.DateTime, nullable=False),
        sa.Column("sleep_end", sa.DateTime, nullable=True),
        sa.Column("duration_minutes", sa.Float, nullable=True),
        sa.Column("label", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "traces",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("span_id", sa.String, unique=True, nullable=False),
        sa.Column("parent_id", sa.String, nullable=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("start_time", sa.Float, nullable=False),
        sa.Column("end_time", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("status", sa.String, default="ok"),
        sa.Column("attributes", sa.Text, nullable=True),
        sa.Column("cost_usd", sa.Float, default=0.0),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "episodes",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id"), unique=True, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("key_fact_ids", sa.Text, nullable=True),
        sa.Column("key_entities", sa.Text, nullable=True),
        sa.Column("importance", sa.Float, default=0.5),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "benchmark_results",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("suite", sa.String, nullable=False),
        sa.Column("timestamp", sa.Float, nullable=False),
        sa.Column("metrics", sa.Text, nullable=True),
        sa.Column("errors", sa.Text, nullable=True),
        sa.Column("duration_s", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "plan_records",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("plan_id", sa.String, unique=True, nullable=False),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("steps_json", sa.Text, nullable=True),
        sa.Column("critique_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.Float, nullable=True),
        sa.Column("completed_at", sa.Float, nullable=True),
    )

    _create_if_missing(
        "health_metrics",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("platform", sa.String, nullable=False),
        sa.Column("metric_type", sa.String, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String, nullable=True),
        sa.Column("date_str", sa.String, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=True),
        sa.Column("raw_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    _create_if_missing(
        "health_syncs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("platform", sa.String, nullable=False, unique=True),
        sa.Column("last_sync_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String, default="never"),
        sa.Column("metrics_synced", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    for table in [
        "health_syncs", "health_metrics", "plan_records", "benchmark_results",
        "episodes", "traces", "sleep_logs", "state_events", "proactive_log",
        "feedback_log", "personality_state", "calendar_events", "tasks",
        "fact_relationships", "facts", "messages", "conversations",
    ]:
        op.drop_table(table, if_exists=True)

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, JSON, ForeignKey, func, event, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool, QueuePool
from datetime import datetime, timezone
from server.config import settings


def _resolve_db_url() -> str:
    """Return the effective database URL — explicit db_url wins, else SQLite fallback."""
    url = (settings.db_url or "").strip()
    return url or f"sqlite:///{settings.db_path}"


def _db_backend(url: str) -> str:
    """Return short backend name from URL scheme."""
    if url.startswith("sqlite"):
        return "sqlite"
    if "postgresql" in url or "postgres" in url:
        return "postgresql"
    if "mysql" in url or "mariadb" in url:
        return "mysql"
    if "mssql" in url:
        return "mssql"
    return "unknown"


def _build_engine(url: str):
    backend = _db_backend(url)
    if backend == "sqlite":
        eng = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.db_echo,
        )
        # Enable WAL mode for SQLite — better concurrent read performance
        @event.listens_for(eng, "connect")
        def _set_wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
        return eng
    else:
        return create_engine(
            url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,     # detect and drop stale connections
            echo=settings.db_echo,
        )


DB_URL = _resolve_db_url()
DB_BACKEND = _db_backend(DB_URL)

engine = _build_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    # Temporary chat: hidden from Recent, never mined for memory, deleted when the user leaves it.
    temporary = Column(Boolean, nullable=False, default=False, server_default="0")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sentiment_score = Column(Float, nullable=True)  # -1 to 1
    conversation = relationship("Conversation", back_populates="messages")
    attachments = relationship("Attachment", back_populates="message", order_by="Attachment.created_at")


class ConversationArtifact(Base):
    """Something Luna produced in a conversation that later turns build on —
    today, code blocks. Kept outside the chat history so it survives context
    fitting and summaries (like files on disk for a coding agent)."""
    __tablename__ = "conversation_artifacts"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    turn = Column(Integer, nullable=True)                      # user turn number it answered
    kind = Column(String, nullable=False, default="code")
    language = Column(String, nullable=True)
    names = Column(String, nullable=True)                      # "encode_base62, decode_base62"
    title = Column(String, nullable=True)                      # the request it answered, shortened
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Attachment(Base):
    """A file the user attached in chat. Bytes and extracted text live under
    data/uploads/<id>/ (see services/files); this row is the index."""
    __tablename__ = "attachments"
    id = Column(String, primary_key=True)                       # uuid4 hex
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True, index=True)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    kind = Column(String, nullable=False)                       # pdf | docx | pptx | spreadsheet | csv | text | image
    size_bytes = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="ready")    # ready | error
    error = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)                 # pages / slides / sheets / rows
    token_estimate = Column(Integer, nullable=True)
    summary_line = Column(String, nullable=True)                # "PDF · 12 pages"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    message = relationship("Message", back_populates="attachments")


class Fact(Base):
    __tablename__ = "facts"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)  # personal|preference|relationship|event|goal|health
    content = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    source_conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    # Memory quality fields (improvement #5)
    importance = Column(Float, default=0.5)          # 0=trivial, 1=critical
    expires_at = Column(DateTime, nullable=True)      # auto-deactivate after this datetime
    is_private = Column(Boolean, default=False)       # hide from prompt context when True
    source = Column(String, default="inferred")       # explicit|inferred|observed
    superseded_by = Column(Integer, ForeignKey("facts.id"), nullable=True)  # conflict resolution
    memory_type = Column(String, default="long")      # "short" | "long" | "persistent"


class FactRelationship(Base):
    __tablename__ = "fact_relationships"
    id = Column(Integer, primary_key=True, index=True)
    fact_id_a = Column(Integer, ForeignKey("facts.id"), nullable=False)
    fact_id_b = Column(Integer, ForeignKey("facts.id"), nullable=False)
    relationship = Column(String, nullable=False)  # contradicts|confirms|updates|pattern
    confidence = Column(Float, default=0.8)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    priority = Column(String, default="medium")  # low|medium|high
    list_name = Column(String, nullable=True)    # Tasks app list ("Work", "Personal"); None = no list
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)
    recurring = Column(String, nullable=True)  # daily|weekly|monthly|yearly
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PersonalityState(Base):
    __tablename__ = "personality_state"
    id = Column(Integer, primary_key=True, default=1)
    # Learned style preferences (0.0 - 1.0)
    verbosity = Column(Float, default=0.5)        # 0=brief, 1=detailed
    formality = Column(Float, default=0.35)       # 0=casual, 1=formal
    humor = Column(Float, default=0.6)            # 0=serious, 1=witty
    depth = Column(Float, default=0.55)           # 0=surface, 1=technical deep
    emotional_support = Column(Float, default=0.7)
    question_frequency = Column(Float, default=0.5)
    # Mood state
    current_mood = Column(String, default="neutral")
    mood_intensity = Column(Float, default=0.5)
    energy_level = Column(Float, default=1.0)
    # Interaction history
    total_interactions = Column(Integer, default=0)
    positive_signals = Column(Integer, default=0)
    negative_signals = Column(Integer, default=0)
    last_interaction = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FeedbackLog(Base):
    __tablename__ = "feedback_log"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    reward_signal = Column(Float, nullable=False)  # -1.0 to 1.0
    response_features = Column(JSON, nullable=True)  # {verbosity, humor, depth, ...}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ProactiveLog(Base):
    __tablename__ = "proactive_log"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    reason = Column(String, nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class StateEvent(Base):
    """Time-aware state engine event log."""
    __tablename__ = "state_events"
    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    hour           = Column(Integer, nullable=False)
    day_of_week    = Column(Integer, nullable=False)   # 0=Mon … 6=Sun
    transcript     = Column(Text, nullable=True)
    emotion        = Column(String, nullable=True)
    volume         = Column(Float, nullable=True)       # RMS 0-1 (normalised)
    speech_speed   = Column(Float, nullable=True)       # words-per-minute
    speech_duration= Column(Float, nullable=True)       # seconds
    pc_active      = Column(Boolean, nullable=True)
    active_app     = Column(String, nullable=True)      # process name
    idle_seconds   = Column(Integer, nullable=True)     # seconds since last input
    inferred_state = Column(String, nullable=False)     # UserState enum value


class SleepLog(Base):
    __tablename__ = "sleep_logs"
    id          = Column(Integer, primary_key=True, index=True)
    sleep_start = Column(DateTime, nullable=False)
    sleep_end   = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True)   # filled on wake
    label       = Column(String, nullable=True)        # "bedtime" | "nap" | "away"
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Trace(Base):
    """One span from the telemetry tracer."""
    __tablename__ = "traces"
    id              = Column(Integer, primary_key=True, index=True)
    span_id         = Column(String, unique=True, nullable=False, index=True)
    parent_id       = Column(String, nullable=True)
    name            = Column(String, nullable=False)       # llm_call | memory_retrieve | tool_call | …
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    start_time      = Column(Float, nullable=False)        # monotonic seconds
    end_time        = Column(Float, nullable=True)
    latency_ms      = Column(Float, nullable=True)
    status          = Column(String, default="ok")         # ok | error
    attributes      = Column(Text, nullable=True)          # JSON blob
    cost_usd        = Column(Float, default=0.0)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Episode(Base):
    """Episodic memory: one row per completed conversation."""
    __tablename__ = "episodes"
    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), unique=True, nullable=False, index=True)
    summary         = Column(Text, nullable=False)
    key_fact_ids    = Column(Text, nullable=True)          # JSON list of Fact IDs
    key_entities    = Column(Text, nullable=True)          # JSON list of entity strings
    importance      = Column(Float, default=0.5)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class BenchmarkResult(Base):
    """Historical benchmark run result for one suite."""
    __tablename__ = "benchmark_results"
    id          = Column(Integer, primary_key=True, index=True)
    suite       = Column(String, nullable=False, index=True)   # memory | llm | tools | planner
    timestamp   = Column(Float, nullable=False)
    metrics     = Column(Text, nullable=True)                  # JSON dict
    errors      = Column(Text, nullable=True)                  # JSON list
    duration_s  = Column(Float, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PlanRecord(Base):
    """Persisted plan from the planner-executor-critic engine."""
    __tablename__ = "plan_records"
    id              = Column(Integer, primary_key=True, index=True)
    plan_id         = Column(String, unique=True, nullable=False, index=True)
    goal            = Column(Text, nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    status          = Column(String, nullable=False)           # planning | running | done | failed | critiqued
    steps_json      = Column(Text, nullable=True)              # JSON list of Step dataclass dicts
    critique_json   = Column(Text, nullable=True)              # JSON CritiqueResult dict
    created_at      = Column(Float, nullable=True)             # monotonic timestamp
    completed_at    = Column(Float, nullable=True)


class HealthMetric(Base):
    """One data point from any health platform (steps, HR, sleep, weight, etc.)."""
    __tablename__ = "health_metrics"
    id          = Column(Integer, primary_key=True, index=True)
    platform    = Column(String, nullable=False, index=True)   # fitbit | google_fit | oura | withings | garmin | apple | samsung
    metric_type = Column(String, nullable=False, index=True)   # steps | heart_rate | sleep_duration_min | weight_kg | …
    value       = Column(Float, nullable=False)
    unit        = Column(String, nullable=True)                 # steps | bpm | min | kg | % | mmHg | …
    date_str    = Column(String, nullable=False, index=True)    # YYYY-MM-DD — daily bucket
    timestamp   = Column(DateTime, nullable=True)               # intra-day precision if available
    raw_json    = Column(Text, nullable=True)                   # original API response snippet
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class HealthSync(Base):
    """Last sync state per platform."""
    __tablename__ = "health_syncs"
    id              = Column(Integer, primary_key=True, index=True)
    platform        = Column(String, nullable=False, unique=True)
    last_sync_at    = Column(DateTime, nullable=True)
    status          = Column(String, default="never")       # never | ok | error
    metrics_synced  = Column(Integer, default=0)
    error_message   = Column(Text, nullable=True)
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Note(Base):
    """A note in the Notes app."""
    __tablename__ = "notes"
    id         = Column(Integer, primary_key=True, index=True)
    title      = Column(String, nullable=False, default="")
    body       = Column(Text, nullable=False, default="")
    pinned     = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class BudgetCategory(Base):
    """A spending category with an optional monthly limit (0 = no limit)."""
    __tablename__ = "budget_categories"
    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False, unique=True)
    icon        = Column(String, nullable=False, default="")
    limit_cents = Column(Integer, nullable=False, default=0)
    sort        = Column(Integer, nullable=False, default=0)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class BudgetTransaction(Base):
    """One expense or income entry. Amounts are whole cents, always positive."""
    __tablename__ = "budget_transactions"
    id           = Column(Integer, primary_key=True, index=True)
    kind         = Column(String, nullable=False, default="expense")   # expense | income
    amount_cents = Column(Integer, nullable=False)
    description  = Column(String, nullable=False, default="")
    category_id  = Column(Integer, ForeignKey("budget_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    date_str     = Column(String, nullable=False, index=True)          # YYYY-MM-DD
    source       = Column(String, nullable=False, default="manual")    # manual | receipt
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)

    # SQLite-only backward-compat: add columns introduced in later versions.
    # For PostgreSQL/MySQL/MSSQL these are handled by Alembic (`alembic upgrade head`).
    if DB_BACKEND == "sqlite":
        with engine.connect() as conn:
            for col, definition in [
                ("importance",     "REAL DEFAULT 0.5"),
                ("expires_at",     "DATETIME"),
                ("is_private",     "BOOLEAN DEFAULT 0"),
                ("source",         "VARCHAR DEFAULT 'inferred'"),
                ("superseded_by",  "INTEGER"),
                ("memory_type",    "VARCHAR DEFAULT 'long'"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE facts ADD COLUMN {col} {definition}"))
                    conn.commit()
                except Exception:
                    pass  # column already exists
            for table, column, definition in [
                ("tasks", "list_name", "VARCHAR"),
                ("conversations", "temporary", "BOOLEAN NOT NULL DEFAULT 0"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                    conn.commit()
                except Exception:
                    pass  # column already exists

    db = SessionLocal()
    try:
        state = db.query(PersonalityState).filter_by(id=1).first()
        if not state:
            db.add(PersonalityState(id=1))
            db.commit()
    finally:
        db.close()

"""
Alembic environment for Luna.

Reads the database URL from Luna's settings (backend/config.py) so that
`alembic upgrade head` always targets the same database as the running app.

Usage:
  alembic upgrade head         # apply all pending migrations
  alembic downgrade -1         # roll back one migration
  alembic current              # show current schema revision
  alembic history              # list all migrations
  alembic revision --autogenerate -m "add X column"  # generate from model changes
"""

import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make sure Luna's backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.models.database import Base, _resolve_db_url, _db_backend

# Alembic Config object — gives access to alembic.ini values
config = context.config

# Wire up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for --autogenerate support
target_metadata = Base.metadata

# Resolve DB URL from Luna settings at runtime
_url = _resolve_db_url()
config.set_main_option("sqlalchemy.url", _url)
_backend = _db_backend(_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection)."""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connect_args = {}
    pool_class = pool.NullPool  # no pooling inside short-lived alembic process

    if _backend == "sqlite":
        connect_args = {"check_same_thread": False}

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool_class,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Render AS IDENTITY instead of AUTOINCREMENT for SQL Server
            render_as_batch=(_backend == "sqlite"),  # batch mode required for SQLite ALTER
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Notes app and temporary chats

Revision ID: 005
Revises: 004
Create Date: 2026-11-17
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Skip what create_all()/startup already made.
    inspector = sa.inspect(op.get_bind())
    if "notes" not in inspector.get_table_names():
        op.create_table(
            "notes",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("title", sa.String, nullable=False),
            sa.Column("body", sa.Text, nullable=False),
            sa.Column("pinned", sa.Boolean, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_notes_updated_at", "notes", ["updated_at"])
    columns = {c["name"] for c in inspector.get_columns("conversations")}
    if "temporary" not in columns:
        op.add_column("conversations", sa.Column("temporary", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("conversations", "temporary")
    op.drop_index("ix_notes_updated_at", table_name="notes")
    op.drop_table("notes")

"""Chat file attachments

Revision ID: 002
Revises: 001
Create Date: 2026-09-23
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Skip if create_all() already made it (the app creates tables on startup).
    if "attachments" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "attachments",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("conversation_id", sa.Integer, sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("mime_type", sa.String, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("token_estimate", sa.Integer, nullable=True),
        sa.Column("summary_line", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_attachments_conversation_id", "attachments", ["conversation_id"])
    op.create_index("ix_attachments_message_id", "attachments", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_message_id", table_name="attachments")
    op.drop_index("ix_attachments_conversation_id", table_name="attachments")
    op.drop_table("attachments")

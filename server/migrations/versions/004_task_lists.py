"""Tasks app lists

Revision ID: 004
Revises: 003
Create Date: 2026-11-17
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Skip if the app already added it on startup.
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("tasks")}
    if "list_name" not in columns:
        op.add_column("tasks", sa.Column("list_name", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "list_name")

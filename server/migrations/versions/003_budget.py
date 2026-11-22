"""Budget categories and transactions

Revision ID: 003
Revises: 002
Create Date: 2026-11-17
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Skip tables create_all() already made (the app creates tables on startup).
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "budget_categories" not in existing:
        op.create_table(
            "budget_categories",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False, unique=True),
            sa.Column("icon", sa.String, nullable=False),
            sa.Column("limit_cents", sa.Integer, nullable=False),
            sa.Column("sort", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )
    if "budget_transactions" not in existing:
        op.create_table(
            "budget_transactions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("kind", sa.String, nullable=False),
            sa.Column("amount_cents", sa.Integer, nullable=False),
            sa.Column("description", sa.String, nullable=False),
            sa.Column("category_id", sa.Integer,
                      sa.ForeignKey("budget_categories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("date_str", sa.String, nullable=False),
            sa.Column("source", sa.String, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_budget_transactions_category_id", "budget_transactions", ["category_id"])
        op.create_index("ix_budget_transactions_date_str", "budget_transactions", ["date_str"])


def downgrade() -> None:
    op.drop_index("ix_budget_transactions_date_str", table_name="budget_transactions")
    op.drop_index("ix_budget_transactions_category_id", table_name="budget_transactions")
    op.drop_table("budget_transactions")
    op.drop_table("budget_categories")

"""add user rules

Revision ID: 20260506_0900
Revises: 20260506_0417
Create Date: 2026-05-06 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260506_0900"
down_revision: str | None = "20260506_0417"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_rules",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("match_merchant_raw", sa.Text(), nullable=True),
        sa.Column("match_account_clue", sa.Text(), nullable=True),
        sa.Column("set_account_id", sa.String(length=64), nullable=True),
        sa.Column("set_merchant_canonical", sa.String(length=160), nullable=True),
        sa.Column("set_category", sa.String(length=80), nullable=True),
        sa.Column("set_purpose", sa.String(length=40), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=35), nullable=False),
        sa.Column("updated_at", sa.String(length=35), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user_rules")

"""add categories

Revision ID: 20260506_0417
Revises: 20260505_1645
Create Date: 2026-05-06 04:17:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260506_0417"
down_revision: str | None = "20260505_1645"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("intent_type", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.String(length=35), nullable=False),
        sa.Column("updated_at", sa.String(length=35), nullable=False),
        sa.Column("deleted_at", sa.String(length=35), nullable=True),
        sa.Column("deleted_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("categories")

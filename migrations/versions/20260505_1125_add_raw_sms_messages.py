"""add raw sms messages

Revision ID: 20260505_1125
Revises: 20260505_0919
Create Date: 2026-05-05 11:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260505_1125"
down_revision: str | None = "20260505_0919"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_sms_messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("external_message_id", sa.String(length=160), nullable=False),
        sa.Column("sender", sa.String(length=80), nullable=False),
        sa.Column("received_at", sa.String(length=35), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("parser_output", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=35), nullable=False),
        sa.Column("updated_at", sa.String(length=35), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_message_id"),
    )


def downgrade() -> None:
    op.drop_table("raw_sms_messages")

"""initial ledger tables

Revision ID: 20260505_0919
Revises:
Create Date: 2026-05-05 09:19:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260505_0919"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("account_type", sa.String(length=40), nullable=False),
        sa.Column("balance_tracking", sa.Boolean(), nullable=False),
        sa.Column("current_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_manual_update", sa.Date(), nullable=True),
        sa.Column("created_at", sa.String(length=35), nullable=False),
        sa.Column("updated_at", sa.String(length=35), nullable=False),
        sa.Column("deleted_at", sa.String(length=35), nullable=True),
        sa.Column("deleted_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_type", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("merchant_raw", sa.Text(), nullable=True),
        sa.Column("merchant_canonical", sa.String(length=160), nullable=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("parsing_confidence", sa.String(length=20), nullable=True),
        sa.Column("merchant_mapping_confidence", sa.String(length=20), nullable=True),
        sa.Column("category_confidence", sa.String(length=20), nullable=True),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("duplicate_status", sa.String(length=40), nullable=False),
        sa.Column("ledger_status", sa.String(length=40), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=35), nullable=False),
        sa.Column("updated_at", sa.String(length=35), nullable=False),
        sa.Column("deleted_at", sa.String(length=35), nullable=True),
        sa.Column("deleted_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=True),
        sa.Column("transaction_id", sa.String(length=64), nullable=True),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("field_changes", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=35), nullable=False),
        sa.Column("updated_at", sa.String(length=35), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["ledger_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("ledger_transactions")
    op.drop_table("accounts")

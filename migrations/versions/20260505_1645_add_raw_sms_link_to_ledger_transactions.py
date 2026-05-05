"""add raw sms link to ledger transactions

Revision ID: 20260505_1645
Revises: 20260505_1125
Create Date: 2026-05-05 16:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260505_1645"
down_revision: str | None = "20260505_1125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ledger_transactions") as batch_op:
        batch_op.add_column(sa.Column("raw_sms_message_id", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_ledger_transactions_raw_sms_message_id",
            ["raw_sms_message_id"],
        )
        batch_op.create_foreign_key(
            "fk_ledger_transactions_raw_sms_message_id_raw_sms_messages",
            "raw_sms_messages",
            ["raw_sms_message_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ledger_transactions") as batch_op:
        batch_op.drop_constraint(
            "fk_ledger_transactions_raw_sms_message_id_raw_sms_messages",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "uq_ledger_transactions_raw_sms_message_id",
            type_="unique",
        )
        batch_op.drop_column("raw_sms_message_id")

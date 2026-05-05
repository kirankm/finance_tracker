from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.database import Base

__all__ = ["Account", "AuditEvent", "Base", "LedgerTransaction", "RawSmsMessage"]


class UTCDateTime(TypeDecorator[datetime]):
    impl = String(35)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: object
    ) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()

    def process_result_value(
        self, value: str | None, dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)


def utc_now() -> datetime:
    return datetime.now(UTC)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deleted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )


class Account(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(40), nullable=False)
    balance_tracking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_manual_update: Mapped[date | None] = mapped_column(Date, nullable=True)

    transactions: Mapped[list["LedgerTransaction"]] = relationship(
        back_populates="account", cascade="save-update, merge"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="account", cascade="save-update, merge"
    )


class LedgerTransaction(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ledger_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    merchant_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_canonical: Mapped[str | None] = mapped_column(String(160), nullable=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    parsing_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    merchant_mapping_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    duplicate_status: Mapped[str] = mapped_column(String(40), nullable=False)
    ledger_status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    account: Mapped[Account] = relationship(back_populates="transactions")
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="transaction", cascade="save-update, merge"
    )


class RawSmsMessage(Base, TimestampMixin):
    __tablename__ = "raw_sms_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_message_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    sender: Mapped[str] = mapped_column(String(80), nullable=False)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False)
    parser_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field_changes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[Account | None] = relationship(back_populates="audit_events")
    transaction: Mapped[LedgerTransaction | None] = relationship(back_populates="audit_events")

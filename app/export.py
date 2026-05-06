import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Any

from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, LedgerTransaction, RawSmsMessage


def export_json(db_session: Session) -> dict[str, Any]:
    return {
        "format_version": 1,
        "accounts": [
            account_to_dict(account)
            for account in db_session.scalars(select(Account).order_by(Account.id))
        ],
        "ledger_transactions": [
            transaction_to_dict(transaction)
            for transaction in db_session.scalars(
                select(LedgerTransaction).order_by(
                    LedgerTransaction.transaction_date,
                    LedgerTransaction.id,
                )
            )
        ],
        "raw_sms_messages": [
            raw_sms_to_metadata(raw_sms)
            for raw_sms in db_session.scalars(
                select(RawSmsMessage).order_by(RawSmsMessage.received_at, RawSmsMessage.id)
            )
        ],
        "audit_events": [
            audit_event_to_dict(audit_event)
            for audit_event in db_session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id)
            )
        ],
    }


def export_ledger_csv(db_session: Session) -> Response:
    rows = [
        transaction_to_dict(transaction)
        for transaction in db_session.scalars(
            select(LedgerTransaction).order_by(
                LedgerTransaction.transaction_date,
                LedgerTransaction.id,
            )
        )
    ]
    output = StringIO()
    fieldnames = [
        "id",
        "transaction_date",
        "amount",
        "transaction_type",
        "purpose",
        "category",
        "merchant_raw",
        "merchant_canonical",
        "account_id",
        "source",
        "review_status",
        "duplicate_status",
        "ledger_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ledger-transactions.csv"'},
    )


def account_to_dict(account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "balance_tracking": account.balance_tracking,
        "current_balance": serialize(account.current_balance),
        "last_manual_update": serialize(account.last_manual_update),
        "deleted_at": serialize(account.deleted_at),
        "deleted_reason": account.deleted_reason,
        "created_at": serialize(account.created_at),
        "updated_at": serialize(account.updated_at),
    }


def transaction_to_dict(transaction: LedgerTransaction) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "transaction_date": serialize(transaction.transaction_date),
        "amount": serialize(transaction.amount),
        "transaction_type": transaction.transaction_type,
        "purpose": transaction.purpose,
        "category": transaction.category,
        "merchant_raw": transaction.merchant_raw,
        "merchant_canonical": transaction.merchant_canonical,
        "account_id": transaction.account_id,
        "raw_sms_message_id": transaction.raw_sms_message_id,
        "source": transaction.source,
        "parsing_confidence": transaction.parsing_confidence,
        "merchant_mapping_confidence": transaction.merchant_mapping_confidence,
        "category_confidence": transaction.category_confidence,
        "review_status": transaction.review_status,
        "duplicate_status": transaction.duplicate_status,
        "ledger_status": transaction.ledger_status,
        "source_metadata": transaction.source_metadata,
        "deleted_at": serialize(transaction.deleted_at),
        "deleted_reason": transaction.deleted_reason,
        "created_at": serialize(transaction.created_at),
        "updated_at": serialize(transaction.updated_at),
    }


def raw_sms_to_metadata(raw_sms: RawSmsMessage) -> dict[str, Any]:
    return {
        "id": raw_sms.id,
        "external_message_id": raw_sms.external_message_id,
        "sender": raw_sms.sender,
        "received_at": serialize(raw_sms.received_at),
        "source": raw_sms.source,
        "processing_status": raw_sms.processing_status,
        "parser_output": raw_sms.parser_output,
        "body_exported": False,
        "created_at": serialize(raw_sms.created_at),
        "updated_at": serialize(raw_sms.updated_at),
    }


def audit_event_to_dict(audit_event: AuditEvent) -> dict[str, Any]:
    return {
        "id": audit_event.id,
        "account_id": audit_event.account_id,
        "transaction_id": audit_event.transaction_id,
        "actor_type": audit_event.actor_type,
        "event_type": audit_event.event_type,
        "field_changes": audit_event.field_changes,
        "reason": audit_event.reason,
        "created_at": serialize(audit_event.created_at),
        "updated_at": serialize(audit_event.updated_at),
    }


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value

import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Any

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, Category, LedgerTransaction, RawSmsMessage, UserRule

SUPPORTED_EXPORT_FORMAT_VERSIONS = {1, 2}
CURRENT_EXPORT_FORMAT_VERSION = 2
REQUIRED_IMPORT_SECTIONS = (
    "accounts",
    "ledger_transactions",
    "raw_sms_messages",
    "categories",
    "audit_events",
    "user_rules",
)


def export_json(db_session: Session, *, include_raw_sms_body: bool = False) -> dict[str, Any]:
    return {
        "format_version": CURRENT_EXPORT_FORMAT_VERSION,
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
            raw_sms_to_metadata(raw_sms, include_body=include_raw_sms_body)
            for raw_sms in db_session.scalars(
                select(RawSmsMessage).order_by(RawSmsMessage.received_at, RawSmsMessage.id)
            )
        ],
        "categories": [
            category_to_dict(category)
            for category in db_session.scalars(select(Category).order_by(Category.id))
        ],
        "audit_events": [
            audit_event_to_dict(audit_event)
            for audit_event in db_session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id)
            )
        ],
        "user_rules": [
            user_rule_to_dict(rule)
            for rule in db_session.scalars(
                select(UserRule).order_by(UserRule.priority, UserRule.id)
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
    writer.writerows(sanitize_csv_row(row) for row in rows)
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


def raw_sms_to_metadata(raw_sms: RawSmsMessage, *, include_body: bool = False) -> dict[str, Any]:
    row = {
        "id": raw_sms.id,
        "external_message_id": raw_sms.external_message_id,
        "sender": raw_sms.sender,
        "received_at": serialize(raw_sms.received_at),
        "source": raw_sms.source,
        "processing_status": raw_sms.processing_status,
        "parser_output": raw_sms.parser_output,
        "body_exported": include_body,
        "created_at": serialize(raw_sms.created_at),
        "updated_at": serialize(raw_sms.updated_at),
    }
    if include_body:
        row["body"] = raw_sms.body
    return row


def category_to_dict(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "intent_type": category.intent_type,
        "deleted_at": serialize(category.deleted_at),
        "deleted_reason": category.deleted_reason,
        "created_at": serialize(category.created_at),
        "updated_at": serialize(category.updated_at),
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


def user_rule_to_dict(rule: UserRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "priority": rule.priority,
        "match_merchant_raw": rule.match_merchant_raw,
        "match_account_clue": rule.match_account_clue,
        "set_account_id": rule.set_account_id,
        "set_merchant_canonical": rule.set_merchant_canonical,
        "set_category": rule.set_category,
        "set_purpose": rule.set_purpose,
        "enabled": rule.enabled,
        "source_metadata": rule.source_metadata,
        "created_at": serialize(rule.created_at),
        "updated_at": serialize(rule.updated_at),
    }


def validate_import_json(payload: dict[str, Any]) -> dict[str, Any]:
    version = payload.get("format_version")
    if version not in SUPPORTED_EXPORT_FORMAT_VERSIONS:
        raise HTTPException(status_code=422, detail="unsupported export format_version")

    required_sections: tuple[str, ...] = REQUIRED_IMPORT_SECTIONS
    if version == 1:
        required_sections = tuple(
            section for section in REQUIRED_IMPORT_SECTIONS if section != "user_rules"
        )
    missing = [
        section
        for section in required_sections
        if section not in payload or not isinstance(payload.get(section), list)
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"export JSON is missing required sections: {', '.join(missing)}",
        )

    raw_sms_messages = payload.get("raw_sms_messages", [])
    raw_sms_bodies_included = sum(
        1
        for raw_sms in raw_sms_messages
        if isinstance(raw_sms, dict)
        and raw_sms.get("body_exported") is True
        and "body" in raw_sms
    )
    warnings = []
    if version == 1:
        warnings.append("format_version 1 does not include user_rules")

    return {
        "valid": True,
        "format_version": version,
        "counts": {
            "accounts": len(payload.get("accounts", [])),
            "ledger_transactions": len(payload.get("ledger_transactions", [])),
            "raw_sms_messages": len(raw_sms_messages),
            "categories": len(payload.get("categories", [])),
            "audit_events": len(payload.get("audit_events", [])),
            "user_rules": len(payload.get("user_rules", [])),
        },
        "raw_sms_bodies_included": raw_sms_bodies_included,
        "warnings": warnings,
    }


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def sanitize_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: sanitize_csv_cell(value) for key, value in row.items()}


def sanitize_csv_cell(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value

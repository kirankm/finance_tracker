from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, Category, LedgerTransaction

VALIDATION_ERROR_STATUS = 422


class AccountCreatePayload(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    account_type: str = Field(min_length=1, max_length=40)
    balance_tracking: bool = False
    current_balance: str | None = None


class AccountUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    account_type: str | None = Field(default=None, min_length=1, max_length=40)
    balance_tracking: bool | None = None
    current_balance: str | None = None


class AccountListResponse(BaseModel):
    items: list[dict[str, Any]]


class CategoryCreatePayload(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    intent_type: str | None = Field(default=None, max_length=40)


class CategoryUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    intent_type: str | None = Field(default=None, max_length=40)


class DeletePayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class CategoryListResponse(BaseModel):
    items: list[dict[str, Any]]


def list_accounts(db_session: Session) -> AccountListResponse:
    accounts = db_session.scalars(select(Account).order_by(Account.id)).all()
    return AccountListResponse(items=[account_to_dict(account) for account in accounts])


def create_account(db_session: Session, payload: AccountCreatePayload) -> dict[str, Any]:
    if db_session.get(Account, payload.id) is not None:
        raise HTTPException(status_code=409, detail="account already exists")
    account = Account(
        id=payload.id,
        name=payload.name,
        account_type=payload.account_type,
        balance_tracking=payload.balance_tracking,
        current_balance=parse_optional_decimal(payload.current_balance),
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account_to_dict(account)


def update_account(
    db_session: Session, account_id: str, payload: AccountUpdatePayload
) -> dict[str, Any]:
    account = db_session.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    updates = payload.model_dump(exclude_unset=True)
    changes: dict[str, dict[str, Any]] = {}
    for field_name, value in updates.items():
        normalized = parse_optional_decimal(value) if field_name == "current_balance" else value
        before = getattr(account, field_name)
        setattr(account, field_name, normalized)
        changes[field_name] = {"before": serialize(before), "after": serialize(normalized)}
    if changes:
        db_session.add(
            AuditEvent(
                id=f"audit_{uuid4().hex}",
                account=account,
                actor_type="user",
                event_type="account_updated",
                field_changes=changes,
            )
        )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account_to_dict(account)


def list_categories(db_session: Session, include_deleted: bool) -> CategoryListResponse:
    categories = db_session.scalars(select(Category).order_by(Category.id)).all()
    return CategoryListResponse(
        items=[
            category_to_dict(category)
            for category in categories
            if include_deleted or category.deleted_at is None
        ]
    )


def create_category(db_session: Session, payload: CategoryCreatePayload) -> dict[str, Any]:
    if db_session.get(Category, payload.id) is not None:
        raise HTTPException(status_code=409, detail="category already exists")
    category = Category(id=payload.id, name=payload.name, intent_type=payload.intent_type)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category_to_dict(category)


def update_category(
    db_session: Session, category_id: str, payload: CategoryUpdatePayload
) -> dict[str, Any]:
    category = db_session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")
    updates = payload.model_dump(exclude_unset=True)
    changes: dict[str, dict[str, Any]] = {}
    for field_name, value in updates.items():
        before = getattr(category, field_name)
        setattr(category, field_name, value)
        changes[field_name] = {"before": serialize(before), "after": serialize(value)}
    if changes:
        db_session.add(
            AuditEvent(
                id=f"audit_{uuid4().hex}",
                actor_type="user",
                event_type="category_updated",
                field_changes={"category_id": category.id, **changes},
            )
        )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category_to_dict(category)


def delete_category(
    db_session: Session, category_id: str, payload: DeletePayload
) -> dict[str, Any]:
    category = db_session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")
    active_transaction = db_session.scalar(
        select(LedgerTransaction).where(
            LedgerTransaction.category == category_id,
            LedgerTransaction.deleted_at.is_(None),
        )
    )
    if active_transaction is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="category is used by active ledger transactions",
        )
    category.deleted_at = datetime.now(UTC)
    changes = {
        "category_id": category.id,
        "deleted_at": {"before": None, "after": serialize(category.deleted_at)},
        "deleted_reason": {"before": category.deleted_reason, "after": payload.reason},
    }
    category.deleted_reason = payload.reason
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            actor_type="user",
            event_type="category_deleted",
            field_changes=changes,
            reason=payload.reason,
        )
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category_to_dict(category)


def parse_optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS,
            detail="current_balance must be a decimal value",
        ) from exc


def account_to_dict(account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "name": account.name,
        "account_type": account.account_type,
        "balance_tracking": account.balance_tracking,
        "current_balance": serialize(account.current_balance),
        "deleted_at": serialize(account.deleted_at),
        "deleted_reason": account.deleted_reason,
    }


def category_to_dict(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "intent_type": category.intent_type,
        "deleted_at": serialize(category.deleted_at),
        "deleted_reason": category.deleted_reason,
    }


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value

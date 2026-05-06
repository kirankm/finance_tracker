from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, LedgerTransaction, RawSmsMessage, UserRule
from app.rules import UserApprovedRule

RULE_VALUE_FIELDS = {
    "account_id",
    "merchant_canonical",
    "category",
    "purpose",
}
RULE_UPDATE_FIELDS = {
    "name",
    "priority",
    "match_merchant_raw",
    "match_account_clue",
    "set_account_id",
    "set_merchant_canonical",
    "set_category",
    "set_purpose",
}


class RuleCandidateApprovePayload(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    updates: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class RuleCandidateActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class UserRuleUpdatePayload(BaseModel):
    updates: dict[str, Any] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=500)


class UserRuleActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


def list_rule_candidates(db_session: Session) -> dict[str, Any]:
    candidates = collect_rule_candidates(db_session)
    rejected_ids = rejected_candidate_ids(db_session)
    approved_ids = approved_candidate_ids(db_session)
    items = []
    for candidate in candidates:
        status_value = "candidate"
        if candidate["id"] in rejected_ids:
            status_value = "rejected"
        if candidate["id"] in approved_ids:
            status_value = "approved"
        items.append({**candidate, "status": status_value})
    return {"items": items, "total": len(items)}


def approve_rule_candidate(
    db_session: Session,
    candidate_id: str,
    payload: RuleCandidateApprovePayload,
) -> dict[str, Any]:
    if candidate_id in approved_candidate_ids(db_session):
        raise HTTPException(status_code=409, detail="rule candidate already approved")
    if candidate_id in rejected_candidate_ids(db_session):
        raise HTTPException(status_code=409, detail="rule candidate was rejected")
    candidate = find_rule_candidate(db_session, candidate_id)
    proposed_values = dict(candidate["proposed_values"])
    for field_name, value in payload.updates.items():
        if field_name not in RULE_VALUE_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=f"unsupported rule field: {field_name}",
            )
        proposed_values[field_name] = normalize_optional_string(value)

    match = dict(candidate["match"])
    if not match:
        raise HTTPException(status_code=422, detail="rule candidate has no match condition")
    if not any(value not in (None, "") for value in proposed_values.values()):
        raise HTTPException(status_code=422, detail="rule candidate has no values to apply")

    rule = UserRule(
        id=f"rule_{uuid4().hex}",
        name=payload.name or str(candidate["default_name"]),
        priority=10,
        match_merchant_raw=normalize_optional_string(match.get("merchant_raw")),
        match_account_clue=normalize_optional_string(match.get("account_clue")),
        set_account_id=normalize_optional_string(proposed_values.get("account_id")),
        set_merchant_canonical=normalize_optional_string(
            proposed_values.get("merchant_canonical")
        ),
        set_category=normalize_optional_string(proposed_values.get("category")),
        set_purpose=normalize_optional_string(proposed_values.get("purpose")),
        enabled=True,
        source_metadata={
            "source": "rule_candidate",
            "source_candidate_id": candidate_id,
            "source_type": candidate["source_type"],
            "source_id": candidate["source_id"],
            "approved_at": datetime.now(UTC).isoformat(),
        },
    )
    db_session.add(rule)
    db_session.flush()
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            actor_type="user",
            event_type="user_rule_approved",
            field_changes={
                "rule_id": rule.id,
                "source_candidate_id": candidate_id,
                "match": match,
                "set_values": proposed_values,
            },
            reason=payload.reason,
        )
    )
    db_session.commit()
    db_session.refresh(rule)
    return user_rule_to_dict(rule)


def reject_rule_candidate(
    db_session: Session,
    candidate_id: str,
    payload: RuleCandidateActionPayload,
) -> dict[str, Any]:
    if candidate_id in approved_candidate_ids(db_session):
        raise HTTPException(status_code=409, detail="rule candidate already approved")
    find_rule_candidate(db_session, candidate_id)
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            actor_type="user",
            event_type="rule_candidate_rejected",
            field_changes={"rule_candidate_id": candidate_id},
            reason=payload.reason,
        )
    )
    db_session.commit()
    return {"rule_candidate_id": candidate_id, "status": "rejected"}


def list_user_rules(db_session: Session, include_disabled: bool = True) -> dict[str, Any]:
    query = select(UserRule).order_by(UserRule.priority, UserRule.id)
    if not include_disabled:
        query = query.where(UserRule.enabled.is_(True))
    items = [user_rule_to_dict(rule) for rule in db_session.scalars(query)]
    return {"items": items, "total": len(items)}


def update_user_rule(
    db_session: Session, rule_id: str, payload: UserRuleUpdatePayload
) -> dict[str, Any]:
    rule = get_user_rule(db_session, rule_id)
    changes: dict[str, dict[str, Any]] = {}
    for field_name, value in payload.updates.items():
        if field_name not in RULE_UPDATE_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=f"unsupported user rule field: {field_name}",
            )
        normalized_value = normalize_rule_update_value(field_name, value)
        before = getattr(rule, field_name)
        if before == normalized_value:
            continue
        setattr(rule, field_name, normalized_value)
        changes[field_name] = {"before": before, "after": normalized_value}

    if changes:
        db_session.add(
            AuditEvent(
                id=f"audit_{uuid4().hex}",
                actor_type="user",
                event_type="user_rule_updated",
                field_changes={"rule_id": rule.id, "changes": changes},
                reason=payload.reason,
            )
        )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return user_rule_to_dict(rule)


def disable_user_rule(
    db_session: Session, rule_id: str, payload: UserRuleActionPayload
) -> dict[str, Any]:
    rule = get_user_rule(db_session, rule_id)
    before = rule.enabled
    rule.enabled = False
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            actor_type="user",
            event_type="user_rule_disabled",
            field_changes={"rule_id": rule.id, "enabled": {"before": before, "after": False}},
            reason=payload.reason,
        )
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return user_rule_to_dict(rule)


def load_enabled_user_approved_rules(db_session: Session) -> list[UserApprovedRule]:
    rules = db_session.scalars(
        select(UserRule)
        .where(UserRule.enabled.is_(True))
        .order_by(UserRule.priority, UserRule.id)
    )
    return [
        UserApprovedRule(
            rule_id=rule.id,
            match_merchant_raw=rule.match_merchant_raw,
            match_account_clue=rule.match_account_clue,
            set_account_id=rule.set_account_id,
            set_merchant_canonical=rule.set_merchant_canonical,
            set_category=rule.set_category,
            set_purpose=rule.set_purpose,
            priority=rule.priority,
        )
        for rule in rules
    ]


def collect_rule_candidates(db_session: Session) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for raw_sms in db_session.scalars(select(RawSmsMessage).order_by(RawSmsMessage.created_at)):
        candidate = candidate_from_mapping(
            source_type="raw_sms",
            source_id=raw_sms.id,
            data=dict(raw_sms.parser_output or {}),
        )
        if candidate is not None:
            candidates.append(candidate)
    for transaction in db_session.scalars(
        select(LedgerTransaction).order_by(LedgerTransaction.created_at)
    ):
        candidate = candidate_from_mapping(
            source_type="ledger_transaction",
            source_id=transaction.id,
            data={
                **dict(transaction.source_metadata or {}),
                "merchant_raw": transaction.merchant_raw,
            },
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def candidate_from_mapping(
    *, source_type: str, source_id: str, data: dict[str, Any]
) -> dict[str, Any] | None:
    rule_candidate = data.get("rule_candidate")
    if not isinstance(rule_candidate, dict):
        return None
    proposed_values = proposed_values_from_rule_candidate(rule_candidate)
    if not proposed_values:
        return None
    match = {
        "merchant_raw": data.get("merchant_raw"),
        "account_clue": data.get("account_clue"),
    }
    match = {key: value for key, value in match.items() if value not in (None, "")}
    candidate_id = stable_candidate_id(source_type, source_id, match, proposed_values)
    return {
        "id": candidate_id,
        "source_type": source_type,
        "source_id": source_id,
        "match": match,
        "proposed_values": proposed_values,
        "default_name": default_rule_name(match, proposed_values),
        "history_count": rule_candidate.get("history_count", 0),
    }


def proposed_values_from_rule_candidate(rule_candidate: dict[str, Any]) -> dict[str, Any]:
    fields = rule_candidate.get("fields", [])
    if not isinstance(fields, list):
        return {}
    proposed_values: dict[str, Any] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_name = field.get("field")
        if field_name in RULE_VALUE_FIELDS:
            proposed_values[str(field_name)] = field.get("value")
    return {key: value for key, value in proposed_values.items() if value not in (None, "")}


def find_rule_candidate(db_session: Session, candidate_id: str) -> dict[str, Any]:
    for candidate in collect_rule_candidates(db_session):
        if candidate["id"] == candidate_id:
            return candidate
    raise HTTPException(status_code=404, detail="rule candidate not found")


def rejected_candidate_ids(db_session: Session) -> set[str]:
    rejected = set()
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "rule_candidate_rejected")
    )
    for event in events:
        candidate_id = event.field_changes.get("rule_candidate_id")
        if isinstance(candidate_id, str):
            rejected.add(candidate_id)
    return rejected


def approved_candidate_ids(db_session: Session) -> set[str]:
    approved = set()
    for rule in db_session.scalars(select(UserRule)):
        candidate_id = dict(rule.source_metadata or {}).get("source_candidate_id")
        if isinstance(candidate_id, str):
            approved.add(candidate_id)
    return approved


def stable_candidate_id(
    source_type: str,
    source_id: str,
    match: dict[str, Any],
    proposed_values: dict[str, Any],
) -> str:
    digest_input = repr(
        (
            source_type,
            source_id,
            sorted(match.items()),
            sorted(proposed_values.items()),
        )
    )
    digest = sha256(digest_input.encode("utf-8")).hexdigest()
    return f"rule_candidate_{digest[:16]}"


def default_rule_name(match: dict[str, Any], proposed_values: dict[str, Any]) -> str:
    matched_value = match.get("merchant_raw") or match.get("account_clue") or "rule"
    category = proposed_values.get("category")
    if category:
        return f"{matched_value} -> {category}"
    return str(matched_value)


def get_user_rule(db_session: Session, rule_id: str) -> UserRule:
    rule = db_session.get(UserRule, rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user rule not found",
        )
    return rule


def normalize_rule_update_value(field_name: str, value: Any) -> Any:
    if field_name == "priority":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="priority must be an integer") from exc
    if field_name == "name":
        text = str(value).strip()
        if not text:
            raise HTTPException(status_code=422, detail="name must not be blank")
        return text
    return normalize_optional_string(value)


def normalize_optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


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
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }

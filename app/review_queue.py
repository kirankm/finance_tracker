from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RawSmsMessage

ReviewDecision = Literal["reviewed"]


class ReviewDecisionPayload(BaseModel):
    decision: ReviewDecision
    reason: str | None = Field(default=None, max_length=500)


class ReviewQueueItem(BaseModel):
    raw_sms_id: str
    external_message_id: str
    sender: str
    received_at: datetime
    source: str
    processing_status: str
    candidate: dict[str, Any]


class ReviewQueueDetail(ReviewQueueItem):
    body: str


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]


def list_pending_review_items(db_session: Session) -> ReviewQueueResponse:
    raw_messages = db_session.scalars(
        select(RawSmsMessage).order_by(RawSmsMessage.received_at, RawSmsMessage.id)
    ).all()
    return ReviewQueueResponse(
        items=[
            raw_sms_to_queue_item(raw_sms)
            for raw_sms in raw_messages
            if raw_sms.parser_output.get("review_status") == "needs_review"
        ]
    )


def get_review_item_detail(db_session: Session, raw_sms_id: str) -> ReviewQueueDetail:
    raw_sms = get_raw_sms_or_404(db_session, raw_sms_id)
    return raw_sms_to_queue_detail(raw_sms)


def mark_review_item_reviewed(
    db_session: Session,
    raw_sms_id: str,
    payload: ReviewDecisionPayload,
) -> ReviewQueueDetail:
    raw_sms = get_raw_sms_or_404(db_session, raw_sms_id)
    parser_output = dict(raw_sms.parser_output)
    parser_output["review_status"] = payload.decision
    parser_output["review_metadata"] = {
        "decision": payload.decision,
        "reason": payload.reason,
        "actor_type": "user",
        "reviewed_at": datetime.now(UTC).isoformat(),
    }
    raw_sms.parser_output = parser_output
    db_session.add(raw_sms)
    db_session.commit()
    db_session.refresh(raw_sms)
    return raw_sms_to_queue_detail(raw_sms)


def get_raw_sms_or_404(db_session: Session, raw_sms_id: str) -> RawSmsMessage:
    raw_sms = db_session.get(RawSmsMessage, raw_sms_id)
    if raw_sms is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="review item not found",
        )
    return raw_sms


def raw_sms_to_queue_item(raw_sms: RawSmsMessage) -> ReviewQueueItem:
    return ReviewQueueItem(
        raw_sms_id=raw_sms.id,
        external_message_id=raw_sms.external_message_id,
        sender=raw_sms.sender,
        received_at=raw_sms.received_at,
        source=raw_sms.source,
        processing_status=raw_sms.processing_status,
        candidate=raw_sms.parser_output,
    )


def raw_sms_to_queue_detail(raw_sms: RawSmsMessage) -> ReviewQueueDetail:
    item = raw_sms_to_queue_item(raw_sms)
    return ReviewQueueDetail(**item.model_dump(), body=raw_sms.body)

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from hashlib import sha256
from secrets import compare_digest
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.corrections import (
    CorrectionPayload,
    LedgerTransactionCorrectionResponse,
    correct_ledger_transaction,
    correct_review_candidate,
)
from app.database import get_db_session
from app.ledger_promotion import (
    LedgerPromotionPayload,
    LedgerPromotionResponse,
    promote_reviewed_sms_candidate,
)
from app.models import RawSmsMessage
from app.review_queue import (
    ReviewDecisionPayload,
    ReviewQueueDetail,
    ReviewQueueResponse,
    get_review_item_detail,
    list_pending_review_items,
    mark_review_item_reviewed,
)
from app.rules import enrich_candidate
from app.sms_parser import parse_sms

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

app = FastAPI(title=settings.app_name)


class InboundSmsPayload(BaseModel):
    message_id: str = Field(min_length=1, max_length=160)
    sender: str = Field(min_length=1, max_length=80)
    received_at: datetime
    body: str = Field(min_length=1)


class InboundSmsResponse(BaseModel):
    raw_sms_id: str
    processing_status: str
    candidate: dict[str, object]


class AndroidIncomeSmsWebhookPayload(BaseModel):
    sender: str = Field(alias="from", min_length=1, max_length=80)
    text: str = Field(min_length=1)
    sent_stamp: str | None = Field(default=None, alias="sentStamp")
    received_stamp: str = Field(alias="receivedStamp", min_length=1)
    sim: str | None = Field(default=None, max_length=40)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("received_stamp")
    @classmethod
    def received_stamp_must_be_epoch_milliseconds(cls, value: str) -> str:
        if not value.isdecimal():
            raise ValueError("receivedStamp must be epoch milliseconds")
        try:
            datetime.fromtimestamp(int(value) / 1000, tz=UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise ValueError("receivedStamp must be a valid epoch millisecond value") from exc
        return value

    def to_inbound_sms_payload(self) -> InboundSmsPayload:
        message_id = stable_forwarder_message_id(
            self.sender, self.text, self.received_stamp, self.sim
        )
        received_at = datetime.fromtimestamp(
            int(self.received_stamp) / 1000, tz=UTC
        )
        return InboundSmsPayload(
            message_id=message_id,
            sender=self.sender,
            received_at=received_at,
            body=self.text,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def is_authorized_inbound_sms_request(request: Request) -> bool:
    supplied_secret = request.headers.get("X-Inbound-SMS-Secret")
    return supplied_secret is not None and compare_digest(
        supplied_secret, settings.inbound_sms_secret
    )


@app.middleware("http")
async def require_inbound_sms_secret(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    protected_paths = {
        "/api/inbound-sms",
        "/api/forwarders/android-income-sms-webhook",
    }
    if (
        (
            request.url.path in protected_paths
            or request.url.path.startswith("/api/review-queue")
            or request.url.path.startswith("/api/ledger-transactions")
        )
        and not is_authorized_inbound_sms_request(request)
    ):
        return Response(
            content='{"detail":"unauthorized"}',
            status_code=status.HTTP_401_UNAUTHORIZED,
            media_type="application/json",
        )

    response = await call_next(request)
    return response


def stable_forwarder_message_id(
    sender: str, body: str, received_stamp: str, sim: str | None
) -> str:
    digest = sha256(
        "\n".join([sender, body, received_stamp, sim or ""]).encode("utf-8")
    ).hexdigest()
    return f"android_income_sms_webhook_{digest}"


def persist_inbound_sms(
    payload: InboundSmsPayload,
    response: Response,
    db_session: Session,
    *,
    source: str,
) -> InboundSmsResponse:
    existing_raw_sms = db_session.scalar(
        select(RawSmsMessage).where(RawSmsMessage.external_message_id == payload.message_id)
    )
    if existing_raw_sms is not None:
        response.status_code = status.HTTP_200_OK
        return InboundSmsResponse(
            raw_sms_id=existing_raw_sms.id,
            processing_status=existing_raw_sms.processing_status,
            candidate=existing_raw_sms.parser_output,
        )

    candidate = enrich_candidate(parse_sms(payload.body))
    parser_output = candidate.model_dump(exclude_none=True)
    raw_sms = RawSmsMessage(
        id=f"raw_sms_{uuid4().hex}",
        external_message_id=payload.message_id,
        sender=payload.sender,
        received_at=payload.received_at,
        body=payload.body,
        source=source,
        processing_status="candidate_created",
        parser_output=parser_output,
    )
    db_session.add(raw_sms)
    db_session.commit()

    return InboundSmsResponse(
        raw_sms_id=raw_sms.id,
        processing_status=raw_sms.processing_status,
        candidate=parser_output,
    )


@app.post(
    "/api/inbound-sms",
    response_model=InboundSmsResponse,
    status_code=status.HTTP_201_CREATED,
)
def receive_inbound_sms(
    payload: InboundSmsPayload,
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> InboundSmsResponse:
    return persist_inbound_sms(
        payload, response, db_session, source="external_forwarder"
    )


@app.post(
    "/api/forwarders/android-income-sms-webhook",
    response_model=InboundSmsResponse,
    status_code=status.HTTP_201_CREATED,
)
def receive_android_income_sms_webhook(
    payload: AndroidIncomeSmsWebhookPayload,
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> InboundSmsResponse:
    return persist_inbound_sms(
        payload.to_inbound_sms_payload(),
        response,
        db_session,
        source="android_income_sms_webhook",
    )


@app.get("/api/review-queue", response_model=ReviewQueueResponse)
def review_queue(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ReviewQueueResponse:
    return list_pending_review_items(db_session)


@app.get("/api/review-queue/{raw_sms_id}", response_model=ReviewQueueDetail)
def review_queue_detail(
    raw_sms_id: str,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ReviewQueueDetail:
    return get_review_item_detail(db_session, raw_sms_id)


@app.post("/api/review-queue/{raw_sms_id}/review", response_model=ReviewQueueDetail)
def review_queue_mark_reviewed(
    raw_sms_id: str,
    payload: ReviewDecisionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ReviewQueueDetail:
    return mark_review_item_reviewed(db_session, raw_sms_id, payload)


@app.patch(
    "/api/review-queue/{raw_sms_id}/corrections",
    response_model=ReviewQueueDetail,
)
def review_queue_correct_candidate(
    raw_sms_id: str,
    payload: CorrectionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ReviewQueueDetail:
    return correct_review_candidate(db_session, raw_sms_id, payload)


@app.post(
    "/api/review-queue/{raw_sms_id}/promote",
    response_model=LedgerPromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
def review_queue_promote_to_ledger(
    raw_sms_id: str,
    payload: LedgerPromotionPayload,
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> LedgerPromotionResponse:
    promotion_response, status_code = promote_reviewed_sms_candidate(
        db_session, raw_sms_id, payload
    )
    response.status_code = status_code
    return promotion_response


@app.patch(
    "/api/ledger-transactions/{transaction_id}/corrections",
    response_model=LedgerTransactionCorrectionResponse,
)
def ledger_transaction_correct(
    transaction_id: str,
    payload: CorrectionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> LedgerTransactionCorrectionResponse:
    return correct_ledger_transaction(db_session, transaction_id, payload)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": settings.app_name, "environment": settings.environment},
    )

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from secrets import compare_digest
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import AnalysisParams, get_analysis_summary
from app.cash_tracking import CashBalanceUpdatePayload, update_cash_balance
from app.config import get_settings
from app.corrections import (
    CorrectionPayload,
    LedgerTransactionCorrectionResponse,
    correct_ledger_transaction,
    correct_review_candidate,
)
from app.database import get_db_session
from app.export import export_json, export_ledger_csv, validate_import_json
from app.insights import (
    InsightActionPayload,
    InsightsParams,
    list_insights,
    mark_insight_dismissed,
    mark_insight_reviewed,
)
from app.ledger_promotion import (
    LedgerPromotionPayload,
    LedgerPromotionResponse,
    promote_reviewed_sms_candidate,
)
from app.ledger_search import LedgerSearchParams, search_ledger_transactions
from app.management import (
    AccountCreatePayload,
    AccountListResponse,
    AccountUpdatePayload,
    CategoryCreatePayload,
    CategoryListResponse,
    CategoryUpdatePayload,
    DeletePayload,
    create_account,
    create_category,
    delete_category,
    list_accounts,
    list_categories,
    update_account,
    update_category,
)
from app.manual_transactions import (
    ManualTransactionActionPayload,
    ManualTransactionCreatePayload,
    ManualTransactionUpdatePayload,
    create_manual_transaction,
    delete_manual_transaction,
    ignore_manual_transaction,
    mark_manual_transaction_duplicate,
    restore_manual_transaction,
    update_manual_transaction,
)
from app.models import RawSmsMessage
from app.operational_readiness import operational_readiness
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
from app.user_rules import (
    RuleCandidateActionPayload,
    RuleCandidateApprovePayload,
    UserRuleActionPayload,
    UserRuleUpdatePayload,
    approve_rule_candidate,
    disable_user_rule,
    list_rule_candidates,
    list_user_rules,
    load_enabled_user_approved_rules,
    reject_rule_candidate,
    update_user_rule,
)

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
            or request.url.path.startswith("/api/analysis")
            or request.url.path.startswith("/api/insights")
            or request.url.path.startswith("/api/ledger-transactions")
            or request.url.path.startswith("/api/manual-transactions")
            or request.url.path.startswith("/api/rule-candidates")
            or request.url.path.startswith("/api/user-rules")
            or request.url.path.startswith("/api/export")
            or request.url.path.startswith("/api/import")
            or request.url.path.startswith("/api/ops")
            or request.url.path.startswith("/api/accounts")
            or request.url.path.startswith("/api/categories")
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

    candidate = enrich_candidate(
        parse_sms(payload.body),
        user_rules=load_enabled_user_approved_rules(db_session),
    )
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


@app.get("/api/ledger-transactions")
def ledger_transactions_search(
    db_session: Annotated[Session, Depends(get_db_session)],
    id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: str | None = None,
    transaction_type: str | None = None,
    purpose: str | None = None,
    category: str | None = None,
    merchant: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    review_status: str | None = None,
    duplicate_status: str | None = None,
    ledger_status: str | None = None,
    source: str | None = None,
    include_deleted: bool = False,
    sort_by: str = "transaction_date",
    sort_dir: str = "desc",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return search_ledger_transactions(
        db_session,
        LedgerSearchParams(
            transaction_id=id,
            date_from=date_from,
            date_to=date_to,
            account_id=account_id,
            transaction_type=transaction_type,
            purpose=purpose,
            category=category,
            merchant=merchant,
            amount_min=amount_min,
            amount_max=amount_max,
            review_status=review_status,
            duplicate_status=duplicate_status,
            ledger_status=ledger_status,
            source=source,
            include_deleted=include_deleted,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        ),
    )


@app.get("/api/analysis/summary")
def analysis_summary(
    db_session: Annotated[Session, Depends(get_db_session)],
    month: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, object]:
    return get_analysis_summary(
        db_session,
        AnalysisParams(month=month, date_from=date_from, date_to=date_to),
    )


@app.get("/api/insights")
def insights_list(
    db_session: Annotated[Session, Depends(get_db_session)],
    month: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_dismissed: bool = False,
    include_reviewed: bool = False,
) -> dict[str, object]:
    return list_insights(
        db_session,
        InsightsParams(
            month=month,
            date_from=date_from,
            date_to=date_to,
            include_dismissed=include_dismissed,
            include_reviewed=include_reviewed,
        ),
    )


@app.post("/api/insights/{insight_id}/dismiss")
def insights_dismiss(
    insight_id: str,
    payload: InsightActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return mark_insight_dismissed(db_session, insight_id, payload)


@app.post("/api/insights/{insight_id}/review")
def insights_review(
    insight_id: str,
    payload: InsightActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return mark_insight_reviewed(db_session, insight_id, payload)


@app.get("/api/rule-candidates")
def rule_candidates_list(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return list_rule_candidates(db_session)


@app.post("/api/rule-candidates/{candidate_id}/approve", status_code=status.HTTP_201_CREATED)
def rule_candidates_approve(
    candidate_id: str,
    payload: RuleCandidateApprovePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return approve_rule_candidate(db_session, candidate_id, payload)


@app.post("/api/rule-candidates/{candidate_id}/reject")
def rule_candidates_reject(
    candidate_id: str,
    payload: RuleCandidateActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return reject_rule_candidate(db_session, candidate_id, payload)


@app.get("/api/user-rules")
def user_rules_list(
    db_session: Annotated[Session, Depends(get_db_session)],
    include_disabled: bool = True,
) -> dict[str, object]:
    return list_user_rules(db_session, include_disabled=include_disabled)


@app.patch("/api/user-rules/{rule_id}")
def user_rules_update(
    rule_id: str,
    payload: UserRuleUpdatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return update_user_rule(db_session, rule_id, payload)


@app.post("/api/user-rules/{rule_id}/disable")
def user_rules_disable(
    rule_id: str,
    payload: UserRuleActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return disable_user_rule(db_session, rule_id, payload)


@app.post("/api/manual-transactions", status_code=status.HTTP_201_CREATED)
def manual_transactions_create(
    payload: ManualTransactionCreatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return create_manual_transaction(db_session, payload)


@app.patch("/api/manual-transactions/{transaction_id}")
def manual_transactions_update(
    transaction_id: str,
    payload: ManualTransactionUpdatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return update_manual_transaction(db_session, transaction_id, payload)


@app.post("/api/manual-transactions/{transaction_id}/ignore")
def manual_transactions_ignore(
    transaction_id: str,
    payload: ManualTransactionActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return ignore_manual_transaction(db_session, transaction_id, payload)


@app.post("/api/manual-transactions/{transaction_id}/mark-duplicate")
def manual_transactions_mark_duplicate(
    transaction_id: str,
    payload: ManualTransactionActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return mark_manual_transaction_duplicate(db_session, transaction_id, payload)


@app.delete("/api/manual-transactions/{transaction_id}")
def manual_transactions_delete(
    transaction_id: str,
    payload: ManualTransactionActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return delete_manual_transaction(db_session, transaction_id, payload)


@app.post("/api/manual-transactions/{transaction_id}/restore")
def manual_transactions_restore(
    transaction_id: str,
    payload: ManualTransactionActionPayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return restore_manual_transaction(db_session, transaction_id, payload)


@app.get("/api/export/json")
def export_json_data(
    db_session: Annotated[Session, Depends(get_db_session)],
    include_raw_sms_body: bool = False,
) -> dict[str, object]:
    return export_json(db_session, include_raw_sms_body=include_raw_sms_body)


@app.post("/api/import/json/validate")
def import_json_validate(payload: dict[str, object]) -> dict[str, object]:
    return validate_import_json(payload)


@app.get("/api/ops/readiness")
def ops_readiness() -> dict[str, object]:
    return operational_readiness(settings)


@app.get("/api/export/ledger-transactions.csv")
def export_ledger_transactions_csv(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    return export_ledger_csv(db_session)


@app.get("/api/accounts", response_model=AccountListResponse)
def accounts_list(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AccountListResponse:
    return list_accounts(db_session)


@app.post("/api/accounts", status_code=status.HTTP_201_CREATED)
def accounts_create(
    payload: AccountCreatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return create_account(db_session, payload)


@app.patch("/api/accounts/{account_id}")
def accounts_update(
    account_id: str,
    payload: AccountUpdatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return update_account(db_session, account_id, payload)


@app.post("/api/accounts/{account_id}/cash-balance")
def accounts_update_cash_balance(
    account_id: str,
    payload: CashBalanceUpdatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return update_cash_balance(db_session, account_id, payload)


@app.get("/api/categories", response_model=CategoryListResponse)
def categories_list(
    db_session: Annotated[Session, Depends(get_db_session)],
    include_deleted: bool = False,
) -> CategoryListResponse:
    return list_categories(db_session, include_deleted)


@app.post("/api/categories", status_code=status.HTTP_201_CREATED)
def categories_create(
    payload: CategoryCreatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return create_category(db_session, payload)


@app.patch("/api/categories/{category_id}")
def categories_update(
    category_id: str,
    payload: CategoryUpdatePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return update_category(db_session, category_id, payload)


@app.delete("/api/categories/{category_id}")
def categories_delete(
    category_id: str,
    payload: DeletePayload,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, object]:
    return delete_category(db_session, category_id, payload)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": settings.app_name, "environment": settings.environment},
    )

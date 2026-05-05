from collections.abc import Awaitable, Callable
from datetime import datetime
from secrets import compare_digest
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_session
from app.models import RawSmsMessage
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
    if request.url.path == "/api/inbound-sms" and not is_authorized_inbound_sms_request(
        request
    ):
        return Response(
            content='{"detail":"unauthorized"}',
            status_code=status.HTTP_401_UNAUTHORIZED,
            media_type="application/json",
        )

    response = await call_next(request)
    return response


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

    candidate = parse_sms(payload.body)
    parser_output = candidate.model_dump(exclude_none=True)
    raw_sms = RawSmsMessage(
        id=f"raw_sms_{uuid4().hex}",
        external_message_id=payload.message_id,
        sender=payload.sender,
        received_at=payload.received_at,
        body=payload.body,
        source="external_forwarder",
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": settings.app_name, "environment": settings.environment},
    )

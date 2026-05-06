from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app


@contextmanager
def make_test_client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = testing_session_local()

    def override_get_db_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_home_page_renders_review_ui_without_shared_secret() -> None:
    with make_test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "Review Queue" in html
    assert "data-testid=\"review-shell\"" in html
    assert "change-me-in-development" not in html
    assert "X-Inbound-SMS-Secret" in html


def test_review_ui_wires_existing_authenticated_api_actions() -> None:
    with make_test_client() as client:
        response = client.get("/")

    html = response.text
    assert "/api/review-queue" in html
    assert "/corrections" in html
    assert "/review" in html
    assert "/promote" in html
    assert "merchant_canonical" in html
    assert "category" in html
    assert "purpose" in html
    assert "transaction_date" in html
    assert "ledger_sanity_status" in html


def test_review_ui_keeps_raw_sms_in_detail_region_not_list_template() -> None:
    with make_test_client() as client:
        response = client.get("/")

    html = response.text
    list_region = html.split('data-testid="queue-list"', maxsplit=1)[1].split(
        'data-testid="detail-panel"', maxsplit=1
    )[0]
    detail_region = html.split('data-testid="detail-panel"', maxsplit=1)[1]
    assert "rawBody" not in list_region
    assert "Raw SMS" not in list_region
    assert "rawBody" in detail_region
    assert "Raw SMS" in detail_region

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


def test_review_ui_tracks_original_values_and_submits_only_changed_corrections() -> None:
    with make_test_client() as client:
        response = client.get("/")

    html = response.text
    assert "originalCorrectionValues" in html
    assert "value && value !== originalValue" in html


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


def test_review_ui_exposes_structured_ledger_search_filters() -> None:
    with make_test_client() as client:
        response = client.get("/")

    html = response.text
    search_region = html.split('data-testid="ledger-search-panel"', maxsplit=1)[1].split(
        "</section>", maxsplit=1
    )[0]
    assert "/api/ledger-transactions" in html
    assert "ledgerDateFrom" in search_region
    assert "ledgerDateTo" in search_region
    assert "ledgerAccount" in search_region
    assert "ledgerTransactionType" in search_region
    assert "ledgerPurpose" in search_region
    assert "ledgerCategory" in search_region
    assert "ledgerMerchant" in search_region
    assert "ledgerAmountMin" in search_region
    assert "ledgerReviewStatus" in search_region
    assert "ledgerDuplicateStatus" in search_region
    assert "ledgerLedgerStatus" in search_region
    assert "ledgerSource" in search_region
    assert "ledgerIncludeDeleted" in search_region
    assert "rawBody" not in search_region


def test_review_ui_exposes_analysis_panel() -> None:
    with make_test_client() as client:
        response = client.get("/")

    html = response.text
    analysis_region = html.split('data-testid="analysis-panel"', maxsplit=1)[1].split(
        "</section>", maxsplit=1
    )[0]
    assert "/api/analysis/summary" in html
    assert "analysisMonth" in analysis_region
    assert "analysisDateFrom" in analysis_region
    assert "analysisDateTo" in analysis_region
    assert "loadAnalysis" in analysis_region
    assert "analysisResults" in analysis_region
    assert "rawBody" not in analysis_region

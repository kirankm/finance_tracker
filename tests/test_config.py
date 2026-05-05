import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_default_development_values() -> None:
    settings = Settings()

    assert settings.app_name == "Automated SMS Expense Tracker"
    assert settings.environment == "development"
    assert settings.database_url == "sqlite:///./data/finance_tracker.db"


def test_inbound_sms_secret_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        Settings(inbound_sms_secret="   ")

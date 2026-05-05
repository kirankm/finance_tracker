from pathlib import Path
from typing import Any

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


def test_production_rejects_development_inbound_sms_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", inbound_sms_secret="change-me-in-development")


def test_settings_ignore_unrelated_deployment_dotenv_values(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("CADDY_DOMAIN=daily-expense.duckdns.org\n", encoding="utf-8")

    settings_kwargs: dict[str, Any] = {"_env_file": dotenv_path}
    settings = Settings(**settings_kwargs)

    assert settings.environment == "development"

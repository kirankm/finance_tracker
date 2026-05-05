from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Automated SMS Expense Tracker"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./data/finance_tracker.db"
    inbound_sms_secret: str = Field(default="change-me-in-development", min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("inbound_sms_secret")
    @classmethod
    def inbound_sms_secret_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("inbound_sms_secret must not be blank")
        return value

    @model_validator(mode="after")
    def production_must_not_use_development_inbound_sms_secret(self) -> Self:
        if (
            self.environment == "production"
            and self.inbound_sms_secret == "change-me-in-development"
        ):
            raise ValueError(
                "production inbound_sms_secret must not use the development default"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

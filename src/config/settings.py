"""
Central configuration for Multi-Agent RevOps Orchestrator.

Uses pydantic-settings for type-safe environment variable loading.
All secrets and runtime configuration live here.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Anthropic Claude (Primary LLM)
    # -------------------------------------------------------------------------
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL")
    claude_max_tokens: int = Field(default=4096, alias="CLAUDE_MAX_TOKENS")
    claude_temperature: float = Field(default=0.2, alias="CLAUDE_TEMPERATURE")

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(..., alias="DATABASE_URL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # -------------------------------------------------------------------------
    # Redis (for LangGraph checkpointing + cross-run state)
    # -------------------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_ttl_seconds: int = Field(default=86400, alias="REDIS_TTL_SECONDS")

    # -------------------------------------------------------------------------
    # WhatsApp Cloud API (Router Agent)
    # -------------------------------------------------------------------------
    whatsapp_access_token: str | None = Field(default=None, alias="WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id: str | None = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_business_account_id: str | None = Field(default=None, alias="WHATSAPP_BUSINESS_ACCOUNT_ID")
    whatsapp_api_version: str = Field(default="v21.0", alias="WHATSAPP_API_VERSION")
    whatsapp_recipient_phone: str | None = Field(default=None, alias="WHATSAPP_RECIPIENT_PHONE")
    whatsapp_enabled: bool = Field(default=True, alias="WHATSAPP_ENABLED")

    # -------------------------------------------------------------------------
    # SMTP / Email (Router Agent)
    # -------------------------------------------------------------------------
    smtp_host: str = Field(default="smtp.sendgrid.net", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="apikey", alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="revops@yourcompany.com", alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="RevOps Intelligence", alias="SMTP_FROM_NAME")
    smtp_to_emails: str = Field(default="founder@company.com", alias="SMTP_TO_EMAILS")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    email_enabled: bool = Field(default=True, alias="EMAIL_ENABLED")

    # -------------------------------------------------------------------------
    # Scheduler
    # -------------------------------------------------------------------------
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    scheduler_timezone: str = Field(default="Asia/Kolkata", alias="SCHEDULER_TIMEZONE")
    scheduler_weekly_cron: str = Field(default="0 9 * * MON", alias="SCHEDULER_WEEKLY_CRON")

    # -------------------------------------------------------------------------
    # FastAPI
    # -------------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_reload: bool = Field(default=False, alias="API_RELOAD")
    api_title: str = Field(default="Multi-Agent RevOps Orchestrator", alias="API_TITLE")
    api_version: str = Field(default="1.0.0", alias="API_VERSION")

    # -------------------------------------------------------------------------
    # Logging & Runtime
    # -------------------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    max_scraper_retries: int = Field(default=2, alias="MAX_SCRAPER_RETRIES")
    enable_state_logging: bool = Field(default=True, alias="ENABLE_STATE_LOGGING")

    # -------------------------------------------------------------------------
    # Computed / Derived Settings
    # -------------------------------------------------------------------------

    @computed_field  # type: ignore[misc]
    @property
    def smtp_to_email_list(self) -> List[str]:
        """Parse comma-separated SMTP_TO_EMAILS into list."""
        return [e.strip() for e in self.smtp_to_emails.split(",") if e.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def is_whatsapp_configured(self) -> bool:
        return bool(
            self.whatsapp_access_token
            and self.whatsapp_phone_number_id
            and self.whatsapp_recipient_phone
        )

    @computed_field  # type: ignore[misc]
    @property
    def is_email_configured(self) -> bool:
        return bool(self.smtp_password)

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        return not self.demo_mode

    @field_validator("claude_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("claude_temperature must be between 0.0 and 1.0")
        return v

    @field_validator("whatsapp_recipient_phone")
    @classmethod
    def validate_whatsapp_phone(cls, v: str | None) -> str | None:
        if v and not v.startswith("+"):
            raise ValueError("WHATSAPP_RECIPIENT_PHONE must be in E.164 format (e.g. +14155552671)")
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Call get_settings() everywhere."""
    return Settings()


# Convenience for scripts
settings = get_settings()

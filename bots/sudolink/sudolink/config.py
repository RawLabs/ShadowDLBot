"Application settings loaded from environment variables."

from __future__ import annotations

import os

from pydantic import BaseModel, Field, field_validator

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.6422.76 Safari/537.36"
)


class Settings(BaseModel):
    telegram_bot_token: str = Field(..., description="Telegram Bot API token")
    openai_api_key: str = Field(..., description="API key for OpenAI responses")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    max_results: int = Field(default=4, ge=1, le=8)
    insight_limit: int = Field(
        default=3, ge=0, le=6, description="Number of insight bullets to generate"
    )
    http_timeout: float = Field(default=12.0, description="Seconds for HTTP calls")
    log_level: str = Field(default="INFO")
    # Some publishers throttle or outright block obviously automated UA strings.
    # Pretend to be a mainstream browser by default so metadata fetches succeed.
    user_agent: str = Field(default=DEFAULT_USER_AGENT)

    model_config = {"extra": "ignore"}

    @field_validator("telegram_bot_token")
    def _validate_token(cls, value: str) -> str:
        if not value or value.isspace():
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        return value

    @field_validator("openai_api_key")
    def _validate_openai_api_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("SUDOLINK_OPENAI_API_KEY (or OPENAI_API_KEY) is required")
        return value.strip()

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            telegram_bot_token=_env_first(
                "SUDOLINK_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", default=""
            ),
            openai_api_key=_env_first(
                "SUDOLINK_OPENAI_API_KEY", "OPENAI_API_KEY", default=""
            ),
            openai_model=os.getenv("SUDOLINK_OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
            max_results=int(os.getenv("SUDOLINK_RESULT_LIMIT", os.getenv("RESULT_LIMIT", "4"))),
            insight_limit=int(
                os.getenv("SUDOLINK_INSIGHT_LIMIT", os.getenv("INSIGHT_LIMIT", "3"))
            ),
            http_timeout=float(
                os.getenv("SUDOLINK_REQUEST_TIMEOUT", os.getenv("REQUEST_TIMEOUT", "12"))
            ),
            log_level=os.getenv("SUDOLINK_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")),
            user_agent=os.getenv("SUDOLINK_USER_AGENT", os.getenv("USER_AGENT", DEFAULT_USER_AGENT)),
        )


def _env_first(*keys: str, default: str | None = None) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default

"""Application settings and configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra='ignore'  # Ignore extra env vars not defined in model
    )

    # LLM Configuration
    OPENAI_API_KEY: str
    LLM_MODEL: str = "gpt-4o-mini"  # or "gpt-4o-mini", "gpt-4-turbo"
    LLM_TEMPERATURE: float = 1.0
    LLM_MAX_TOKENS: int = 4096

    # Checkpointer Configuration
    CHECKPOINTER_TYPE: Literal["memory", "postgres", "redis"] = "memory"
    POSTGRES_CHECKPOINTER_URL: str | None = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Taxi Customer Support API"
    DEBUG: bool = True

    # Database Configuration (optional for MVP)
    DATABASE_URL: str = "sqlite:///./taxi.db"

    # Customer API Configuration
    CUSTOMER_API_BASE_URL: str = "https://s3xzbvdt-4021.use2.devtunnels.ms"


settings = Settings()

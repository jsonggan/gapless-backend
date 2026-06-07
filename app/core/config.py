"""Application settings and configuration."""

from typing import Literal

from pydantic import AnyHttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/gapless"
    REDIS_URL: str = "redis://localhost:6379/0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False

    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    # LLM (Kimi / OpenAI-compatible)
    KIMI_API_KEY: str | None = None
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-latest"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Return the SQLAlchemy database URI."""
        return self.DATABASE_URL

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_development(self) -> bool:
        """Return True if running in development mode."""
        return self.APP_ENV == "development"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        """Return True if running in production mode."""
        return self.APP_ENV == "production"


settings = Settings()

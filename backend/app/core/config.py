"""Application configuration.

All configurable values are read from environment variables so that no
secret or environment-specific value is hard-coded in the source tree.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from the environment (or a local .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Application -----------------------------------------------------
    app_name: str = "SME Financial Health Monitoring Dashboard"
    environment: str = "development"
    api_prefix: str = "/api"

    # ---- Database --------------------------------------------------------
    postgres_user: str = "fyp_user"
    postgres_password: str = "change_me"
    postgres_db: str = "fyp_financial_health"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    # ---- Authentication --------------------------------------------------
    jwt_secret_key: str = "development-only-secret-do-not-use-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ---- CORS ------------------------------------------------------------
    cors_origins: str = "http://localhost:5173"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return the database URL, assembling it from parts if not given."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, from the comma-separated env value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance, so the environment is read once."""
    return Settings()


settings = get_settings()

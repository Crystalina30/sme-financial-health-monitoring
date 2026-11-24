"""Application configuration.

All configurable values are read from environment variables so that no
secret or environment-specific value is hard-coded in the source tree.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Values that must never be used in production.
_DEVELOPMENT_SECRETS = {"development-only-secret-do-not-use-in-production", "change_me", ""}


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

    @model_validator(mode="after")
    def refuse_unsafe_production_settings(self) -> "Settings":
        """In production, refuse to start with development secrets.

        A JWT secret must be at least 32 characters and not a known default;
        the database password must not be the default either.
        """
        if not self.is_production:
            return self
        problems = []
        if self.jwt_secret_key in _DEVELOPMENT_SECRETS or len(self.jwt_secret_key) < 32:
            problems.append("JWT_SECRET_KEY must be set to a random value of 32+ characters")
        if self.postgres_password in _DEVELOPMENT_SECRETS and not self.database_url:
            problems.append("POSTGRES_PASSWORD must be changed from the default")
        if any("*" in origin for origin in self.cors_origin_list):
            problems.append("CORS_ORIGINS must list exact origins, not a wildcard")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems) + ".")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance, so the environment is read once."""
    return Settings()


settings = get_settings()

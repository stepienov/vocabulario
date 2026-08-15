from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Railway/Postgres dają postgres(ql)://; SQLAlchemy async potrzebuje +asyncpg."""
    value = (url or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql+asyncpg://" + value[len("postgres://") :]
    elif value.startswith("postgresql://"):
        value = "postgresql+asyncpg://" + value[len("postgresql://") :]
    # asyncpg używa ssl= zamiast libpq sslmode=
    value = value.replace("sslmode=", "ssl=")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    # Railway wstrzykuje PORT
    api_port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT", "PORT"))
    allowed_origins: str = "http://localhost:3000,http://10.0.2.2:8000"

    database_url: str = (
        "postgresql+asyncpg://vocabulario:vocabulario_dev@localhost:5432/vocabulario"
    )
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_database_url(value)
        return value

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    openai_api_key: str = ""
    llm_provider: str = "openai"
    llm_lookup_model: str = "gpt-5.6-terra"
    llm_enrichment_model: str = "gpt-5.6-terra"
    # Per-task override for preserve layout analysis (empty → llm_lookup_model).
    llm_import_layout_model: str = ""
    llm_import_provider: str = "openai"  # openai | anthropic
    anthropic_api_key: str = ""
    llm_mock: bool = False
    llm_rate_limit_per_minute: int = 20
    llm_max_retries: int = 2

    # Zapis lexical_entries + learning_cards do Postgres (wyłączone = tylko podgląd AI)
    persist_words: bool = False

    google_oauth_client_id: str = ""
    google_oauth_client_id_android: str = ""
    google_oauth_client_secret: str = ""

    # FCM legacy server key (optional; push helpers no-op when empty)
    fcm_server_key: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def google_client_ids(self) -> list[str]:
        ids = []
        for value in (self.google_oauth_client_id, self.google_oauth_client_id_android):
            if value:
                ids.append(value)
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()

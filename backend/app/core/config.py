from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

KNOWN_ENVIRONMENTS = frozenset({"development", "test", "staging", "beta", "production"})
DEPLOYED_ENVIRONMENTS = frozenset({"staging", "beta", "production"})
_DEFAULT_JWT_SECRET = "change-me"
_MIN_JWT_SECRET_CHARS = 32
JWT_ALGORITHM = "HS256"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "10.0.2.2"})


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

    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    # Fernet key for the 5-minute refresh retry results; never the JWT secret.
    auth_refresh_retry_key: str = ""

    openai_api_key: str = ""
    llm_provider: str = "openai"
    llm_lookup_model: str = "gpt-5.6-terra"
    llm_enrichment_model: str = "gpt-5.6-terra"
    # Tańszy model na proste kroki (dystraktory, fallback examples).
    llm_light_model: str = "gpt-5.6-luna"
    llm_import_layout_model: str = ""
    llm_import_provider: str = "openai"  # openai | anthropic
    anthropic_api_key: str = ""
    llm_mock: bool = False
    llm_rate_limit_per_minute: int = 20
    llm_max_retries: int = 2
    # Surowy JSON request/response LLM do debugowania (osobna tabela, nie app_logs).
    llm_store_payloads: bool = True
    llm_payload_ttl_days: int = 30

    # User-Agent wymagany przez Wikimedia (Wikisłownik).
    wikimedia_user_agent: str = (
        "Vocabulario/1.0 (https://github.com/stepienov/vocabulario; wiktionary-lookup)"
    )

    # Zapis lexical_entries + learning_cards do Postgres (wyłączone = tylko podgląd AI)
    persist_words: bool = False

    google_oauth_client_id: str = ""
    google_oauth_client_id_android: str = ""
    google_oauth_client_secret: str = ""

    # FCM legacy server key (optional; push helpers no-op when empty)
    fcm_server_key: str = ""

    admin_username: str = ""
    admin_password: str = ""
    admin_cookie_secret: str = ""

    @property
    def panel_enabled(self) -> bool:
        return bool((self.admin_username or "").strip() and (self.admin_password or "").strip())

    @property
    def panel_cookie_secret(self) -> str:
        return (self.admin_cookie_secret or "").strip() or self.jwt_secret

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

    @property
    def is_deployed(self) -> bool:
        return self.environment in DEPLOYED_ENVIRONMENTS

    def deployment_errors(self) -> list[str]:
        """Names of invalid settings; never their values.

        Local environments accept dev defaults; staging/beta/production must not.
        """
        if self.environment not in KNOWN_ENVIRONMENTS:
            return ["environment"]
        if not self.is_deployed:
            return []
        errors: list[str] = []
        if self.debug:
            errors.append("debug")
        secret = self.jwt_secret or ""
        if secret == _DEFAULT_JWT_SECRET or len(secret) < _MIN_JWT_SECRET_CHARS:
            errors.append("jwt_secret")
        if self.jwt_algorithm != JWT_ALGORITHM:
            errors.append("jwt_algorithm")
        if not self._token_periods_valid():
            errors.append("token_expiry")
        if not _is_fernet_key(self.auth_refresh_retry_key) or (
            self.auth_refresh_retry_key.strip() == secret.strip()
        ):
            errors.append("auth_refresh_retry_key")
        if not _is_remote_database(self.database_url):
            errors.append("database_url")
        if not all(_is_public_https_origin(origin) for origin in self.cors_origins):
            errors.append("allowed_origins")
        if not self.google_client_ids:
            errors.append("google_oauth_client_id")
        if self.llm_mock:
            errors.append("llm_mock")
        elif not self.openai_api_key.strip():
            errors.append("openai_api_key")
        import_provider = (self.llm_import_provider or "openai").strip().lower()
        if import_provider == "anthropic" and not self.anthropic_api_key.strip():
            errors.append("anthropic_api_key")
        return errors

    def _token_periods_valid(self) -> bool:
        access = self.access_token_expire_minutes
        refresh_minutes = self.refresh_token_expire_days * 24 * 60
        return 0 < access < refresh_minutes


def _is_fernet_key(value: str) -> bool:
    key = (value or "").strip()
    if not key:
        return False
    from cryptography.fernet import Fernet

    try:
        Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False
    return True


def _is_remote_database(url: str) -> bool:
    try:
        parsed = make_url(url)
    except ArgumentError:
        return False
    return bool(parsed.host) and parsed.host.lower() not in _LOCAL_HOSTS


def _is_public_https_origin(origin: str) -> bool:
    parts = urlsplit(origin)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and bool(host) and host not in _LOCAL_HOSTS


@lru_cache
def get_settings() -> Settings:
    return Settings()

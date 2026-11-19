from decimal import Decimal
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

    # Account e-mail (E-001/F-004/T-002). `log` only prints locally; deployed needs `resend`.
    public_app_origin: str = ""
    mail_transport: str = "log"
    mail_from: str = ""
    mail_reply_to: str = ""
    resend_api_key: str = ""
    # Separate Fernet key for queued mail payloads; never the JWT or refresh retry key.
    mail_outbox_key: str = ""
    # HMAC key for rate-limit subjects (>= 32 chars, separate from every other secret).
    auth_rate_limit_key: str = ""
    # Proxies in front of the API; the client IP is the Nth entry from the right of
    # X-Forwarded-For. 0 means no trusted proxy and the socket peer is used.
    trusted_proxy_hops: int = 0
    # Svix signing secret (`whsec_...`) of the Resend webhook; without it the endpoint answers 503.
    resend_webhook_secret: str = ""
    # Learning API refuses accounts without a proven address. Switch on only after the
    # Android release with the verification screens is out (T-002, release order of F-003).
    email_verification_gate: bool = False
    # PUT /profiles/{id} bez expected_revision (legacy) jest dozwolony do przełączenia minimalnej
    # wersji klienta (E-001/F-002/T-001); potem brak pola to 422, nie zapis w ciemno.
    profile_update_requires_revision: bool = False
    # Minimal Android versionCode (E-001/F-002/T-001). 0 = no gate. Above 0 every /api/v1 call except
    # the public legal/deletion/link-confirmation routes must send a sufficient `X-App-Version-Code`,
    # otherwise 426 `app_update_required`. Raise it only after the newer Play release is out.
    min_app_version_code: int = 0
    # Play listing opened by the "update" button; required while the gate is on.
    app_update_url: str = ""
    # Account deletion (E-001/F-006/T-002). Requests are refused until the flag is on; the
    # HMAC key (>= 32 chars) pseudonymises the user id in the kept process record and must
    # outlive ordinary deploys, so it is never rotated casually or reused as another secret.
    account_deletion_enabled: bool = False
    account_erasure_key: str = ""
    account_erasure_key_version: int = 1
    # Terms/privacy (E-001/F-007/T-003). Off: register records an acceptance when sent but old
    # clients still work; on: new accounts must send it and accounts without one get 403
    # `terms_acceptance_required` on learning routes. Switch on with the Android release.
    legal_acceptance_enforced: bool = False
    # Public identity of the operator and the monitored support address shown on the public pages.
    operator_name: str = ""
    support_email: str = ""
    # Digital Asset Links for the Android app (comma separated SHA-256 certificate fingerprints).
    android_package: str = "com.vocabulario.app"
    android_cert_sha256: str = ""
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
    # Diagnostic copies of prompts/answers, query and lemma in telemetry: off for real beta data.
    llm_store_payloads: bool = False
    llm_payload_ttl_days: int = 30
    app_log_retention_days: int = 7
    llm_usage_retention_days: int = 30

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

    # AI spend cap (E-001/F-008/T-004), USD per UTC month. WARN raises alerts only; HARD stops new
    # paid calls. Deployed environments must set both (HARD >= WARN > 0): 0/empty never means
    # "unlimited" there. Local environments with both at 0 skip the counter.
    ai_monthly_warn_usd: Decimal = Decimal("0")
    ai_monthly_hard_usd: Decimal = Decimal("0")
    # Where operator alerts go; falls back to the public support address. Plain e-mail transport
    # of the app is only one channel: an external monitor stays the independent one.
    operator_alert_email: str = ""

    @property
    def ai_budget_enforced(self) -> bool:
        return self.ai_monthly_hard_usd > 0
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
        errors.extend(self._mail_errors())
        if self.account_deletion_enabled and not self.erasure_key_ready():
            errors.append("account_erasure_key")
        if len(self.auth_rate_limit_key.strip()) < 32 or self.auth_rate_limit_key.strip() in {
            secret.strip(),
            self.auth_refresh_retry_key.strip(),
            self.mail_outbox_key.strip(),
        }:
            errors.append("auth_rate_limit_key")
        if self.trusted_proxy_hops < 1:
            errors.append("trusted_proxy_hops")
        if not _is_remote_database(self.database_url):
            errors.append("database_url")
        if not all(_is_public_https_origin(origin) for origin in self.cors_origins):
            errors.append("allowed_origins")
        if not self.google_oauth_client_id.strip():
            errors.append("google_oauth_client_id")
        if self.llm_mock:
            errors.append("llm_mock")
        elif not self.openai_api_key.strip():
            errors.append("openai_api_key")
        import_provider = (self.llm_import_provider or "openai").strip().lower()
        if import_provider == "anthropic" and not self.anthropic_api_key.strip():
            errors.append("anthropic_api_key")
        if not self.operator_name.strip():
            errors.append("operator_name")
        if not is_mail_address(self.support_email):
            errors.append("support_email")
        if self.operator_alert_email.strip() and not is_mail_address(self.operator_alert_email):
            errors.append("operator_alert_email")
        if self.min_app_version_code < 0 or (
            self.min_app_version_code > 0 and not self._update_url_valid()
        ):
            errors.append("app_update")
        if not (0 < self.ai_monthly_warn_usd <= self.ai_monthly_hard_usd):
            errors.append("ai_monthly_budget")
        elif not self._models_priced():
            errors.append("llm_model_pricing")
        return errors

    def _update_url_valid(self) -> bool:
        """Only this app's own Play listing; the client never opens any other address."""
        return self.app_update_url == f"https://play.google.com/store/apps/details?id={self.android_package}"

    def _models_priced(self) -> bool:
        """Every configured model needs a price, or the cap cannot reserve for its calls."""
        from app.ai.prompts.v1 import LOOKUP_DRAFT_MODEL, LOOKUP_EXPAND_MODEL
        from app.services.llm_pricing import has_pricing

        models = {
            self.llm_lookup_model,
            self.llm_enrichment_model,
            self.llm_light_model,
            self.llm_import_layout_model.strip() or self.llm_lookup_model,
            LOOKUP_DRAFT_MODEL,
            LOOKUP_EXPAND_MODEL,
        }
        return all(has_pricing(m) for m in models)

    def _token_periods_valid(self) -> bool:
        access = self.access_token_expire_minutes
        refresh_minutes = self.refresh_token_expire_days * 24 * 60
        return 0 < access < refresh_minutes

    def erasure_key_ready(self) -> bool:
        key = self.account_erasure_key.strip()
        others = {
            self.jwt_secret.strip(),
            self.auth_refresh_retry_key.strip(),
            self.mail_outbox_key.strip(),
            self.auth_rate_limit_key.strip(),
        }
        return len(key) >= 32 and key not in others and self.account_erasure_key_version > 0

    def mail_ready(self) -> bool:
        """Whether account mail can be accepted; local environments use the log transport."""
        return not self.is_deployed or not self._mail_errors()

    def _mail_errors(self) -> list[str]:
        errors: list[str] = []
        if not _is_bare_public_origin(self.public_app_origin):
            errors.append("public_app_origin")
        if self.mail_transport != "resend":
            errors.append("mail_transport")
        elif not self.resend_api_key.strip():
            errors.append("resend_api_key")
        if not is_mail_address(self.mail_from):
            errors.append("mail_from")
        if not is_mail_address(self.mail_reply_to):
            errors.append("mail_reply_to")
        other_keys = {self.jwt_secret.strip(), self.auth_refresh_retry_key.strip()}
        if (
            not _is_fernet_key(self.mail_outbox_key)
            or self.mail_outbox_key.strip() in other_keys
        ):
            errors.append("mail_outbox_key")
        return errors


def is_mail_address(value: str) -> bool:
    """`addr@domain.tld` or `Name <addr@domain.tld>`, without spaces or line breaks in the address."""
    from email.utils import parseaddr

    raw = (value or "").strip()
    if not raw or "\n" in raw or "\r" in raw:
        return False
    _, address = parseaddr(raw)
    local, _, domain = address.rpartition("@")
    return (
        bool(local)
        and "." in domain
        and not domain.startswith(".")
        and not domain.endswith(".")
        and " " not in address
    )


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


def _is_bare_public_origin(origin: str) -> bool:
    """Link host for e-mails: https://host[:port] only, no userinfo/path/query/fragment."""
    value = (origin or "").strip()
    if not _is_public_https_origin(value):
        return False
    parts = urlsplit(value)
    return (
        "@" not in parts.netloc
        and parts.path in ("", "/")
        and not parts.query
        and not parts.fragment
        and not value.endswith("#")
        and not value.endswith("?")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

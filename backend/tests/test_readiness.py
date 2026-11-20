import asyncio
import base64
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import readiness
from app.core.config import Settings
from app.db import session as db_session

SECRET = "S" * 40
RETRY_KEY = base64.urlsafe_b64encode(b"r" * 32).decode()
MAIL_KEY = base64.urlsafe_b64encode(b"m" * 32).decode()
GOOD_DEPLOYED = {
    "environment": "beta",
    "debug": False,
    "jwt_secret": SECRET,
    "auth_refresh_retry_key": RETRY_KEY,
    "database_url": "postgresql://app:db-secret-value@postgres.railway.internal:5432/railway",
    "allowed_origins": "https://vocabulario.example",
    "google_oauth_client_id": "client-id.apps.googleusercontent.com",
    "openai_api_key": "sk-test-value",
    "llm_mock": False,
    "public_app_origin": "https://vocabulario.example",
    "mail_transport": "resend",
    "resend_api_key": "re_test_value",
    "mail_from": "Vocabulario <auth@mail.vocabulario.example>",
    "mail_reply_to": "help@vocabulario.example",
    "mail_outbox_key": MAIL_KEY,
    "auth_rate_limit_key": "L" * 40,
    "trusted_proxy_hops": 1,
    "operator_name": "Example Operator",
    "support_email": "help@vocabulario.example",
    "ai_monthly_warn_usd": "70",
    "ai_monthly_hard_usd": "100",
}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**GOOD_DEPLOYED, **overrides})


def test_valid_deployed_settings_have_no_errors():
    assert _settings().deployment_errors() == []


def test_enabled_version_gate_needs_this_apps_play_listing():
    url = "https://play.google.com/store/apps/details?id=io.vocabulario.app"
    assert _settings(min_app_version_code=5, app_update_url=url).deployment_errors() == []


def test_local_environments_accept_dev_defaults():
    for env in ("development", "test"):
        assert Settings(_env_file=None, environment=env).deployment_errors() == []


def test_unknown_environment_is_an_error():
    assert _settings(environment="prod").deployment_errors() == ["environment"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"debug": True}, "debug"),
        ({"jwt_secret": "change-me"}, "jwt_secret"),
        ({"jwt_secret": "short-secret"}, "jwt_secret"),
        ({"jwt_algorithm": "HS512"}, "jwt_algorithm"),
        ({"access_token_expire_minutes": 0}, "token_expiry"),
        ({"refresh_token_expire_days": 0}, "token_expiry"),
        ({"auth_refresh_retry_key": ""}, "auth_refresh_retry_key"),
        ({"auth_refresh_retry_key": "not-a-fernet-key"}, "auth_refresh_retry_key"),
        ({"jwt_secret": RETRY_KEY}, "auth_refresh_retry_key"),
        ({"database_url": "postgresql://u:p@localhost:5432/vocabulario"}, "database_url"),
        ({"database_url": "not a url"}, "database_url"),
        ({"allowed_origins": "https://ok.example,http://10.0.2.2:8000"}, "allowed_origins"),
        ({"allowed_origins": "http://vocabulario.example"}, "allowed_origins"),
        ({"allowed_origins": "*"}, "allowed_origins"),
        ({"google_oauth_client_id": ""}, "google_oauth_client_id"),
        ({"llm_mock": True}, "llm_mock"),
        ({"openai_api_key": " "}, "openai_api_key"),
        ({"llm_import_provider": " Anthropic "}, "anthropic_api_key"),
        ({"public_app_origin": ""}, "public_app_origin"),
        ({"public_app_origin": "http://vocabulario.example"}, "public_app_origin"),
        ({"public_app_origin": "https://vocabulario.example/app"}, "public_app_origin"),
        ({"public_app_origin": "https://u:p@vocabulario.example"}, "public_app_origin"),
        ({"public_app_origin": "https://vocabulario.example?next=x"}, "public_app_origin"),
        ({"public_app_origin": "https://localhost"}, "public_app_origin"),
        ({"mail_transport": "log"}, "mail_transport"),
        ({"resend_api_key": ""}, "resend_api_key"),
        ({"mail_from": ""}, "mail_from"),
        ({"mail_from": "no-address"}, "mail_from"),
        ({"mail_from": "a@b.c\nBcc: x@y.z"}, "mail_from"),
        ({"mail_reply_to": "help@localhost"}, "mail_reply_to"),
        ({"mail_outbox_key": ""}, "mail_outbox_key"),
        ({"mail_outbox_key": "not-a-fernet-key"}, "mail_outbox_key"),
        ({"mail_outbox_key": RETRY_KEY}, "mail_outbox_key"),
        ({"auth_rate_limit_key": ""}, "auth_rate_limit_key"),
        ({"auth_rate_limit_key": SECRET}, "auth_rate_limit_key"),
        ({"trusted_proxy_hops": 0}, "trusted_proxy_hops"),
        ({"operator_name": " "}, "operator_name"),
        ({"support_email": ""}, "support_email"),
        ({"support_email": "help@localhost"}, "support_email"),
        ({"operator_alert_email": "not-an-address"}, "operator_alert_email"),
        ({"ai_monthly_hard_usd": "0"}, "ai_monthly_budget"),
        ({"ai_monthly_warn_usd": "0"}, "ai_monthly_budget"),
        ({"ai_monthly_warn_usd": "120"}, "ai_monthly_budget"),
        ({"llm_light_model": "unpriced-model"}, "llm_model_pricing"),
        ({"min_app_version_code": -1}, "app_update"),
        ({"min_app_version_code": 5}, "app_update"),
        ({"min_app_version_code": 5, "app_update_url": "https://example.com/app"}, "app_update"),
        (
            {
                "min_app_version_code": 5,
                "app_update_url": "http://play.google.com/store/apps/details?id=io.vocabulario.app",
            },
            "app_update",
        ),
    ],
)
def test_each_invalid_deployed_setting_is_named(overrides, field):
    assert _settings(**overrides).deployment_errors() == [field]


def test_deployed_defaults_report_names_without_values():
    errors = Settings(_env_file=None, environment="production").deployment_errors()
    assert set(errors) >= {"debug", "jwt_secret", "database_url", "allowed_origins"}
    assert "change-me" not in " ".join(errors)
    assert SECRET not in " ".join(_settings(debug=True).deployment_errors())


async def _get_ready(app_settings: Settings, monkeypatch):
    from app.main import create_app

    monkeypatch.setattr(readiness, "get_settings", lambda: app_settings)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health/ready")


def _assert_unavailable(response):
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert response.headers["cache-control"] == "no-store"


async def test_ready_is_503_with_invalid_config_without_leaking(monkeypatch, caplog):
    monkeypatch.setattr(readiness, "_schema_ready", True)
    monkeypatch.setattr(readiness, "_last_failure", None)
    response = await _get_ready(_settings(debug=True), monkeypatch)
    _assert_unavailable(response)
    assert "debug" in caplog.text
    assert SECRET not in caplog.text + response.text
    assert "db-secret-value" not in caplog.text + response.text


async def test_ready_is_503_before_schema_is_applied(monkeypatch):
    monkeypatch.setattr(readiness, "_schema_ready", False)
    _assert_unavailable(await _get_ready(Settings(_env_file=None), monkeypatch))


async def test_ready_is_503_when_database_refuses(monkeypatch):
    dead = create_async_engine("postgresql+asyncpg://nobody:pw-value@127.0.0.1:1/dead_test")
    monkeypatch.setattr(db_session, "engine", dead)
    monkeypatch.setattr(readiness, "_schema_ready", True)
    try:
        response = await _get_ready(Settings(_env_file=None), monkeypatch)
    finally:
        await dead.dispose()
    _assert_unavailable(response)
    assert "pw-value" not in response.text


async def test_ready_gives_up_on_a_hanging_database(monkeypatch):
    async def hang():
        await asyncio.sleep(10)

    monkeypatch.setattr(readiness, "_ping_db", hang)
    monkeypatch.setattr(readiness, "_schema_ready", True)
    started = time.monotonic()
    response = await _get_ready(Settings(_env_file=None), monkeypatch)
    _assert_unavailable(response)
    assert time.monotonic() - started < readiness.TOTAL_TIMEOUT_SECONDS


@pytest.mark.pg
async def test_ready_is_ok_with_database_and_schema(pg, monkeypatch):
    monkeypatch.setattr(readiness, "_schema_ready", True)
    response = await _get_ready(Settings(_env_file=None), monkeypatch)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("age_minutes", "failure"),
    [(None, "maintenance heartbeat stale"), (45, "maintenance heartbeat stale"), (5, None)],
)
async def test_deployed_readiness_needs_a_fresh_maintenance_heartbeat(
    monkeypatch, age_minutes, failure
):
    from datetime import UTC, datetime, timedelta

    from app.services import maintenance

    async def heartbeat():
        return None if age_minutes is None else datetime.now(UTC) - timedelta(minutes=age_minutes)

    async def ping():
        return None

    monkeypatch.setattr(readiness, "get_settings", lambda: _settings())
    monkeypatch.setattr(readiness, "_schema_ready", True)
    monkeypatch.setattr(readiness, "_ping_db", ping)
    monkeypatch.setattr(maintenance, "last_heartbeat", heartbeat)
    assert await readiness._failure() == failure

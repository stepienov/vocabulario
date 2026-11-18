import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import readiness
from app.core.config import Settings
from app.db import session as db_session

SECRET = "S" * 40
GOOD_DEPLOYED = {
    "environment": "beta",
    "debug": False,
    "jwt_secret": SECRET,
    "database_url": "postgresql://app:db-secret-value@postgres.railway.internal:5432/railway",
    "allowed_origins": "https://vocabulario.example",
    "google_oauth_client_id": "client-id.apps.googleusercontent.com",
    "openai_api_key": "sk-test-value",
    "llm_mock": False,
}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**GOOD_DEPLOYED, **overrides})


def test_valid_deployed_settings_have_no_errors():
    assert _settings().deployment_errors() == []


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
        ({"database_url": "postgresql://u:p@localhost:5432/vocabulario"}, "database_url"),
        ({"database_url": "not a url"}, "database_url"),
        ({"allowed_origins": "https://ok.example,http://10.0.2.2:8000"}, "allowed_origins"),
        ({"allowed_origins": "http://vocabulario.example"}, "allowed_origins"),
        ({"allowed_origins": "*"}, "allowed_origins"),
        ({"google_oauth_client_id": ""}, "google_oauth_client_id"),
        ({"llm_mock": True}, "llm_mock"),
        ({"openai_api_key": " "}, "openai_api_key"),
        ({"llm_import_provider": " Anthropic "}, "anthropic_api_key"),
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

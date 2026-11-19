import pytest
from httpx import ASGITransport, AsyncClient

from app.core import client_version
from app.core.client_version import parse_version_code, update_required
from app.core.config import get_settings
from app.main import create_app

PLAY_URL = "https://play.google.com/store/apps/details?id=com.vocabulario.app"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("7", 7), (" 12 ", 12), (None, 0), ("", 0), ("-3", 0), ("1.5", 0), ("abc", 0), ("٣", 0), ("1" * 10, 0)],
)
def test_version_header_parsing_never_raises(raw, expected):
    assert parse_version_code(raw) == expected


@pytest.mark.parametrize(
    ("path", "header", "minimum", "blocked"),
    [
        ("/api/v1/sync/pull", "5", 0, False),
        ("/api/v1/sync/pull", "4", 5, True),
        ("/api/v1/sync/pull", "5", 5, False),
        ("/api/v1/sync/pull", "6", 5, False),
        ("/api/v1/sync/pull", None, 5, True),
        ("/api/v1/auth/refresh", "garbage", 5, True),
        ("/api/v1/auth/login", None, 5, True),
        ("/health/ready", None, 5, False),
        ("/legal", None, 5, False),
        ("/support", None, 5, False),
        ("/api/v1/legal/current", None, 5, False),
        ("/api/v1/account-deletion/status", None, 5, False),
        ("/api/v1/auth/password-reset/confirm", None, 5, False),
        ("/api/v1/auth/email-verification/confirm", None, 5, False),
        ("/api/v1/auth/email-change/confirm", None, 5, False),
        ("/api/v1/auth/mail-events", None, 5, False),
        ("/api/v1/auth/logout", None, 5, False),
        ("/api/v1/auth/password-reset", None, 5, True),
        ("/api/v1/auth/email-verification/status", None, 5, True),
    ],
)
def test_gate_decision(path, header, minimum, blocked):
    assert update_required(path, header, minimum) is blocked


async def _call(monkeypatch, method: str, path: str, headers: dict | None = None, **settings):
    for name, value in settings.items():
        monkeypatch.setattr(get_settings(), name, value)
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers)


async def test_old_client_gets_426_with_minimum_and_update_url(monkeypatch):
    response = await _call(
        monkeypatch, "GET", "/api/v1/me", min_app_version_code=7, app_update_url=PLAY_URL
    )
    assert response.status_code == 426
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "detail": {
            "code": "app_update_required",
            "message": "app_update_required",
            "min_version_code": 7,
            "update_url": PLAY_URL,
        }
    }


async def test_426_comes_before_authentication(monkeypatch):
    response = await _call(
        monkeypatch,
        "POST",
        "/api/v1/auth/refresh",
        headers={"Authorization": "Bearer nonsense"},
        min_app_version_code=7,
    )
    assert response.status_code == 426
    assert "update_url" not in response.json()["detail"]


async def test_sufficient_client_reaches_the_route(monkeypatch):
    response = await _call(
        monkeypatch, "GET", "/api/v1/me", headers={client_version.HEADER: "7"}, min_app_version_code=7
    )
    assert response.status_code == 401


async def test_gate_off_by_default_and_health_is_never_gated(monkeypatch):
    assert (await _call(monkeypatch, "GET", "/api/v1/me", min_app_version_code=0)).status_code == 401
    assert (await _call(monkeypatch, "GET", "/health", min_app_version_code=99)).status_code == 200


async def test_public_legal_manifest_stays_open_for_old_clients(monkeypatch):
    response = await _call(monkeypatch, "GET", "/api/v1/legal/current", min_app_version_code=99)
    assert response.status_code != 426

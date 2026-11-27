from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin_ui.auth import COOKIE_NAME
from app.admin_ui.router import mount_admin
from app.core.config import get_settings


def _panel_client(monkeypatch, username: str, password: str) -> TestClient:
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_username", username)
    monkeypatch.setattr(settings, "admin_password", password)
    async def allow_login_attempts(*_rules):
        return None

    monkeypatch.setattr("app.admin_ui.router.auth_limits.enforce", allow_login_attempts)
    app = FastAPI()
    mount_admin(app)
    return TestClient(app)


def test_panel_disabled_is_404(monkeypatch):
    client = _panel_client(monkeypatch, "", "")
    response = client.get("/admin/login")
    assert response.status_code == 404


def test_login_page_ok_when_enabled(monkeypatch):
    client = _panel_client(monkeypatch, "admin", "s3cret")
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert "Panel administracyjny" in response.text


def test_login_rejects_bad_password(monkeypatch):
    client = _panel_client(monkeypatch, "admin", "s3cret")
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "wrong", "next": "/admin"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert COOKIE_NAME not in response.cookies


def test_login_applies_ip_and_username_limits(monkeypatch):
    client = _panel_client(monkeypatch, "admin", "s3cret")
    seen = []

    async def record_rules(*rules):
        seen.extend(rules)

    monkeypatch.setattr("app.admin_ui.router.auth_limits.enforce", record_rules)
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "wrong", "next": "/admin"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert [(rule.scope, rule.limit) for rule in seen] == [
        ("panel_login_ip", 20),
        ("panel_login_user", 10),
    ]


def test_login_sets_cookie(monkeypatch):
    client = _panel_client(monkeypatch, "admin", "s3cret")
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "s3cret", "next": "/admin"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert COOKIE_NAME in response.cookies


def test_admin_sessions_are_revoked_when_credentials_or_version_change(monkeypatch):
    from app.admin_ui.auth import _decode, _encode

    _panel_client(monkeypatch, "admin", "s3cret")
    settings = get_settings()
    token = _encode("admin")
    assert _decode(token) == "admin"

    monkeypatch.setattr(settings, "admin_password", "new-secret")
    assert _decode(token) is None

    monkeypatch.setattr(settings, "admin_password", "s3cret")
    monkeypatch.setattr(settings, "admin_session_version", 2)
    assert _decode(token) is None

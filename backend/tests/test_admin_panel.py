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

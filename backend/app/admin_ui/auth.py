from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

from app.core.config import get_settings

COOKIE_NAME = "vocabulario_admin"
TOKEN_TYPE = "admin_panel"
COOKIE_MAX_AGE = 14 * 24 * 3600


class LoginRequired(Exception):
    def __init__(self, next_url: str = "/admin"):
        self.next_url = next_url


class PanelDisabled(Exception):
    pass


def panel_enabled() -> bool:
    return get_settings().panel_enabled


def _encode(username: str) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "sub": username,
        "type": TOKEN_TYPE,
        "exp": datetime.now(UTC) + timedelta(seconds=COOKIE_MAX_AGE),
    }
    return jwt.encode(payload, settings.panel_cookie_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.panel_cookie_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None
    if payload.get("type") != TOKEN_TYPE:
        return None
    sub = payload.get("sub")
    if not sub or sub != settings.admin_username:
        return None
    return str(sub)


def verify_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    if not settings.panel_enabled:
        return False
    from hmac import compare_digest

    return compare_digest(username, settings.admin_username) and compare_digest(
        password, settings.admin_password
    )


def set_session_cookie(response: RedirectResponse, username: str) -> None:
    settings = get_settings()
    secure = (settings.environment or "").lower() == "production"
    response.set_cookie(
        COOKIE_NAME,
        _encode(username),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/admin",
    )


def clear_session_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(COOKIE_NAME, path="/admin")


def require_panel(request: Request) -> str:
    if not panel_enabled():
        raise PanelDisabled()
    token = request.cookies.get(COOKIE_NAME)
    username = _decode(token) if token else None
    if not username:
        raise LoginRequired(str(request.url.path))
    return username

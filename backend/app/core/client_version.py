"""Minimal Android version gate (E-001/F-002/T-001): a readable 426, never an authorisation check."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from app.core.config import Settings

HEADER = "x-app-version-code"
API_PREFIX = "/api/v1/"

# Public pages and provider callbacks call these without the app: they stay open to every client.
EXEMPT_PREFIXES = (
    "/api/v1/legal/",
    "/api/v1/account-deletion/",
    "/api/v1/auth/email-verification/confirm",
    "/api/v1/auth/password-reset/confirm",
    "/api/v1/auth/email-change/confirm",
    "/api/v1/auth/logout",
    "/api/v1/auth/mail-events",
    "/api/v1/admin/",
)


def parse_version_code(raw: str | None) -> int:
    """Missing or malformed counts as 0, i.e. a client from before the header existed."""
    value = (raw or "").strip()
    if not value.isascii() or not value.isdigit() or len(value) > 9:
        return 0
    return int(value)


def update_required(path: str, header: str | None, minimum: int) -> bool:
    if minimum <= 0 or not path.startswith(API_PREFIX):
        return False
    if path.startswith(EXEMPT_PREFIXES):
        return False
    return parse_version_code(header) < minimum


def update_required_response(settings: Settings) -> JSONResponse:
    detail: dict[str, object] = {
        "code": "app_update_required",
        "message": "app_update_required",
        "min_version_code": settings.min_app_version_code,
    }
    if settings.app_update_url:
        detail["update_url"] = settings.app_update_url
    return JSONResponse(status_code=426, content={"detail": detail}, headers={"Cache-Control": "no-store"})

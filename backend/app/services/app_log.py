"""Trwały dziennik w Postgres — osobna transakcja, nigdy nie psuje requestu."""

from __future__ import annotations

import logging
import traceback as tb_mod
from contextvars import ContextVar
from typing import Any
from uuid import UUID, uuid4

from app.models import AppLog

logger = logging.getLogger(__name__)

request_id_var: ContextVar[UUID | None] = ContextVar("app_log_request_id", default=None)
user_id_var: ContextVar[UUID | None] = ContextVar("app_log_user_id", default=None)
profile_id_var: ContextVar[UUID | None] = ContextVar("app_log_profile_id", default=None)

_MAX_MSG = 4000
_MAX_TB = 20000
_SECRET_KEYS = frozenset(
    {
        "authorization",
        "password",
        "refresh_token",
        "access_token",
        "id_token",
        "openai_api_key",
        "api_key",
        "jwt",
        "cookie",
    }
)


def bind_request_context(
    *,
    request_id: UUID | None = None,
    user_id: UUID | None = None,
    profile_id: UUID | None = None,
) -> None:
    if request_id is not None:
        request_id_var.set(request_id)
    if user_id is not None:
        user_id_var.set(user_id)
    if profile_id is not None:
        profile_id_var.set(profile_id)


def clear_request_context() -> None:
    request_id_var.set(None)
    user_id_var.set(None)
    profile_id_var.set(None)


def _as_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _clip(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    return value if len(value) <= limit else value[: limit - 1] + "…"


def sanitize_payload(payload: dict | None) -> dict | None:
    if not payload:
        return None
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key).lower() in _SECRET_KEYS:
            out[str(key)] = "[redacted]"
        elif isinstance(value, str) and len(value) > 2000:
            out[str(key)] = value[:2000] + "…"
        else:
            out[str(key)] = value
    return out


def category_for_path(path: str) -> str:
    p = path.lower()
    if "/lookup" in p:
        return "lookup"
    if "/imports" in p:
        return "import"
    if "/srs" in p:
        return "srs"
    if "/cards" in p:
        return "cards"
    if "/lists" in p:
        return "lists"
    if "/settings" in p:
        return "settings"
    if "/profiles" in p:
        return "profiles"
    if "/auth" in p:
        return "auth"
    if "/sync" in p:
        return "sync"
    if "/devices" in p:
        return "devices"
    if "/corrections" in p or "/self-edit" in p or "/history" in p:
        return "cards"
    return "http"


def is_noisy_get(method: str, path: str) -> bool:
    if method.upper() != "GET":
        return False
    p = path.lower()
    if p.endswith("/health"):
        return True
    if "/progress" in p or p.endswith("/jobs/active"):
        return True
    if p.endswith("/words") or "/lists/" in p and p.endswith("/words"):
        return True
    if p.rstrip("/").endswith("/lists"):
        return True
    if "/sync/pull" in p or p.endswith("/stats"):
        return True
    if p.endswith("/settings") or p.endswith("/profiles"):
        return True
    return False


def should_log_http(method: str, path: str, status: int, duration_ms: int) -> bool:
    if status >= 400:
        return True
    if duration_ms >= 2000:
        return True
    if is_noisy_get(method, path):
        return False
    return True


async def log_event(
    *,
    level: str,
    category: str,
    event: str,
    status: str = "ok",
    user_id: UUID | str | None = None,
    profile_id: UUID | str | None = None,
    request_id: UUID | None = None,
    http_method: str | None = None,
    http_path: str | None = None,
    http_status: int | None = None,
    entity_type: str | None = None,
    entity_id: str | UUID | None = None,
    duration_ms: int | None = None,
    message: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    traceback: str | None = None,
    payload: dict | None = None,
    exc: BaseException | None = None,
) -> None:
    if exc is not None:
        error_type = error_type or type(exc).__name__
        error_message = error_message or str(exc)
        traceback = traceback or tb_mod.format_exc()
        if status == "ok":
            status = "error"
        if level == "info":
            level = "error"
    try:
        from app.db.session import async_session_factory

        row = AppLog(
            id=uuid4(),
            level=(level or "info")[:16],
            category=(category or "http")[:32],
            event=(event or "unknown")[:64],
            status=(status or "ok")[:16],
            request_id=request_id or request_id_var.get(),
            user_id=_as_uuid(user_id) or user_id_var.get(),
            profile_id=_as_uuid(profile_id) or profile_id_var.get(),
            http_method=(http_method or None) and http_method[:16],
            http_path=_clip(http_path, 512),
            http_status=http_status,
            entity_type=(entity_type or None) and entity_type[:32],
            entity_id=None if entity_id is None else str(entity_id)[:64],
            duration_ms=duration_ms,
            message=_clip(message, _MAX_MSG),
            error_type=_clip(error_type, 128),
            error_message=_clip(error_message, _MAX_MSG),
            traceback=_clip(traceback, _MAX_TB),
            payload=sanitize_payload(payload),
        )
        async with async_session_factory() as db:
            db.add(row)
            await db.commit()
    except Exception:
        logger.exception("app_log write failed event=%s", event)

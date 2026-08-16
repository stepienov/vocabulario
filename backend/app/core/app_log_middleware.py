from __future__ import annotations

import time
from uuid import UUID, uuid4

from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.app_log import (
    bind_request_context,
    category_for_path,
    clear_request_context,
    log_event,
    should_log_http,
)


def _user_id_from_request(request: Request) -> UUID | None:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        from app.core.security import decode_token

        payload = decode_token(token)
        return UUID(str(payload.get("sub")))
    except (JWTError, ValueError, TypeError, KeyError):
        return None


def _profile_id_from_request(request: Request) -> UUID | None:
    raw = request.query_params.get("profile_id")
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


class AppLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid4()
        user_id = _user_id_from_request(request)
        profile_id = _profile_id_from_request(request)
        bind_request_context(request_id=request_id, user_id=user_id, profile_id=profile_id)
        path = request.url.path
        method = request.method
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await log_event(
                level="error",
                category=category_for_path(path),
                event="http_unhandled",
                status="error",
                http_method=method,
                http_path=path,
                duration_ms=duration_ms,
                message=f"{method} {path} crashed",
                exc=exc,
            )
            clear_request_context()
            raise
        duration_ms = int((time.perf_counter() - started) * 1000)
        status = response.status_code
        if should_log_http(method, path, status, duration_ms):
            level = "error" if status >= 500 else "warn" if status >= 400 else "info"
            await log_event(
                level=level,
                category=category_for_path(path),
                event="http_request",
                status="error" if status >= 400 else "ok",
                http_method=method,
                http_path=path,
                http_status=status,
                duration_ms=duration_ms,
                message=f"{method} {path} → {status}",
                payload={"query": dict(request.query_params)},
            )
        clear_request_context()
        return response

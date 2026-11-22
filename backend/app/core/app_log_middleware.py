from __future__ import annotations

import time
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.app_log import (
    bind_request_context,
    category_for_path,
    clear_request_context,
    log_event,
    route_template,
    should_log_http,
)
from app.services.background import spawn_background
from app.services.llm_usage import clear_llm_usage_context


def _user_id_from_request(request: Request) -> UUID | None:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    from app.core.security import token_subject

    return token_subject(token)


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
        clear_llm_usage_context()
        path = request.url.path
        method = request.method
        shape = route_template(path)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            captured = exc  # the name is cleared when the except block ends
            spawn_background(
                lambda: log_event(
                    level="error",
                    category=category_for_path(path),
                    event="http_unhandled",
                    status="error",
                    http_method=method,
                    http_path=shape,
                    duration_ms=duration_ms,
                    message=f"{method} {shape} crashed",
                    exc=captured,
                ),
                name="app_log_http",
            )
            clear_request_context()
            raise
        duration_ms = int((time.perf_counter() - started) * 1000)
        status = response.status_code
        if should_log_http(method, path, status, duration_ms):
            level = "error" if status >= 500 else "warn" if status >= 400 else "info"
            spawn_background(
                lambda: log_event(
                    level=level,
                    category=category_for_path(path),
                    event="http_request",
                    status="error" if status >= 400 else "ok",
                    http_method=method,
                    http_path=shape,
                    http_status=status,
                    duration_ms=duration_ms,
                    message=f"{method} {shape} → {status}",
                ),
                name="app_log_http",
            )
        clear_request_context()
        return response

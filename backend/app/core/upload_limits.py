from __future__ import annotations

import json

MAX_IMPORT_FILE_BYTES = 10 * 1024 * 1024
MAX_IMPORT_REQUEST_BYTES = MAX_IMPORT_FILE_BYTES + 64 * 1024
_IMPORT_UPLOAD_PATHS = frozenset({"/api/v1/imports/jobs/file", "/api/v1/imports/file"})
_TOO_LARGE_BODY = json.dumps(
    {"detail": {"code": "import_too_large", "message": "Import file exceeds 10 MiB."}}
).encode("utf-8")


class _UploadTooLarge(Exception):
    pass


class ImportUploadLimitMiddleware:
    """Bound the upload request body before Starlette spools multipart file data."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in _IMPORT_UPLOAD_PATHS
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", ()))
        try:
            content_length = int(headers.get(b"content-length", b""))
        except ValueError:
            content_length = 0
        if content_length > MAX_IMPORT_REQUEST_BYTES:
            await self._reject(send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_IMPORT_REQUEST_BYTES:
                    raise _UploadTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _UploadTooLarge:
            await self._reject(send)

    @staticmethod
    async def _reject(send):
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE_BODY)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE_BODY})

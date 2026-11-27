import pytest

from app.core.upload_limits import (
    MAX_IMPORT_FILE_BYTES,
    MAX_IMPORT_REQUEST_BYTES,
    ImportUploadLimitMiddleware,
)


async def _run_middleware(headers, chunks):
    sent = []

    async def app(scope, receive, send):
        while True:
            message = await receive()
            if message["type"] == "http.request" and not message.get("more_body", False):
                break

    async def receive():
        return chunks.pop(0)

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/imports/jobs/file",
        "headers": headers,
    }
    await ImportUploadLimitMiddleware(app)(scope, receive, send)
    return sent


@pytest.mark.asyncio
async def test_import_upload_rejects_declared_oversized_body_without_reading_it():
    sent = await _run_middleware(
        [(b"content-length", str(MAX_IMPORT_REQUEST_BYTES + 1).encode())],
        [{"type": "http.request", "body": b"", "more_body": False}],
    )
    assert sent[0]["status"] == 413
    assert b"import_too_large" in sent[1]["body"]


@pytest.mark.asyncio
async def test_import_upload_rejects_chunked_oversized_body():
    sent = await _run_middleware(
        [],
        [
            {
                "type": "http.request",
                "body": b"x" * MAX_IMPORT_REQUEST_BYTES,
                "more_body": True,
            },
            {"type": "http.request", "body": b"x", "more_body": False},
        ],
    )
    assert sent[0]["status"] == 413
    assert b"import_too_large" in sent[1]["body"]


def test_import_file_limit_is_10_mib():
    assert MAX_IMPORT_FILE_BYTES == 10 * 1024 * 1024

"""E-001/F-004/T-002: Resend adapter maps provider answers without real network calls."""

import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.mail_transport import (
    LogTransport,
    OutgoingMail,
    ResendTransport,
    UnconfiguredTransport,
    get_transport,
)

MAIL = OutgoingMail(
    to="someone@test.com",
    sender="Vocabulario <auth@app.example>",
    reply_to="help@app.example",
    subject="Reset",
    text="text body",
    html="<p>html body</p>",
    locale="pl",
    template="reset_password/v1",
)


async def _send(handler):
    transport = ResendTransport("re_test_key", http_transport=httpx.MockTransport(handler))
    return await transport.send(MAIL, "auth-mail/123")


async def test_accepted_request_carries_key_and_full_message():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"id": "re-msg-1"})

    result = await _send(handler)
    assert result.outcome == "accepted" and result.provider_message_id == "re-msg-1"
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["Idempotency-Key"] == "auth-mail/123"
    assert seen["headers"]["Authorization"] == "Bearer re_test_key"
    assert seen["body"] == {
        "from": MAIL.sender,
        "to": [MAIL.to],
        "subject": MAIL.subject,
        "text": MAIL.text,
        "html": MAIL.html,
        "reply_to": MAIL.reply_to,
    }


@pytest.mark.parametrize(
    ("status", "name", "headers", "outcome", "code", "retry_after"),
    [
        (429, "rate_limit_exceeded", {"retry-after": "7"}, "retry", "resend_rate_limit_exceeded", 7),
        (429, "daily_quota_exceeded", {}, "retry", "resend_daily_quota_exceeded", None),
        (500, "application_error", {}, "retry", "resend_application_error", None),
        (503, "service_unavailable", {}, "retry", "resend_service_unavailable", None),
        (409, "concurrent_idempotent_requests", {}, "retry", None, None),
        (409, "invalid_idempotent_request", {}, "permanent", None, None),
        (422, "missing_required_field", {}, "permanent", "resend_missing_required_field", None),
        (403, "validation_error", {}, "permanent", "resend_validation_error", None),
        (401, "missing_api_key", {}, "permanent", "resend_missing_api_key", None),
    ],
)
async def test_provider_errors(status, name, headers, outcome, code, retry_after):
    def handler(request):
        return httpx.Response(status, json={"statusCode": status, "name": name}, headers=headers)

    result = await _send(handler)
    assert result.outcome == outcome
    assert result.error_code == (code or f"resend_{name}")
    assert result.retry_after_s == retry_after


async def test_network_failures_and_missing_id_are_retried():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def broken(request):
        raise httpx.ConnectError("down", request=request)

    def no_id(request):
        return httpx.Response(200, text="not json")

    assert (await _send(timeout)).error_code == "resend_timeout"
    assert (await _send(broken)).error_code == "resend_network"
    result = await _send(no_id)
    assert result.outcome == "retry" and result.error_code == "resend_missing_id"


async def test_log_transport_refuses_deployed_environments(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    result = await LogTransport().send(MAIL, "auth-mail/1")
    assert result.outcome == "permanent" and result.error_code == "log_transport_disabled"


def test_resend_without_key_is_unconfigured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mail_transport", "resend")
    monkeypatch.setattr(settings, "resend_api_key", " ")
    assert isinstance(get_transport(), UnconfiguredTransport)

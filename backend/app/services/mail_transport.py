"""Account mail transports (E-001/F-004/T-002).

`log` prints the whole message to the local console for development only.
`resend` calls the Resend Send Email API with a stable idempotency key.
Transports never raise for provider answers; they return a `SendResult`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
SEND_TIMEOUT_S = 12.0
# 409 answers Resend documents as safe to repeat with the same idempotency key.
_RESEND_RETRYABLE_CONFLICTS = frozenset({"concurrent_idempotent_requests", "resource_locked"})


@dataclass(frozen=True)
class OutgoingMail:
    to: str
    sender: str
    reply_to: str
    subject: str
    text: str
    html: str
    locale: str
    template: str


@dataclass(frozen=True)
class SendResult:
    outcome: Literal["accepted", "retry", "permanent"]
    provider_message_id: str | None = None
    error_code: str | None = None
    retry_after_s: float | None = None


class MailTransport(Protocol):
    async def send(self, mail: OutgoingMail, idempotency_key: str) -> SendResult: ...


def _error_code(prefix: str, name: object) -> str:
    cleaned = re.sub(r"[^a-z0-9_]", "", str(name or "").lower())[:40]
    return f"{prefix}_{cleaned or 'unknown'}"


def _retry_after(response: httpx.Response) -> float | None:
    value = (response.headers.get("retry-after") or "").strip()
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


class LogTransport:
    """Development stand-in: the message (with its link) goes only to the local console."""

    async def send(self, mail: OutgoingMail, idempotency_key: str) -> SendResult:
        if get_settings().is_deployed:
            return SendResult("permanent", error_code="log_transport_disabled")
        logger.warning(
            "DEV MAIL %s (%s) to %s\nSubject: %s\n\n%s",
            idempotency_key,
            mail.template,
            mail.to,
            mail.subject,
            mail.text,
        )
        return SendResult("accepted", provider_message_id=f"log-{idempotency_key}")


class UnconfiguredTransport:
    async def send(self, mail: OutgoingMail, idempotency_key: str) -> SendResult:
        return SendResult("permanent", error_code="mail_transport_unconfigured")


class ResendTransport:
    def __init__(self, api_key: str, *, http_transport: httpx.AsyncBaseTransport | None = None):
        self._api_key = api_key
        self._http_transport = http_transport

    async def send(self, mail: OutgoingMail, idempotency_key: str) -> SendResult:
        body = {
            "from": mail.sender,
            "to": [mail.to],
            "subject": mail.subject,
            "text": mail.text,
            "html": mail.html,
        }
        if mail.reply_to:
            body["reply_to"] = mail.reply_to
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": idempotency_key,
        }
        try:
            async with httpx.AsyncClient(
                timeout=SEND_TIMEOUT_S, transport=self._http_transport
            ) as client:
                response = await client.post(RESEND_URL, json=body, headers=headers)
        except httpx.TimeoutException:
            return SendResult("retry", error_code="resend_timeout")
        except httpx.HTTPError:
            return SendResult("retry", error_code="resend_network")
        return _resend_result(response)


def _resend_result(response: httpx.Response) -> SendResult:
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    status = response.status_code
    if 200 <= status < 300:
        message_id = data.get("id")
        if isinstance(message_id, str) and message_id:
            return SendResult("accepted", provider_message_id=message_id[:128])
        return SendResult("retry", error_code="resend_missing_id")
    code = _error_code("resend", data.get("name") or status)
    if status == 429:
        return SendResult("retry", error_code=code, retry_after_s=_retry_after(response))
    if status >= 500 or (status == 409 and data.get("name") in _RESEND_RETRYABLE_CONFLICTS):
        return SendResult("retry", error_code=code, retry_after_s=_retry_after(response))
    return SendResult("permanent", error_code=code)


def get_transport() -> MailTransport:
    settings = get_settings()
    if settings.mail_transport == "log":
        return LogTransport()
    if settings.mail_transport == "resend" and settings.resend_api_key.strip():
        return ResendTransport(settings.resend_api_key.strip())
    return UnconfiguredTransport()

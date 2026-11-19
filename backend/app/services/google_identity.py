"""Local validation of Google ID tokens (E-001/F-005/T-001 section 1).

Signature, issuer, audience, `iat`/`exp` and our own nonce are checked with `google-auth`
against Google's certificates, which are cached per process following the response headers.
No request to `tokeninfo`, no secret, no token in logs. Blocking work runs in a bounded
thread pool, never on the event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import threading
import time
import weakref
from dataclasses import dataclass
from typing import Any

import requests
from cachecontrol import CacheControl
from cachecontrol.cache import DictCache
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings

CLOCK_SKEW_SECONDS = 60
CERT_TIMEOUT_SECONDS = 5
MAX_PARALLEL = 4
FORCED_REFRESH_INTERVAL = 30.0
MAX_TOKEN_CHARS = 8192
MAX_SUB_CHARS = 255
_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


class GoogleTokenInvalid(Exception):
    """The token is not acceptable: signature, audience, issuer, time, subject or nonce."""


class GoogleUnavailable(Exception):
    """The provider keys could not be read, or Google sign-in is not configured here."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str | None
    email_verified: bool
    hosted_domain: str | None

    def proves_address(self) -> bool:
        """Only Gmail or a Workspace (`hd`) address that Google itself verified."""
        if self.email is None or not self.email_verified:
            return False
        return self.email.rpartition("@")[2] == "gmail.com" or bool(self.hosted_domain)


def nonce_hash(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


class _TimedRequest(google_requests.Request):
    """Transport with a hard timeout; the default of google-auth is far too long."""

    def __call__(self, url, method="GET", body=None, headers=None, timeout=CERT_TIMEOUT_SECONDS, **kw):
        return super().__call__(url, method, body, headers, timeout=CERT_TIMEOUT_SECONDS, **kw)


_cache = DictCache()
_local = threading.local()
_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)
_refresh_lock = threading.Lock()
_last_forced_refresh = -FORCED_REFRESH_INTERVAL


def _transport() -> google_requests.Request:
    """One session per worker thread; the certificate cache is shared by the process."""
    request = getattr(_local, "request", None)
    if request is None:
        session = CacheControl(requests.Session(), cache=_cache)
        request = _TimedRequest(session=session)
        _local.request = request
    return request


def _verify_blocking(token: str, audience: str) -> dict[str, Any]:
    return google_id_token.verify_oauth2_token(
        token, _transport(), audience, clock_skew_in_seconds=CLOCK_SKEW_SECONDS
    )


def _unknown_key(exc: ValueError) -> bool:
    return "Certificate for key id" in str(exc)


def _verify_with_rotation(token: str, audience: str) -> dict[str, Any]:
    global _last_forced_refresh
    try:
        return _verify_blocking(token, audience)
    except ValueError as exc:
        if not _unknown_key(exc):
            raise
    # Google may have rotated its keys: at most one forced refresh per interval and process.
    with _refresh_lock:
        now = time.monotonic()
        if now - _last_forced_refresh < FORCED_REFRESH_INTERVAL:
            raise ValueError("unknown signing key")
        _last_forced_refresh = now
        _cache.data.clear()
    return _verify_blocking(token, audience)


def _gate() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    gate = _semaphores.get(loop)
    if gate is None:
        gate = _semaphores[loop] = asyncio.Semaphore(MAX_PARALLEL)
    return gate


def _identity(claims: dict[str, Any], expected_nonce_hash: str) -> GoogleIdentity:
    if claims.get("iss") not in _ISSUERS:
        raise GoogleTokenInvalid("issuer")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub or len(sub) > MAX_SUB_CHARS:
        raise GoogleTokenInvalid("subject")
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(
        nonce_hash(nonce), expected_nonce_hash
    ):
        raise GoogleTokenInvalid("nonce")
    email = claims.get("email")
    email = email.strip().lower() if isinstance(email, str) and email.strip() else None
    hd = claims.get("hd")
    return GoogleIdentity(
        sub=sub,
        email=email,
        email_verified=claims.get("email_verified") is True,
        hosted_domain=hd if isinstance(hd, str) and hd else None,
    )


async def verify_google_token(token: str, expected_nonce_hash: str) -> GoogleIdentity:
    """Validate a Google ID token for one challenge; never trust anything the token points to."""
    audience = get_settings().google_oauth_client_id.strip()
    if not audience:
        raise GoogleUnavailable("google sign-in is not configured")
    if not token or len(token) > MAX_TOKEN_CHARS:
        raise GoogleTokenInvalid("token")
    async with _gate():
        try:
            claims = await asyncio.to_thread(_verify_with_rotation, token, audience)
        except google_exceptions.TransportError as exc:
            raise GoogleUnavailable("certificates unavailable") from exc
        except (ValueError, google_exceptions.GoogleAuthError) as exc:
            raise GoogleTokenInvalid("token") from exc
        except requests.RequestException as exc:
            raise GoogleUnavailable("certificates unavailable") from exc
    return _identity(claims, expected_nonce_hash)

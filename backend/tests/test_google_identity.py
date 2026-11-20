"""Google ID token validation on synthetic keys (E-001/F-005/T-001 section 1); no network."""

import datetime as dt
import json
import time

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt
from google.auth import exceptions as google_exceptions

from app.core.config import get_settings
from app.services import google_identity as gi

AUD = "web-client.apps.googleusercontent.com"
NONCE = "n" * 43


def _key(kid: str):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return crypt.RSASigner.from_string(pem, kid), cert.public_bytes(serialization.Encoding.PEM).decode()


class _Response:
    def __init__(self, certs: dict[str, str]) -> None:
        self.status = 200
        self.data = json.dumps(certs).encode()
        self.headers: dict[str, str] = {}


class FakeTransport:
    def __init__(self, certs: dict[str, str]) -> None:
        self.certs = certs
        self.calls = 0
        self.error: Exception | None = None
        self.later: dict[str, str] | None = None  # served from the second read on (key rotation)

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        if self.calls > 1 and self.later is not None:
            self.certs = self.later
        return _Response(self.certs)


@pytest.fixture
def signer_and_transport(monkeypatch):
    signer, cert = _key("kid-1")
    transport = FakeTransport({"kid-1": cert})
    monkeypatch.setattr(gi, "_transport", lambda: transport)
    monkeypatch.setattr(gi, "_last_forced_refresh", -gi.FORCED_REFRESH_INTERVAL)
    monkeypatch.setattr(get_settings(), "google_oauth_client_id", AUD)
    return signer, transport


def _token(signer, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": AUD,
        "sub": "1234567890",
        "iat": now,
        "exp": now + 3600,
        "nonce": NONCE,
        "email": "Anna@Gmail.com",
        "email_verified": True,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(signer, claims, key_id=signer.key_id).decode()


async def _verify(token: str, nonce: str = NONCE):
    return await gi.verify_google_token(token, gi.nonce_hash(nonce))


async def test_valid_token_gives_identity(signer_and_transport):
    signer, _ = signer_and_transport
    identity = await _verify(_token(signer))
    assert (identity.sub, identity.email, identity.email_verified) == (
        "1234567890",
        "anna@gmail.com",
        True,
    )
    assert identity.proves_address()


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "other-client"},
        {"iss": "https://evil.example"},
        {"exp": int(time.time()) - 600},
        {"iat": int(time.time()) + 3600, "exp": int(time.time()) + 7200},
        {"nonce": "x" * 43},
        {"nonce": None},
        {"sub": None},
        {"sub": ""},
        {"sub": "s" * 256},
    ],
)
async def test_rejected_claims(signer_and_transport, overrides):
    signer, _ = signer_and_transport
    with pytest.raises(gi.GoogleTokenInvalid):
        await _verify(_token(signer, **overrides))


async def test_clock_skew_is_tolerated(signer_and_transport):
    signer, _ = signer_and_transport
    now = int(time.time())
    assert (await _verify(_token(signer, exp=now - 30))).sub == "1234567890"


async def test_wrong_signature_and_garbage_are_rejected(signer_and_transport):
    _, _ = signer_and_transport
    other, _cert = _key("kid-1")
    with pytest.raises(gi.GoogleTokenInvalid):
        await _verify(_token(other))
    for garbage in ("", "abc", "a.b.c", "x" * (gi.MAX_TOKEN_CHARS + 1)):
        with pytest.raises(gi.GoogleTokenInvalid):
            await _verify(garbage)


async def test_unverified_or_string_flag_never_proves_address(signer_and_transport):
    signer, _ = signer_and_transport
    for flag in (False, "true", None):
        identity = await _verify(_token(signer, email_verified=flag))
        assert identity.email_verified is False and not identity.proves_address()
    outlook = await _verify(_token(signer, email="a@outlook.com"))
    assert not outlook.proves_address()
    workspace = await _verify(_token(signer, email="a@firma.es", hd="firma.es"))
    assert workspace.proves_address()


async def test_missing_configuration_and_transport_failure_are_unavailable(
    signer_and_transport, monkeypatch
):
    signer, transport = signer_and_transport
    token = _token(signer)
    transport.error = google_exceptions.TransportError("down")
    with pytest.raises(gi.GoogleUnavailable):
        await _verify(token)
    monkeypatch.setattr(get_settings(), "google_oauth_client_id", " ")
    with pytest.raises(gi.GoogleUnavailable):
        await _verify(token)


async def test_unknown_key_forces_one_refresh_per_interval(signer_and_transport):
    _, transport = signer_and_transport
    rotated, _ = _key("kid-2")
    token = _token(rotated)
    with pytest.raises(gi.GoogleTokenInvalid):
        await _verify(token)
    first = transport.calls
    assert first == 2  # the normal read and one forced refresh
    with pytest.raises(gi.GoogleTokenInvalid):
        await _verify(token)
    assert transport.calls == first + 1  # inside the interval: no second forced refresh


async def test_rotated_key_is_picked_up_after_refresh(signer_and_transport):
    _, transport = signer_and_transport
    rotated, cert = _key("kid-2")
    transport.later = {"kid-2": cert}
    assert (await _verify(_token(rotated))).sub == "1234567890"
    assert transport.calls == 2

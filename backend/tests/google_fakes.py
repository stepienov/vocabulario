"""Fake Google verification for PG tests: the nonce and claim rules stay the production ones."""

import json
from uuid import uuid4

from app.services import google_challenges
from app.services import google_identity as gi


def google_token(nonce: str, sub: str, email: str | None = None, **claims) -> str:
    body = {"iss": "accounts.google.com", "sub": sub, "nonce": nonce, **claims}
    if email is not None:
        body["email"] = email
    return json.dumps(body)


def install_fake_google(monkeypatch) -> None:
    """Replace only the signature check; `_identity` still validates issuer, sub and nonce."""

    async def verify(token: str, expected_nonce_hash: str) -> gi.GoogleIdentity:
        try:
            claims = json.loads(token)
        except ValueError as exc:
            raise gi.GoogleTokenInvalid("token") from exc
        return gi._identity(claims, expected_nonce_hash)

    monkeypatch.setattr(google_challenges, "verify_google_token", verify)


async def login_challenge(client) -> dict:
    response = await client.post("/api/v1/auth/google/challenge")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


async def google_login(client, sub: str | None = None, email: str | None = None, **claims):
    """Full login round trip; returns the raw response of `/auth/google`."""
    locale = claims.pop("locale", None)
    challenge = await login_challenge(client)
    token = google_token(challenge["nonce"], sub or str(uuid4()), email, **claims)
    body = {"challenge_id": challenge["challenge_id"], "id_token": token}
    if locale:
        body["locale"] = locale
    return await client.post("/api/v1/auth/google", json=body)

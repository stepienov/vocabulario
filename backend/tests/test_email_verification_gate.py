"""Verification gate and Google address trust (E-001/F-004/T-002, step 4)."""

from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.api.v1 import auth as auth_api
from app.core import deps
from app.core.config import get_settings
from app.core.security import now_utc
from app.models import MailOutbox, User
from app.services.mail_outbox import _decrypt
from tests.pg_factories import auth_headers, create_user

pytestmark = pytest.mark.pg

# Reachable without a proven address: account state, recovery and cleanup only.
UNGATED = {
    ("GET", "/api/v1/me"),
    ("GET", "/api/v1/me/settings"),
    ("PUT", "/api/v1/me/settings"),
    ("POST", "/api/v1/auth/password/change"),
    ("POST", "/api/v1/auth/email-verification/request"),
    ("GET", "/api/v1/auth/email-verification/status"),
    ("DELETE", "/api/v1/devices/{token}"),
}
_GATED = {deps.get_verified_user, deps.get_verified_user_id, deps.get_admin_user}
_SIGNED_IN = {deps.get_current_user, deps.get_current_user_id}


def _auth_kind(dependant) -> str | None:
    for dep in dependant.dependencies:
        if dep.call in _GATED:
            return "gated"
        if dep.call in _SIGNED_IN:
            return "open"
        nested = _auth_kind(dep)
        if nested:
            return nested
    return None


def _api_routes(routes, prefix: str = ""):
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
        elif hasattr(route, "original_router"):  # FastAPI >= 0.141 lazy include
            inner = prefix + route.include_context.prefix
            yield from _api_routes(route.original_router.routes, inner)


def test_every_signed_in_route_is_gated_or_allowlisted():
    from app.main import create_app

    open_routes, gated = set(), 0
    for path, route in _api_routes(create_app().routes):
        kind = _auth_kind(route.dependant)
        if kind == "open":
            open_routes |= {(method, path) for method in route.methods}
        gated += kind == "gated"
    assert gated > 40
    assert open_routes == UNGATED


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "email_verification_gate", True)


async def _unverified(pg) -> tuple[User, dict[str, str]]:
    async with pg() as db:
        user = await create_user(db)
        return user, await auth_headers(db, user)


async def _learning_calls(client, headers) -> list[tuple[str, int, str | None]]:
    calls = [
        await client.get("/api/v1/profiles", headers=headers),
        await client.get("/api/v1/sync/pull", headers=headers),
        await client.post(
            "/api/v1/lookup/cached",
            json={"text": "casa", "profile_id": str(uuid4())},
            headers=headers,
        ),
        await client.post("/api/v1/devices/register", json={"token": "x" * 20}, headers=headers),
    ]
    out = []
    for response in calls:
        body = response.json() if response.content else None
        detail = body.get("detail") if isinstance(body, dict) else None
        code = detail.get("code") if isinstance(detail, dict) else None
        out.append((response.request.url.path, response.status_code, code))
    return out


async def test_gate_off_keeps_todays_access(pg, pg_client):
    _, headers = await _unverified(pg)
    for path, status, code in await _learning_calls(pg_client, headers):
        assert code != "email_verification_required", path
        assert status != 403, path


async def test_gate_blocks_unverified_until_link_confirmed(pg, pg_client, gate_on):
    user, headers = await _unverified(pg)
    for path, status, code in await _learning_calls(pg_client, headers):
        assert (path, status, code) == (path, 403, "email_verification_required")

    me = await pg_client.get("/api/v1/me", headers=headers)
    assert (me.status_code, me.json()["email_verified"]) == (200, False)
    assert (await pg_client.get("/api/v1/me/settings", headers=headers)).status_code == 200
    status = await pg_client.get("/api/v1/auth/email-verification/status", headers=headers)
    assert status.status_code == 200
    # The gate does not touch data: the account is still there, untouched.
    async with pg() as db:
        assert (await db.get(User, user.id)).email_verified_at is None

    async with pg() as db:
        (await db.get(User, user.id)).email_verified_at = now_utc()
        await db.commit()
    for path, status, code in await _learning_calls(pg_client, headers):
        assert status != 403 and code != "email_verification_required", path


def _fake_google(monkeypatch, **claims):
    async def verify(_token: str) -> dict:
        return claims

    monkeypatch.setattr(auth_api, "verify_google_id_token", verify)


async def _google_login(client, monkeypatch, **claims) -> User:
    _fake_google(monkeypatch, **claims)
    response = await client.post("/api/v1/auth/google", json={"id_token": "t", "locale": "pl"})
    assert response.status_code == 200, response.text
    return response.json()


async def _account(pg, email: str) -> tuple[User, list[MailOutbox]]:
    async with pg() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        mails = (
            await db.execute(select(MailOutbox).where(MailOutbox.user_id == user.id))
        ).scalars()
        return user, list(mails)


@pytest.mark.parametrize(
    ("email", "extra", "proven"),
    [
        ("anna@gmail.com", {"email_verified": "true"}, True),
        ("anna@firma.es", {"email_verified": "true", "hd": "firma.es"}, True),
        ("anna@gmail.com", {"email_verified": True}, True),
        ("anna@gmail.com", {"email_verified": "false"}, False),
        ("anna@outlook.com", {"email_verified": "true"}, False),
        ("anna@googlemail.com", {"email_verified": "true"}, False),
        ("anna@firma.es", {"email_verified": "true", "hd": ""}, False),
    ],
)
async def test_new_google_account_trusts_only_proven_addresses(
    pg, pg_client, monkeypatch, email, extra, proven
):
    email = email.replace("anna@", f"anna-{uuid4().hex[:8]}@")
    await _google_login(pg_client, monkeypatch, sub=str(uuid4()), email=email, **extra)
    user, mails = await _account(pg, email)
    assert (user.email_verified_at is not None) is proven
    assert [m.kind for m in mails] == ([] if proven else ["verify_email"])
    if not proven:
        assert _decrypt(mails[0]).locale == "pl"


async def test_google_link_by_email_is_not_proof_but_returning_sub_is(pg, pg_client, monkeypatch):
    email = f"owner-{uuid4().hex[:8]}@gmail.com"
    async with pg() as db:
        await create_user(db, email=email)
        await db.commit()
    sub = str(uuid4())
    claims = {"sub": sub, "email": email, "email_verified": "true"}

    await _google_login(pg_client, monkeypatch, **claims)
    user, mails = await _account(pg, email)
    assert (user.google_id, user.email_verified_at, mails) == (sub, None, [])

    await _google_login(pg_client, monkeypatch, **claims)
    assert (await _account(pg, email))[0].email_verified_at is not None


async def test_returning_sub_with_other_address_does_not_verify(pg, pg_client, monkeypatch):
    sub = str(uuid4())
    email = f"first-{uuid4().hex[:8]}@outlook.com"
    await _google_login(pg_client, monkeypatch, sub=sub, email=email, email_verified="true")
    await _google_login(
        pg_client,
        monkeypatch,
        sub=sub,
        email=f"x-{uuid4().hex[:8]}@gmail.com",
        email_verified="true",
    )
    user, mails = await _account(pg, email)
    assert user.email_verified_at is None
    assert [m.kind for m in mails] == ["verify_email"]

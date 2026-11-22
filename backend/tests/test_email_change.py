"""Adding a password to a Google account (E-001/F-004/T-005)."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import now_utc
from app.models import AuthSession, User
from app.services.auth_sessions import AccessContext, create_session
from app.services.mail_outbox import _decrypt
from app.services.recent_auth import issue_recent_auth
from tests.test_account_recovery import (
    NEW_PASSWORD,
    PASSWORD,
    _bearer,
    _code,
    _login,
    _outbox,
    _register,
    _user,
)

pytestmark = pytest.mark.pg


async def _verified(pg, client, prefix: str = "chg") -> tuple[str, dict]:
    email = f"{prefix}-{uuid4()}@test.com"
    tokens = await _register(client, email)
    async with pg() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.email_verified_at = now_utc()
        await db.commit()
    return email, tokens


async def _proof(client, tokens, password: str = PASSWORD, action: str = "change_email") -> str:
    response = await client.post(
        "/api/v1/auth/recent-auth/password",
        json={"password": password, "action": action},
        headers=_bearer(tokens),
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["recent_auth_token"]


async def _google_only(pg, *, verified: bool = True):
    async with pg() as db:
        user = User(
            email=f"g-{uuid4()}@test.com",
            google_id=f"sub-{uuid4()}",
            email_verified_at=now_utc() if verified else None,
        )
        db.add(user)
        await db.flush()
        issued = await create_session(db, user.id)
        await db.commit()
    return user, issued


async def _add_proof(pg, user, issued) -> str:
    async with pg() as db:
        locked = await db.get(User, user.id)
        token, _ = await issue_recent_auth(
            db, locked, AccessContext(user.id, issued.session_id, 1), "add_password"
        )
        await db.commit()
    return token


async def _add(client, issued, password: str, proof: str):
    return await client.post(
        "/api/v1/auth/password/add",
        json={"new_password": password, "recent_auth_token": proof},
        headers={"Authorization": f"Bearer {issued.access_token}"},
    )


async def test_add_password_to_google_account(pg, pg_client):
    user, current = await _google_only(pg)
    async with pg() as db:
        other = await create_session(db, user.id)
        await db.commit()
    proof = await _add_proof(pg, user, current)

    weak = await _add(pg_client, current, "short", proof)
    assert (weak.status_code, _code(weak)) == (422, "password_too_short")
    done = await _add(pg_client, current, NEW_PASSWORD, proof)
    assert done.status_code == 200, done.text
    fresh = done.json()

    me = await pg_client.get("/api/v1/me", headers=_bearer(fresh))
    assert me.json()["login_methods"] == ["password", "google"]
    for stale in (current.access_token, other.access_token):
        old = await pg_client.get("/api/v1/me", headers={"Authorization": f"Bearer {stale}"})
        assert old.status_code == 401
    stored = await _user(pg, user.email)
    assert stored.password_hash.startswith("$argon2id$")
    assert stored.google_id == user.google_id
    [notice] = await _outbox(pg, "password_added")
    assert _decrypt(notice).to == user.email
    assert (await _login(pg_client, user.email, NEW_PASSWORD)).status_code == 200

    async with pg() as db:
        again = await _add_proof_row(db, user, fresh["session_id"])
    overwrite = await _add(
        pg_client, _Issued(fresh["access_token"]), NEW_PASSWORD + "!", again
    )
    assert (overwrite.status_code, _code(overwrite)) == (409, "password_already_set")


class _Issued:
    def __init__(self, access_token: str) -> None:
        self.access_token = access_token


async def _add_proof_row(db, user, session_id) -> str:
    row = await db.get(AuthSession, session_id)
    locked = await db.get(User, user.id)
    token, _ = await issue_recent_auth(
        db, locked, AccessContext(user.id, row.id, row.version), "add_password"
    )
    await db.commit()
    return token


async def test_add_password_needs_verified_address_and_a_fresh_proof(pg, pg_client):
    user, issued = await _google_only(pg, verified=False)
    proof = await _add_proof(pg, user, issued)
    blocked = await _add(pg_client, issued, NEW_PASSWORD, proof)
    assert (blocked.status_code, _code(blocked)) == (403, "email_verification_required")

    verified, ok_session = await _google_only(pg)
    missing = await _add(pg_client, ok_session, NEW_PASSWORD, "garbage")
    assert (missing.status_code, _code(missing)) == (403, "recent_auth_required")
    wrong_action = await _proof_for(pg, verified, ok_session, "change_email")
    refused = await _add(pg_client, ok_session, NEW_PASSWORD, wrong_action)
    assert (refused.status_code, _code(refused)) == (403, "recent_auth_required")
    assert (await _user(pg, verified.email)).password_hash is None


async def _proof_for(pg, user, issued, action: str) -> str:
    async with pg() as db:
        locked = await db.get(User, user.id)
        token, _ = await issue_recent_auth(
            db, locked, AccessContext(user.id, issued.session_id, 1), action
        )
        await db.commit()
    return token

"""Revocable sessions through the HTTP API (E-001/F-003/T-001)."""

from datetime import timedelta
from uuid import uuid1, uuid4

import pytest
from jose import jwt
from sqlalchemy import event, update

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import User
from app.services import auth_sessions as svc
from tests.pg_factories import create_profile, create_user

pytestmark = pytest.mark.pg

PASSWORD = "correct horse battery"


async def _register(client, email=None) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email or f"api-{uuid4()}@test.com", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def _bearer(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def _refresh(client, refresh_token, request_id=None):
    return await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token, "request_id": str(request_id or uuid4())},
    )


async def test_register_login_refresh_and_logout_flow(pg, pg_client):
    email = f"flow-{uuid4()}@test.com"
    registered = await _register(pg_client, email)
    assert registered["token_type"] == "bearer"
    assert 0 < registered["expires_in"] <= get_settings().access_token_expire_minutes * 60
    me = await pg_client.get("/api/v1/me", headers=_bearer(registered))
    assert me.status_code == 200
    assert me.json()["id"] == registered["user_id"]

    logins = [
        await pg_client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        for _ in range(2)
    ]
    assert [r.status_code for r in logins] == [200, 200]
    assert logins[0].json()["session_id"] != logins[1].json()["session_id"]

    request_id = uuid4()
    first = await _refresh(pg_client, registered["refresh_token"], request_id)
    retry = await _refresh(pg_client, registered["refresh_token"], request_id)
    assert first.status_code == retry.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["access_token"] == retry.json()["access_token"]
    assert first.json()["session_id"] == registered["session_id"]
    conflict = await _refresh(pg_client, registered["refresh_token"])
    assert (conflict.status_code, _code(conflict)) == (409, "refresh_conflict")

    rotated = first.json()
    for _ in range(2):
        out = await pg_client.post(
            "/api/v1/auth/logout", json={"refresh_token": rotated["refresh_token"]}
        )
        assert out.status_code == 204
    me = await pg_client.get("/api/v1/me", headers=_bearer(rotated))
    assert (me.status_code, _code(me)) == (401, "session_revoked")
    again = await _refresh(pg_client, rotated["refresh_token"])
    assert (again.status_code, _code(again)) == (401, "session_revoked")
    other = await pg_client.get("/api/v1/me", headers=_bearer(logins[0].json()))
    assert other.status_code == 200


async def test_refresh_and_logout_validate_input(pg, pg_client):
    tokens = await _register(pg_client)
    missing = await pg_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    not_v4 = await _refresh(pg_client, tokens["refresh_token"], uuid1())
    assert missing.status_code == not_v4.status_code == 422
    wrong_type = await _refresh(pg_client, tokens["access_token"])
    assert (wrong_type.status_code, _code(wrong_type)) == (401, "invalid_refresh_token")
    bad_logout = await pg_client.post("/api/v1/auth/logout", json={"refresh_token": "x.y.z"})
    assert (bad_logout.status_code, _code(bad_logout)) == (401, "invalid_refresh_token")
    still = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
    assert still.status_code == 200


async def test_legacy_tokens_require_upgrade_and_never_authorize(pg, pg_client):
    tokens = await _register(pg_client)
    settings = get_settings()
    exp = now_utc() + timedelta(minutes=5)

    def legacy(token_type: str) -> str:
        payload = {"sub": tokens["user_id"], "type": token_type, "exp": exp}
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    me = await pg_client.get("/api/v1/me", headers={"Authorization": f"Bearer {legacy('access')}"})
    assert (me.status_code, _code(me)) == (401, "session_upgrade_required")
    refreshed = await _refresh(pg_client, legacy("refresh"))
    assert (refreshed.status_code, _code(refreshed)) == (401, "session_upgrade_required")
    garbage = await pg_client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})
    assert (garbage.status_code, _code(garbage)) == (401, "invalid_token")


async def test_revocation_applies_to_both_auth_dependencies_and_admin(pg, pg_client):
    async with pg() as db:
        user = await create_user(db)
        await db.execute(update(User).where(User.id == user.id).values(role="admin"))
        profile = await create_profile(db, user, "pl", "es")
        first = await svc.create_session(db, user.id)
        second = await svc.create_session(db, user.id)
        await db.commit()
    lookup = {"text": "prado", "profile_id": str(profile.id), "local_membership": True}

    async def statuses(issued) -> list[int]:
        headers = {"Authorization": f"Bearer {issued.access_token}"}
        return [
            (await pg_client.get("/api/v1/me", headers=headers)).status_code,
            (await pg_client.get("/api/v1/admin/logs", headers=headers)).status_code,
            (await pg_client.post("/api/v1/lookup/cached", headers=headers, json=lookup)).status_code,
        ]

    assert 401 not in await statuses(first)
    async with pg() as db:
        await svc.lock_user(db, user.id)
        await svc.revoke_user_sessions(db, user.id, "password_reset")
        await db.commit()
    assert await statuses(first) == [401, 401, 401]
    assert await statuses(second) == [401, 401, 401]
    login_again = await pg_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first.refresh_token, "request_id": str(uuid4())},
    )
    assert _code(login_again) == "session_revoked"


async def test_one_session_read_per_request(pg, pg_client):
    tokens = await _register(pg_client)
    from app.db import session as db_session

    reads: list[str] = []

    def _before(conn, cursor, statement, parameters, context, executemany):
        if "auth_sessions" in statement.lower():
            reads.append(statement)

    event.listen(db_session.engine.sync_engine, "before_cursor_execute", _before)
    try:
        response = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
    finally:
        event.remove(db_session.engine.sync_engine, "before_cursor_execute", _before)
    assert response.status_code == 200
    assert len(reads) == 1

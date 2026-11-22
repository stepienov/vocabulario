"""Revocable sessions: service contract on real PostgreSQL (E-001/F-003/T-001)."""

import asyncio
import base64
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from jose import jwt
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import ACCESS, REFRESH, TokenError, now_utc, read_token
from app.db.base import Base
from app.db.migrations import apply_schema
from app.models import AuthRefreshRetry, AuthSession
from app.services import auth_sessions as svc
from app.services.auth_sessions import RetryRecordError, SessionAuthError
from tests.pg_factories import create_user

pytestmark = pytest.mark.pg


async def _user_with_session(pg, now=None):
    async with pg() as db:
        user = await create_user(db)
        issued = await svc.create_session(db, user.id, now=now)
        await db.commit()
    return user, issued


async def _refresh(pg, token, request_id, now=None):
    async with pg() as db:
        try:
            issued = await svc.refresh_session(db, token, request_id, now=now)
        except SessionAuthError as exc:
            if exc.commit:
                await db.commit()
            raise
        await db.commit()
        return issued


async def _session(pg, session_id) -> AuthSession:
    async with pg() as db:
        return await db.get(AuthSession, session_id)


async def _retry_count(pg) -> int:
    async with pg() as db:
        return await db.scalar(select(func.count()).select_from(AuthRefreshRetry))


async def _code(coro) -> tuple[int, str]:
    with pytest.raises(SessionAuthError) as info:
        await coro
    return info.value.status_code, info.value.code


async def test_two_logins_in_the_same_second_get_distinct_sessions(pg):
    now = now_utc()
    async with pg() as db:
        user = await create_user(db)
        first = await svc.create_session(db, user.id, now=now)
        second = await svc.create_session(db, user.id, now=now)
        await db.commit()
    assert first.session_id != second.session_id
    tokens = [first.access_token, first.refresh_token, second.access_token, second.refresh_token]
    assert len(set(tokens)) == 4
    jtis = {
        read_token(first.access_token, ACCESS).token_id,
        read_token(first.refresh_token, REFRESH).token_id,
        read_token(second.access_token, ACCESS).token_id,
    }
    assert len(jtis) == 3
    assert read_token(second.access_token, ACCESS).user_id == user.id
    ttl = get_settings().access_token_expire_minutes * 60
    assert ttl - 1 <= first.expires_in(now) <= ttl


async def test_refresh_rotates_and_keeps_the_session_id(pg):
    _, issued = await _user_with_session(pg)
    rotated = await _refresh(pg, issued.refresh_token, uuid4())
    assert rotated.session_id == issued.session_id
    assert rotated.refresh_token != issued.refresh_token
    stored = await _session(pg, issued.session_id)
    assert stored.refresh_token_hash == svc.token_hash(rotated.refresh_token)
    assert stored.version == 1
    again = await _refresh(pg, rotated.refresh_token, uuid4())
    assert again.session_id == issued.session_id


async def test_same_request_id_returns_the_same_pair_without_rotating_again(pg):
    _, issued = await _user_with_session(pg)
    request_id = uuid4()
    first = await _refresh(pg, issued.refresh_token, request_id)
    before = await _session(pg, issued.session_id)
    retry = await _refresh(pg, issued.refresh_token, request_id)
    after = await _session(pg, issued.session_id)
    assert (retry.access_token, retry.refresh_token) == (first.access_token, first.refresh_token)
    assert after.refreshed_at == before.refreshed_at
    assert after.refresh_token_hash == before.refresh_token_hash
    assert await _retry_count(pg) == 1


async def test_parallel_refresh_with_the_same_id_commits_one_rotation(pg):
    _, issued = await _user_with_session(pg)
    request_id = uuid4()
    first, second = await asyncio.gather(
        _refresh(pg, issued.refresh_token, request_id),
        _refresh(pg, issued.refresh_token, request_id),
    )
    assert (first.access_token, first.refresh_token) == (second.access_token, second.refresh_token)
    assert await _retry_count(pg) == 1


async def test_conflicting_retries_are_409_and_keep_the_session(pg):
    _, issued = await _user_with_session(pg)
    request_id = uuid4()
    rotated = await _refresh(pg, issued.refresh_token, request_id)
    assert await _code(_refresh(pg, issued.refresh_token, uuid4())) == (409, "refresh_conflict")
    assert await _code(_refresh(pg, rotated.refresh_token, request_id)) == (409, "refresh_conflict")
    await _refresh(pg, rotated.refresh_token, uuid4())
    assert await _code(_refresh(pg, issued.refresh_token, request_id)) == (409, "refresh_conflict")
    assert (await _session(pg, issued.session_id)).revoked_at is None


async def test_lost_refresh_response_can_be_recovered_after_a_century(pg):
    now = now_utc()
    user, issued = await _user_with_session(pg, now=now)
    async with pg() as db:
        other = await svc.create_session(db, user.id, now=now)
        await db.commit()
    request_id = uuid4()
    original = await _refresh(pg, issued.refresh_token, request_id, now=now)
    edge = now + svc.RETRY_WINDOW - timedelta(seconds=1)
    retry = await _refresh(pg, issued.refresh_token, request_id, now=edge)
    assert retry.access_token == original.access_token
    late = now + timedelta(days=36525)
    recovered = await _refresh(pg, issued.refresh_token, request_id, now=late)
    assert recovered.refresh_token == original.refresh_token
    assert recovered.access_token != original.access_token
    assert read_token(recovered.access_token, ACCESS, now=late).session_id == issued.session_id
    assert await _code(_refresh(pg, issued.refresh_token, uuid4(), now=late)) == (
        401,
        "session_revoked",
    )
    stored = await _session(pg, issued.session_id)
    assert stored.revocation_reason == "refresh_reuse"
    assert await _retry_count(pg) == 0
    assert (await _session(pg, other.session_id)).revoked_at is None


async def test_reused_old_token_with_a_new_id_after_the_window_revokes(pg):
    now = now_utc()
    _, issued = await _user_with_session(pg, now=now)
    await _refresh(pg, issued.refresh_token, uuid4(), now=now)
    late = now + svc.RETRY_WINDOW + timedelta(seconds=1)
    assert await _code(_refresh(pg, issued.refresh_token, uuid4(), now=late)) == (
        401,
        "session_revoked",
    )


async def test_logout_revokes_once_and_rejects_stale_proof(pg):
    _, issued = await _user_with_session(pg)
    rotated = await _refresh(pg, issued.refresh_token, uuid4())
    async with pg() as db:
        assert await _code(svc.logout_session(db, issued.refresh_token)) == (
            401,
            "invalid_refresh_token",
        )
    for _ in range(2):
        async with pg() as db:
            await svc.logout_session(db, rotated.refresh_token)
            await db.commit()
    stored = await _session(pg, issued.session_id)
    assert stored.revocation_reason == "logout"
    assert await _code(_refresh(pg, rotated.refresh_token, uuid4())) == (401, "session_revoked")
    claims = svc.access_claims(rotated.access_token)
    assert await _code(_check(stored, claims)) == (401, "session_revoked")


async def _check(session, claims, now=None):
    return svc.check_access_session(claims, session, now)


async def test_revoke_all_except_current_and_renew_invalidate_old_tokens(pg):
    user, current = await _user_with_session(pg)
    async with pg() as db:
        other = await svc.create_session(db, user.id)
        await db.commit()
    async with pg() as db:
        await svc.lock_user(db, user.id)
        count = await svc.revoke_user_sessions(
            db, user.id, "password_change", keep_session_id=current.session_id
        )
        renewed = await svc.renew_session(db, user.id, current.session_id)
        await db.commit()
    assert count == 1
    assert (await _session(pg, other.session_id)).revocation_reason == "password_change"
    stored = await _session(pg, current.session_id)
    assert stored.version == 2
    old_claims = svc.access_claims(current.access_token)
    assert await _code(_check(stored, old_claims)) == (401, "invalid_token")
    context = svc.check_access_session(svc.access_claims(renewed.access_token), stored)
    assert context.session_version == 2
    assert await _code(_refresh(pg, current.refresh_token, uuid4())) == (
        401,
        "invalid_refresh_token",
    )
    await _refresh(pg, renewed.refresh_token, uuid4())


async def test_session_can_refresh_after_a_century_and_still_be_revoked(pg):
    now = now_utc()
    _, issued = await _user_with_session(pg, now=now)
    later = now + timedelta(days=36525)
    assert read_token(issued.refresh_token, REFRESH, now=later).expires_at is None
    with pytest.raises(TokenError, match="expired"):
        read_token(issued.access_token, ACCESS, now=later)
    rotated = await _refresh(pg, issued.refresh_token, uuid4(), now=later)
    async with pg() as db:
        await svc.logout_session(db, rotated.refresh_token, now=later)
        await db.commit()
    assert await _code(_refresh(pg, rotated.refresh_token, uuid4(), now=later)) == (
        401, "session_revoked"
    )


async def test_migration_preserves_live_old_sessions_without_reviving_expired_or_revoked(pg):
    now = now_utc()
    _, live = await _user_with_session(pg, now=now)
    _, expired = await _user_with_session(pg, now=now)
    _, revoked = await _user_with_session(pg, now=now)
    old_claims = jwt.get_unverified_claims(live.refresh_token)
    old_claims["exp"] = int((now + timedelta(days=30)).timestamp())
    old_token = _encode(old_claims)
    async with pg() as db:
        live_row = await db.get(AuthSession, live.session_id)
        live_row.refresh_token_hash = svc.token_hash(old_token)
        live_row.expires_at = now + timedelta(days=30)
        expired_row = await db.get(AuthSession, expired.session_id)
        expired_row.expires_at = now - timedelta(seconds=1)
        revoked_row = await db.get(AuthSession, revoked.session_id)
        revoked_row.expires_at = now + timedelta(days=30)
        revoked_row.revoked_at = now
        revoked_row.revocation_reason = "logout"
        await db.commit()
    await apply_schema(pg.kw["bind"], Base.metadata)
    await apply_schema(pg.kw["bind"], Base.metadata)
    assert (await _session(pg, live.session_id)).expires_at is None
    assert (await _session(pg, expired.session_id)).expires_at is not None
    assert (await _session(pg, revoked.session_id)).expires_at is not None
    later = now + timedelta(days=36525)
    rotated = await _refresh(pg, old_token, uuid4(), now=later)
    assert rotated.session_id == live.session_id
    assert await _code(_refresh(pg, expired.refresh_token, uuid4(), now=now)) == (
        401, "session_expired"
    )
    assert await _code(_refresh(pg, revoked.refresh_token, uuid4(), now=now)) == (
        401, "session_revoked"
    )


async def test_tampered_retry_record_is_a_server_error(pg):
    _, issued = await _user_with_session(pg)
    request_id = uuid4()
    await _refresh(pg, issued.refresh_token, request_id)
    async with pg() as db:
        row = await db.get(AuthRefreshRetry, (issued.session_id, request_id))
        row.response_ciphertext = b"garbage"
        await db.commit()
    with pytest.raises(RetryRecordError):
        await _refresh(pg, issued.refresh_token, request_id)


def _encode(payload: dict) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _reason(token: str, token_type: str = ACCESS) -> str:
    with pytest.raises(TokenError) as info:
        read_token(token, token_type)
    return info.value.reason


def test_legacy_and_malformed_tokens_are_classified():
    exp = int((now_utc() + timedelta(minutes=5)).timestamp())
    legacy = {"sub": str(uuid4()), "type": "access", "exp": exp}
    assert _reason(_encode(legacy)) == "legacy"
    assert _reason(_encode({**legacy, "exp": exp - 3600})) == "invalid"
    assert _reason(_encode(legacy), REFRESH) == "invalid"
    good = {
        "v": 2,
        "iss": "vocabulario-api",
        "aud": "vocabulario-android",
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "sv": 1,
        "jti": str(uuid4()),
        "type": "access",
        "iat": exp - 60,
        "exp": exp,
    }
    assert read_token(_encode(good), ACCESS).session_version == 1
    for broken in (
        {"aud": "someone-else"},
        {"iss": "someone-else"},
        {"v": 3},
        {"sv": 0},
        {"sv": True},
        {"sid": "not-a-uuid"},
        {"type": "refresh"},
    ):
        assert _reason(_encode({**good, **broken})) == "invalid", broken
    assert _reason(_encode({**good, "iat": exp - 7200, "exp": exp - 3600})) == "expired"
    assert _reason(_unsigned(good)) == "invalid"
    assert _reason("not.a.jwt") == "invalid"


def _unsigned(payload: dict) -> str:
    def part(data: dict) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(payload)}."

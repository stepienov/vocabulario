"""E-001/F-004/T-003: PostgreSQL-backed auth limiter, budgets and neutral login answers."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from starlette.requests import Request

from app.core.config import get_settings
from app.core.security import now_utc
from app.db import session as db_session
from app.models import AuthRateBucket, MailOutbox, MailProviderEvent, User
from app.services.auth_cleanup import purge_auth_records
from app.services.auth_limits import (
    MAIL_BUDGET_ALL,
    MIN,
    RateLimited,
    Rule,
    client_ip,
    count,
    link_budget_open,
    reserve,
    reserve_mail_send,
    subject_hash,
)
from tests.pg_factories import create_user

pytestmark = pytest.mark.pg

PASSWORD = "correct horse battery"


def _code(response) -> str:
    return response.json()["detail"]["code"]


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


async def test_window_edges_and_retry_after(pg):
    t0 = now_utc()
    rule = Rule("t_window", "s", 2, timedelta(seconds=60))
    await reserve(rule, now=t0)
    await reserve(rule, now=t0 + timedelta(seconds=10))
    with pytest.raises(RateLimited) as blocked:
        await reserve(rule, now=t0 + timedelta(seconds=20))
    assert blocked.value.retry_after == 40
    # A rejected attempt is not recorded, so the first hit frees a slot exactly at +60 s.
    await reserve(rule, now=t0 + timedelta(seconds=60))
    with pytest.raises(RateLimited) as again:
        await reserve(rule, now=t0 + timedelta(seconds=61))
    assert again.value.retry_after == 9


async def test_reserve_is_all_or_nothing_and_retry_uses_latest_release(pg):
    t0 = now_utc()
    strict = Rule("t_strict", "s", 1, 5 * MIN)
    loose = Rule("t_loose", "s", 5, MIN)
    await reserve(strict, now=t0)
    with pytest.raises(RateLimited) as blocked:
        await reserve(loose, strict, now=t0 + timedelta(seconds=30))
    assert blocked.value.retry_after == 270
    assert await count(loose, now=t0 + timedelta(seconds=30)) == 0


async def test_concurrent_reservations_never_exceed_the_limit(pg):
    rule = Rule("t_race", "s", 3, 10 * MIN)

    async def attempt() -> bool:
        try:
            await reserve(rule)
            return True
        except RateLimited:
            return False

    results = await asyncio.gather(*(attempt() for _ in range(12)))
    assert results.count(True) == 3


async def test_buckets_store_hashes_not_subjects(pg):
    await reserve(Rule("t_hash", "someone@private.example", 5, MIN))
    async with pg() as db:
        stored = (await db.execute(select(AuthRateBucket.subject_hash))).scalars().all()
    assert stored and all("private" not in value for value in stored)


def test_client_ip_uses_peer_unless_proxies_are_trusted(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    assert client_ip(_request("10.0.0.1", "6.6.6.6")) == "10.0.0.1"
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    # The client-supplied left entries are ignored; the proxy appended the last one.
    assert client_ip(_request("10.0.0.1", "6.6.6.6, 203.0.113.9")) == "203.0.113.9"
    assert client_ip(_request("10.0.0.1")) == "10.0.0.1"
    assert client_ip(_request("2001:db8::1", None)) == client_ip(_request("2001:db8::2", None))


async def test_login_answers_are_identical_and_limited(pg, pg_client):
    email = f"known-{uuid4()}@test.com"
    registered = await pg_client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registered.status_code == 200
    async with pg() as db:
        google_only = await create_user(db)
        await db.commit()

    async def login(address: str, password: str = "wrong password here"):
        return await pg_client.post(
            "/api/v1/auth/login", json={"email": address, "password": password}
        )

    answers = [
        await login(email),
        await login(f"nobody-{uuid4()}@test.com"),
        await login(google_only.email),
    ]
    assert {(r.status_code, _code(r)) for r in answers} == {(401, "invalid_credentials")}
    assert len({r.json()["detail"]["message"] for r in answers}) == 1

    for _ in range(4):
        assert (await login(email)).status_code == 401
    blocked = await login(email, PASSWORD)
    assert (blocked.status_code, _code(blocked)) == (429, "rate_limited")
    assert int(blocked.headers["Retry-After"]) >= 1
    other = await login(f"other-{uuid4()}@test.com")
    assert other.status_code == 401


async def test_parallel_registrations_of_one_address_give_one_conflict(pg, pg_client):
    email = f"race-{uuid4()}@test.com"
    responses = await asyncio.gather(
        *(
            pg_client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
            for _ in range(2)
        )
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 409]
    loser = next(r for r in responses if r.status_code == 409)
    assert _code(loser) == "email_taken"
    async with pg() as db:
        assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 1


async def test_validation_errors_do_not_echo_input(pg, pg_client):
    secret = "my-secret-password-value"
    response = await pg_client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": secret}
    )
    assert response.status_code == 422
    assert secret not in response.text and "input" not in response.text


async def test_exhausted_link_budget_refuses_new_link_mail_requests(pg, pg_client):
    now = now_utc()
    async with pg() as db:
        user = await create_user(db)
        await db.commit()
    await _fill(MAIL_BUDGET_ALL[0], now)
    assert not await link_budget_open()
    register = await pg_client.post(
        "/api/v1/auth/register",
        json={"email": f"late-{uuid4()}@test.com", "password": PASSWORD},
    )
    assert (register.status_code, _code(register)) == (503, "mail_temporarily_unavailable")
    reset = await pg_client.post("/api/v1/auth/password-reset/request", json={"email": user.email})
    assert (reset.status_code, _code(reset)) == (503, "mail_temporarily_unavailable")
    async with pg() as db:
        assert (await db.execute(select(func.count()).select_from(MailOutbox))).scalar_one() == 0


async def _fill(rule: Rule, now) -> None:
    """Put the bucket of `rule` at its limit, creating it when missing."""
    key = (rule.scope, subject_hash(rule.scope, rule.subject))
    async with db_session.async_session_factory() as db:
        bucket = await db.get(AuthRateBucket, key)
        if bucket is None:
            bucket = AuthRateBucket(scope=key[0], subject_hash=key[1], expires_at=now + rule.window)
            db.add(bucket)
        bucket.hits = [now] * rule.limit
        await db.commit()


async def test_mail_send_budget_blocks_and_recovers(pg):
    now = now_utc()
    assert await reserve_mail_send(link=False, now=now) is None
    await _fill(MAIL_BUDGET_ALL[0], now)
    wait = await reserve_mail_send(link=False, now=now + timedelta(seconds=1))
    assert wait is not None and wait > 0
    assert await reserve_mail_send(link=False, now=now + timedelta(hours=24, seconds=1)) is None

async def test_purge_removes_only_expired_technical_records(pg):
    now = now_utc()
    old = now - timedelta(days=8)
    async with pg() as db:
        db.add_all(
            [
                AuthRateBucket(
                    scope="t_old", subject_hash="a", hits=[], expires_at=now - timedelta(hours=25)
                ),
                AuthRateBucket(scope="t_new", subject_hash="b", hits=[], expires_at=now),
                MailProviderEvent(
                    svix_id="old", provider_message_id="m", event_type="email.sent",
                    occurred_at=old, received_at=old,
                ),
                MailProviderEvent(
                    svix_id="new", provider_message_id="m", event_type="email.sent",
                    occurred_at=now, received_at=now,
                ),
            ]
        )
        await db.commit()
    counts = await purge_auth_records(now=now)
    assert counts["rate_buckets"] == 1 and counts["provider_events"] == 1
    async with pg() as db:
        assert (await db.execute(select(AuthRateBucket.scope))).scalars().all() == ["t_new"]
        assert (await db.execute(select(MailProviderEvent.svix_id))).scalars().all() == ["new"]

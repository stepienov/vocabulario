"""E-001/F-004/T-002: one-time e-mail link proofs on real PostgreSQL."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import now_utc
from app.models import AccountActionToken, User
from app.services.action_tokens import (
    RESET_PASSWORD,
    VERIFY_EMAIL,
    ActionTokenError,
    action_token_is_current,
    consume_action_token,
    find_token_owner,
    issue_action_token,
)
from app.services.auth_sessions import lock_user
from tests.pg_factories import create_user

pytestmark = pytest.mark.pg


async def _issue(pg, purpose, now=None):
    async with pg() as session:
        user = await create_user(session)
        issued = await issue_action_token(session, user, purpose, now=now)
        await session.commit()
        return user.id, issued.token, issued.row.id


async def _consume(pg, token, purpose, now=None):
    async with pg() as session:
        owner = await find_token_owner(session, token, purpose)
        user = await lock_user(session, owner)
        row = await consume_action_token(session, user, token, purpose, now=now)
        await session.commit()
        return row


async def _code(coro):
    with pytest.raises(ActionTokenError) as caught:
        await coro
    return caught.value.status_code, caught.value.code


async def test_only_the_hash_is_stored_and_ttls_follow_the_purpose(pg):
    now = now_utc()
    _, verify, verify_id = await _issue(pg, VERIFY_EMAIL, now)
    _, reset, reset_id = await _issue(pg, RESET_PASSWORD, now)
    async with pg() as session:
        rows = {r.id: r for r in (await session.execute(select(AccountActionToken))).scalars()}
    assert len(verify) >= 43 and len(reset) >= 43
    for row, token in ((rows[verify_id], verify), (rows[reset_id], reset)):
        assert token not in row.token_hash and len(row.token_hash) == 64
    assert rows[verify_id].expires_at - rows[verify_id].created_at == timedelta(hours=24)
    assert rows[reset_id].expires_at - rows[reset_id].created_at == timedelta(minutes=30)


async def test_valid_token_is_consumed_once(pg):
    _, token, _ = await _issue(pg, RESET_PASSWORD)
    row = await _consume(pg, token, RESET_PASSWORD)
    assert row.consumed_at is not None
    assert await _code(_consume(pg, token, RESET_PASSWORD)) == (409, "action_token_used")


async def test_wrong_purpose_unknown_and_oversized_tokens_are_invalid(pg):
    _, token, _ = await _issue(pg, VERIFY_EMAIL)
    invalid = (400, "action_token_invalid")
    assert await _code(_consume(pg, token, RESET_PASSWORD)) == invalid
    assert await _code(_consume(pg, token + "x", VERIFY_EMAIL)) == invalid
    assert await _code(_consume(pg, "", VERIFY_EMAIL)) == invalid
    assert await _code(_consume(pg, "a" * 500, VERIFY_EMAIL)) == invalid
    await _consume(pg, token, VERIFY_EMAIL)


async def test_expiry_boundary(pg):
    issued_at = now_utc()
    _, token, _ = await _issue(pg, RESET_PASSWORD, issued_at)
    deadline = issued_at + timedelta(minutes=30)
    assert await _code(_consume(pg, token, RESET_PASSWORD, now=deadline)) == (
        410,
        "action_token_expired",
    )
    row = await _consume(pg, token, RESET_PASSWORD, now=deadline - timedelta(microseconds=1))
    assert row.consumed_at is not None


async def test_credentials_change_kills_reset_but_not_verification(pg):
    async with pg() as session:
        user = await create_user(session)
        reset = await issue_action_token(session, user, RESET_PASSWORD)
        verify = await issue_action_token(session, user, VERIFY_EMAIL)
        user.credentials_revision += 1
        await session.commit()
    assert await _code(_consume(pg, reset.token, RESET_PASSWORD)) == (400, "action_token_invalid")
    await _consume(pg, verify.token, VERIFY_EMAIL)


async def test_email_change_kills_every_link_of_the_old_address(pg):
    async with pg() as session:
        user = await create_user(session)
        reset = await issue_action_token(session, user, RESET_PASSWORD)
        verify = await issue_action_token(session, user, VERIFY_EMAIL)
        user.email_revision += 1
        await session.commit()
        reset_id, verify_id = reset.row.id, verify.row.id
    invalid = (400, "action_token_invalid")
    assert await _code(_consume(pg, reset.token, RESET_PASSWORD)) == invalid
    assert await _code(_consume(pg, verify.token, VERIFY_EMAIL)) == invalid
    async with pg() as session:
        assert not await action_token_is_current(session, reset_id)
        assert not await action_token_is_current(session, verify_id)


async def test_failed_transaction_does_not_use_the_token(pg):
    _, token, token_id = await _issue(pg, RESET_PASSWORD)
    async with pg() as session:
        owner = await find_token_owner(session, token, RESET_PASSWORD)
        user = await lock_user(session, owner)
        await consume_action_token(session, user, token, RESET_PASSWORD)
        await session.rollback()
    async with pg() as session:
        assert await action_token_is_current(session, token_id)
    await _consume(pg, token, RESET_PASSWORD)


async def test_concurrent_consumption_has_exactly_one_winner(pg):
    _, token, _ = await _issue(pg, RESET_PASSWORD)
    results = await asyncio.gather(
        _consume(pg, token, RESET_PASSWORD),
        _consume(pg, token, RESET_PASSWORD),
        return_exceptions=True,
    )
    winners = [r for r in results if isinstance(r, AccountActionToken)]
    losers = [r for r in results if isinstance(r, ActionTokenError)]
    assert len(winners) == 1
    assert [e.code for e in losers] == ["action_token_used"]


async def test_deleting_the_user_removes_its_tokens(pg):
    user_id, token, _ = await _issue(pg, VERIFY_EMAIL)
    async with pg() as session:
        await session.delete(await session.get(User, user_id))
        await session.commit()
    async with pg() as session:
        assert (await session.execute(select(AccountActionToken))).first() is None
    assert await _code(_consume(pg, token, VERIFY_EMAIL)) == (400, "action_token_invalid")


async def test_migration_gives_existing_accounts_no_verification_proof(pg):
    from sqlalchemy import text

    from app.db import session as db_session
    from app.db.base import Base
    from app.db.migrations import apply_schema

    engine = db_session.engine
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "ALTER TABLE users DROP COLUMN email_verified_at, "
                    "DROP COLUMN email_revision, DROP COLUMN credentials_revision"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, role, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), 'old@test.com', 'user', now(), now())"
                )
            )
    finally:
        # Restores the columns for the rest of the run even if the setup above fails.
        await apply_schema(engine, Base.metadata)
    async with pg() as session:
        user = (
            await session.execute(select(User).where(User.email == "old@test.com"))
        ).scalar_one()
    assert user.email_verified_at is None
    assert user.email_revision == 1 and user.credentials_revision == 1

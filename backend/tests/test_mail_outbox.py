"""E-001/F-004/T-002: durable mail outbox and worker on real PostgreSQL."""

import asyncio
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import MailOutbox
from app.services import mail_outbox
from app.services.action_tokens import (
    RESET_PASSWORD,
    consume_action_token,
    issue_action_token,
)
from app.services.mail_outbox import compose_mail, deliver_due_mail, enqueue_mail
from app.services.mail_transport import SendResult
from tests.pg_factories import create_user

pytestmark = pytest.mark.pg

SECRET_LINK = "https://app.example/account/reset-password#token=SECRET-LINK"


class FakeTransport:
    def __init__(self, *results: SendResult, delay: float = 0.0):
        self.results = list(results)
        self.sent: list[tuple[str, str]] = []
        self.delay = delay

    async def send(self, mail, idempotency_key):
        self.sent.append((mail.to, idempotency_key))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.results:
            return self.results.pop(0)
        return SendResult("accepted", provider_message_id=f"msg-{idempotency_key}")


@pytest.fixture
def outbox_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mail_outbox_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "mail_from", "Vocabulario <auth@app.example>")
    monkeypatch.setattr(settings, "mail_reply_to", "help@app.example")


def _mail(to="someone@test.com"):
    return compose_mail(
        to=to,
        subject="Reset",
        text=f"Open {SECRET_LINK}",
        html=f'<a href="{SECRET_LINK}">Reset</a>',
        locale="pl",
        template="reset_password/v1",
    )


async def _queue_reset_mail(pg, *, now=None, ttl=timedelta(minutes=30)):
    now = now or now_utc()
    async with pg() as session:
        user = await create_user(session)
        issued = await issue_action_token(session, user, RESET_PASSWORD, now=now)
        row = await enqueue_mail(
            session,
            kind="reset_password",
            mail=_mail(user.email),
            expires_at=now + ttl,
            user_id=user.id,
            action_token_id=issued.row.id,
            now=now,
        )
        await session.commit()
        return row.id, user.id, issued.token


async def _queue_notice(pg, *, now=None, ttl=timedelta(hours=24)):
    now = now or now_utc()
    async with pg() as session:
        user = await create_user(session)
        row = await enqueue_mail(
            session,
            kind="password_changed",
            mail=_mail(user.email),
            expires_at=now + ttl,
            user_id=user.id,
            now=now,
        )
        await session.commit()
        return row.id


async def _row(pg, mail_id) -> MailOutbox:
    async with pg() as session:
        return await session.get(MailOutbox, mail_id)


def _clock(monkeypatch, at):
    monkeypatch.setattr(mail_outbox, "now_utc", lambda: at)


async def test_payload_is_encrypted_and_sent_once_with_stable_key(pg, outbox_key):
    mail_id, _, _ = await _queue_reset_mail(pg)
    stored = await _row(pg, mail_id)
    assert b"SECRET-LINK" not in stored.payload_ciphertext
    assert b"someone" not in stored.payload_ciphertext
    transport = FakeTransport()
    assert await deliver_due_mail(transport=transport) == 1
    assert await deliver_due_mail(transport=transport) == 0
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "accepted"
    assert row.provider_message_id == f"msg-auth-mail/{mail_id}"
    assert row.attempts == 1 and row.lease_until is None
    assert [key for _, key in transport.sent] == [f"auth-mail/{mail_id}"]


async def test_enqueue_is_part_of_the_callers_transaction(pg, outbox_key):
    async with pg() as session:
        user = await create_user(session)
        await session.commit()
        await enqueue_mail(
            session,
            kind="password_changed",
            mail=_mail(),
            expires_at=now_utc() + timedelta(hours=1),
            user_id=user.id,
        )
        await session.rollback()
    async with pg() as session:
        assert (await session.execute(select(MailOutbox))).first() is None


async def test_link_mail_requires_its_token(pg, outbox_key):
    async with pg() as session:
        with pytest.raises(ValueError):
            await enqueue_mail(
                session, kind="verify_email", mail=_mail(), expires_at=now_utc()
            )


async def test_retry_follows_schedule_and_retry_after_with_same_key(pg, outbox_key, monkeypatch):
    start = now_utc()
    mail_id = await _queue_notice(pg, now=start)
    transport = FakeTransport(
        SendResult("retry", error_code="resend_application_error"),
        SendResult("retry", error_code="resend_rate_limit_exceeded", retry_after_s=500),
    )
    _clock(monkeypatch, start)
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "queued"
    assert row.next_attempt_at == start + timedelta(seconds=30)
    assert row.last_error_code == "resend_application_error"

    _clock(monkeypatch, start + timedelta(seconds=29))
    assert await deliver_due_mail(transport=transport) == 0

    second = start + timedelta(seconds=30)
    _clock(monkeypatch, second)
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.next_attempt_at == second + timedelta(seconds=500)

    _clock(monkeypatch, row.next_attempt_at)
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "accepted" and row.attempts == 3
    assert {key for _, key in transport.sent} == {f"auth-mail/{mail_id}"}


async def test_six_attempts_then_failed(pg, outbox_key, monkeypatch):
    start = now_utc()
    mail_id = await _queue_notice(pg, now=start)
    transport = FakeTransport(*[SendResult("retry", error_code="resend_timeout")] * 10)
    for offset in (0, 30, 120, 300, 600, 1200, 5000):
        _clock(monkeypatch, start + timedelta(seconds=offset))
        await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert len(transport.sent) == 6
    assert row.dispatch_state == "failed" and row.attempts == 6
    assert row.last_error_code == "resend_timeout"


async def test_permanent_error_is_not_retried(pg, outbox_key):
    mail_id = await _queue_notice(pg)
    transport = FakeTransport(SendResult("permanent", error_code="resend_validation_error"))
    await deliver_due_mail(transport=transport)
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "failed" and len(transport.sent) == 1


async def test_link_is_never_sent_after_it_expires(pg, outbox_key, monkeypatch):
    start = now_utc()
    mail_id, _, _ = await _queue_reset_mail(pg, now=start)
    transport = FakeTransport(SendResult("retry", error_code="resend_application_error"))
    _clock(monkeypatch, start)
    await deliver_due_mail(transport=transport)
    _clock(monkeypatch, start + timedelta(minutes=30))
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "cancelled" and row.last_error_code == "expired"
    assert len(transport.sent) == 1


async def test_retry_that_would_land_after_expiry_fails_now(pg, outbox_key, monkeypatch):
    start = now_utc()
    mail_id = await _queue_notice(pg, now=start, ttl=timedelta(seconds=20))
    _clock(monkeypatch, start)
    await deliver_due_mail(transport=FakeTransport(SendResult("retry", error_code="x")))
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "failed" and row.last_error_code == "expired_before_retry"


async def test_exhausted_budget_returns_mail_unspent_or_drops_it_at_expiry(pg, outbox_key):
    from app.services.auth_limits import MAIL_BUDGET_ALL
    from tests.test_auth_limits import _fill

    keep_id, _, _ = await _queue_reset_mail(pg, ttl=timedelta(days=3))
    drop_id, _, _ = await _queue_reset_mail(pg, ttl=timedelta(seconds=30))
    await _fill(MAIL_BUDGET_ALL[0], now_utc())
    transport = FakeTransport()
    await deliver_due_mail(transport=transport)
    assert transport.sent == []
    kept, dropped = await _row(pg, keep_id), await _row(pg, drop_id)
    assert kept.dispatch_state == "queued" and kept.attempts == 0
    assert kept.next_attempt_at > now_utc() + timedelta(hours=1)
    assert dropped.dispatch_state == "cancelled" and dropped.last_error_code == "budget_exhausted"


async def test_used_link_is_cancelled_before_sending(pg, outbox_key):
    mail_id, user_id, token = await _queue_reset_mail(pg)
    async with pg() as session:
        from app.services.auth_sessions import lock_user

        user = await lock_user(session, user_id)
        await consume_action_token(session, user, token, RESET_PASSWORD)
        await session.commit()
    transport = FakeTransport()
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "cancelled" and row.last_error_code == "stale_link"
    assert transport.sent == [] and row.attempts == 0


async def test_unreadable_payload_fails_without_sending(pg, outbox_key, monkeypatch):
    mail_id = await _queue_notice(pg)
    monkeypatch.setattr(get_settings(), "mail_outbox_key", Fernet.generate_key().decode())
    transport = FakeTransport()
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "failed" and row.last_error_code == "payload_key_unavailable"
    assert transport.sent == []


async def test_two_workers_never_send_the_same_mail_twice(pg, outbox_key):
    ids = {await _queue_notice(pg) for _ in range(4)}
    transport = FakeTransport(delay=0.05)
    await asyncio.gather(
        deliver_due_mail(transport=transport), deliver_due_mail(transport=transport)
    )
    keys = [key for _, key in transport.sent]
    assert sorted(keys) == sorted(f"auth-mail/{mail_id}" for mail_id in ids)
    for mail_id in ids:
        assert (await _row(pg, mail_id)).dispatch_state == "accepted"


async def test_expired_lease_is_reclaimed_with_the_same_key(pg, outbox_key, monkeypatch):
    start = now_utc()
    mail_id = await _queue_notice(pg, now=start)
    _clock(monkeypatch, start)
    claim, found = await mail_outbox._claim_one(start)
    assert found and claim is not None
    # Worker died after the claim: nothing else may take it while the lease holds.
    transport = FakeTransport()
    assert await deliver_due_mail(transport=transport) == 0
    _clock(monkeypatch, start + timedelta(seconds=61))
    await deliver_due_mail(transport=transport)
    row = await _row(pg, mail_id)
    assert row.dispatch_state == "accepted" and row.attempts == 2
    assert [key for _, key in transport.sent] == [f"auth-mail/{mail_id}"]
    # The dead worker's late result must not overwrite the new outcome.
    await mail_outbox._finish(claim, SendResult("permanent", error_code="late"), start)
    assert (await _row(pg, mail_id)).dispatch_state == "accepted"

"""E-001/F-008/T-003: dziennik konta zapisywany razem z transakcją i linią logu po commicie."""

import logging
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import AccountDeletion, AccountJournal
from app.services import account_journal as journal
from app.services.account_deletion import subject_hmac
from tests.pg_factories import create_user
from tests.test_account_deletion import _ask, _cancel, _verified

pytestmark = pytest.mark.pg


@pytest.fixture(autouse=True)
def _erasure_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "account_deletion_enabled", True)
    monkeypatch.setattr(settings, "account_erasure_key", "k" * 48)
    monkeypatch.setattr(settings, "account_erasure_key_version", 1)


@pytest.fixture
def lines():
    captured: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            captured.append(record.getMessage())

    handler = Capture()
    logger = logging.getLogger("vocabulario.account_journal")
    logger.addHandler(handler)
    yield captured
    logger.removeHandler(handler)


async def _rows(pg) -> list[AccountJournal]:
    async with pg() as db:
        return list((await db.execute(select(AccountJournal))).scalars())


async def test_commit_writes_row_and_exactly_one_line_without_identifiers(pg, lines):
    async with pg() as db:
        user = await create_user(db, email="private-address@test.com")
        event = journal.record(db, "password_change", user=user)
        assert lines == []
        await db.commit()
    [row] = await _rows(pg)
    assert row.id == event.id and row.subject_hmac == subject_hmac(user.id)[0]
    assert len(lines) == 1
    assert "private-address" not in lines[0] and str(user.id) not in lines[0]
    parsed = journal.parse_line("2026-01-01T00:00:00Z app " + lines[0])
    assert parsed == event


async def test_rollback_and_savepoint_rollback_leave_neither_row_nor_line(pg, lines):
    async with pg() as db:
        user = await create_user(db)
        journal.record(db, "password_reset", user=user)
        await db.rollback()
    assert await _rows(pg) == [] and lines == []

    async with pg() as db:
        user = await create_user(db)
        kept = journal.record(db, "email_changed", user=user)
        savepoint = await db.begin_nested()
        journal.record(db, "google_linked", user=user)
        await savepoint.rollback()
        await db.commit()
    assert [r.id for r in await _rows(pg)] == [kept.id]
    assert len(lines) == 1 and str(kept.id) in lines[0]


async def test_no_erasure_key_means_no_event(pg, lines, monkeypatch):
    monkeypatch.setattr(get_settings(), "account_erasure_key", "")
    async with pg() as db:
        user = await create_user(db)
        assert journal.record(db, "password_change", user=user) is None
        await db.commit()
    assert await _rows(pg) == [] and lines == []


async def test_retention_keeps_events_of_a_running_deletion(pg):
    now = now_utc()
    old = now - timedelta(days=60)
    process = uuid4()
    async with pg() as db:
        db.add(
            AccountDeletion(
                id=process,
                subject_hmac="a" * 64,
                subject_key_version=1,
                state="purging",
                requested_at=old,
                cancel_until=old,
                purge_due_at=now + timedelta(days=1),
                status_secret_hash="b" * 64,
                request_fingerprint="c" * 64,
            )
        )
        db.add_all(
            [
                AccountJournal(
                    event_type="deletion_requested",
                    subject_hmac="a" * 64,
                    subject_key_version=1,
                    occurred_at=old,
                    process_id=process,
                ),
                AccountJournal(
                    event_type="password_change",
                    subject_hmac="d" * 64,
                    subject_key_version=1,
                    occurred_at=old,
                ),
                AccountJournal(
                    event_type="password_change",
                    subject_hmac="d" * 64,
                    subject_key_version=1,
                    occurred_at=now,
                ),
            ]
        )
        await db.commit()
        assert await journal.purge_old(db, now) == 1
        await db.commit()
    kept = await _rows(pg)
    assert sorted(r.event_type for r in kept) == ["deletion_requested", "password_change"]


async def test_deletion_request_and_cancel_are_journaled(pg, pg_client, lines):
    email, _ = await _verified(pg, pg_client)
    response, rid, _secret = await _ask(pg_client, email)
    assert response.status_code == 202
    cancelled = await _cancel(pg_client, email, rid)
    assert cancelled.status_code == 200, cancelled.text

    types = [r.event_type for r in sorted(await _rows(pg), key=lambda r: r.occurred_at)]
    assert types == ["deletion_requested", "deletion_cancelled"]
    parsed = [journal.parse_line(line) for line in lines]
    assert [e.type for e in parsed] == types
    assert all(e.process_id == rid for e in parsed)
    assert parsed[1].lifecycle_revision == parsed[0].lifecycle_revision + 1
    assert email not in "".join(lines)

"""E-001/F-008/T-003: odtworzenie po przywróceniu bazy bez wskrzeszania usuniętych kont."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import AccountDeletion, AccountJournal, AuthSession, User
from app.services import account_journal as journal
from app.services.account_deletion import subject_hmac
from app.services.restore_recovery import recover
from tests.test_account_recovery import (
    NEW_PASSWORD,
    PASSWORD,
    _bearer,
    _code,
    _confirm,
    _login,
    _outbox,
    _register,
    _request_reset,
    _token_from,
    _user,
)

pytestmark = pytest.mark.pg


@pytest.fixture(autouse=True)
def _erasure_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "account_erasure_key", "k" * 48)
    monkeypatch.setattr(settings, "account_erasure_key_version", 1)


def _event(user: User, event_type: str, *, minutes: int = 0, **extra) -> journal.JournalEvent:
    return journal.JournalEvent(
        id=uuid4(),
        type=event_type,
        subject=subject_hmac(user.id)[0],
        key_version=1,
        occurred_at=now_utc() + timedelta(minutes=minutes),
        **extra,
    )


async def _run(pg, events, *, apply=True):
    lines = None if events is None else [e.to_line() for e in events]
    async with pg() as db:
        return await recover(db, lines, apply=apply)


async def _epoch(pg) -> str | None:
    async with pg() as db:
        return (await db.execute(text("SELECT epoch::text FROM sync_epoch WHERE id = 1"))).scalar()


async def test_every_session_ends_and_devices_get_a_new_epoch(pg, pg_client):
    email = f"restore-{uuid4()}@test.com"
    tokens = await _register(pg_client, email)
    before = await _epoch(pg)

    report = await _run(pg, [])
    assert report.sessions_revoked >= 1 and report.applied

    me = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
    assert (me.status_code, _code(me)) == (401, "session_revoked")
    async with pg() as db:
        sessions = (await db.execute(select(AuthSession))).scalars().all()
    assert sessions and all(s.revocation_reason == "restore" for s in sessions)
    assert await _epoch(pg) != before


async def test_dry_run_changes_nothing(pg, pg_client):
    email = f"dry-{uuid4()}@test.com"
    tokens = await _register(pg_client, email)
    user = await _user(pg, email)
    before = await _epoch(pg)

    report = await _run(pg, [_event(user, "deletion_requested", lifecycle_revision=1)], apply=False)
    assert not report.applied and report.deletions_restored == 1

    assert (await pg_client.get("/api/v1/me", headers=_bearer(tokens))).status_code == 200
    assert (await _user(pg, email)).account_status == "active"
    assert await _epoch(pg) == before
    async with pg() as db:
        assert (await db.execute(select(AccountDeletion))).first() is None
        assert (await db.execute(select(AccountJournal))).first() is None


async def test_lost_deletion_request_is_put_back_and_not_repeated(pg, pg_client):
    email = f"lost-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    process = uuid4()
    request = _event(
        user, "deletion_requested", process_id=process, lifecycle_revision=user.lifecycle_revision + 1
    )

    first = await _run(pg, [request])
    assert first.deletions_restored == 1 and first.events_already_in_database == 0
    restored = await _user(pg, email)
    assert restored.account_status == "deletion_pending"
    assert restored.lifecycle_revision == user.lifecycle_revision + 1
    async with pg() as db:
        deletion = (await db.execute(select(AccountDeletion))).scalar_one()
    assert deletion.id == process and deletion.state == "grace"
    assert deletion.cancel_until - deletion.requested_at == timedelta(hours=168)

    again = await _run(pg, [request])
    assert again.deletions_restored == 0 and again.events_already_in_database == 1


async def test_lost_cancel_after_lost_request_ends_active(pg, pg_client):
    email = f"cancel-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    process, revision = uuid4(), user.lifecycle_revision
    events = [
        _event(user, "deletion_requested", process_id=process, lifecycle_revision=revision + 1),
        _event(
            user, "deletion_cancelled", minutes=5, process_id=process, lifecycle_revision=revision + 2
        ),
    ]
    report = await _run(pg, events)
    assert (report.deletions_restored, report.cancels_applied) == (1, 1)
    after = await _user(pg, email)
    assert after.account_status == "active" and after.lifecycle_revision == revision + 2
    assert not after.restore_recovery_required


async def test_cancel_that_does_not_line_up_needs_a_person(pg, pg_client):
    email = f"mismatch-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    report = await _run(
        pg, [_event(user, "deletion_cancelled", process_id=uuid4(), lifecycle_revision=9)]
    )
    assert report.cancels_applied == 0
    assert (await _user(pg, email)).restore_recovery_required


async def test_lost_purge_is_restarted_instead_of_resurrecting_the_account(pg, pg_client):
    email = f"purge-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    done = _event(
        user,
        "purge_completed",
        process_id=uuid4(),
        lifecycle_revision=user.lifecycle_revision + 2,
        due_at=now_utc(),
    )
    report = await _run(pg, [done])
    assert report.purges_restored == 1
    assert (await _user(pg, email)).account_status == "deleting"
    async with pg() as db:
        deletion = (await db.execute(select(AccountDeletion))).scalar_one()
    assert deletion.state == "purging" and deletion.stage == "llm"
    assert (await _login(pg_client, email, PASSWORD)).status_code == 403


async def test_only_lost_credential_changes_flag_an_account(pg, pg_client):
    changed, untouched = f"a-{uuid4()}@test.com", f"b-{uuid4()}@test.com"
    await _register(pg_client, changed)
    await _register(pg_client, untouched)
    lost, kept = await _user(pg, changed), await _user(pg, untouched)
    events = [
        _event(lost, "password_change", credentials_revision=lost.credentials_revision + 1),
        _event(kept, "password_change", credentials_revision=kept.credentials_revision),
    ]
    report = await _run(pg, events)
    assert report.accounts_flagged == 1
    assert (await _user(pg, changed)).restore_recovery_required
    assert not (await _user(pg, untouched)).restore_recovery_required


async def test_flagged_login_needs_the_right_password_then_reset_opens_it(pg, pg_client):
    email = f"flag-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    await _run(pg, [_event(user, "email_changed", email_revision=user.email_revision + 1)])

    wrong = await _login(pg_client, email, "totally wrong password")
    assert (wrong.status_code, _code(wrong)) == (401, "invalid_credentials")
    blocked = await _login(pg_client, email, PASSWORD)
    assert (blocked.status_code, _code(blocked)) == (403, "restore_recovery_required")

    await _request_reset(pg_client, email)
    [row] = await _outbox(pg, "reset_password")
    assert (await _confirm(pg_client, _token_from(row))).status_code == 200
    assert not (await _user(pg, email)).restore_recovery_required
    assert (await _login(pg_client, email, NEW_PASSWORD)).status_code == 200


async def test_lost_journal_flags_everyone_and_reports_only_counts(pg, pg_client):
    for _ in range(2):
        await _register(pg_client, f"nolog-{uuid4()}@test.com")
    report = await _run(pg, None)
    assert report.accounts_flagged == 2
    assert "journal_lost_all_accounts_flagged" in report.notes
    async with pg() as db:
        assert all(
            u.restore_recovery_required for u in (await db.execute(select(User))).scalars()
        )


async def test_events_with_another_key_version_are_counted_not_applied(pg, pg_client):
    email = f"kv-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    foreign = _event(user, "password_change", credentials_revision=99)
    object.__setattr__(foreign, "key_version", 2)
    report = await _run(pg, [foreign])
    assert report.events_unmatched == 1
    assert not (await _user(pg, email)).restore_recovery_required

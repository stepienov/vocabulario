"""Database-restore recovery (E-001/F-008/T-003).

After a point-in-time restore the database can be behind what users did. This closes the gap
without resurrecting anything: every session and proof ends, the sync epoch rotates (devices
resync), deletions that were running are put back, and accounts whose credentials may have
changed after the restore point must prove themselves again. The events come from the
structured log lines written after each commit (`account_journal`); rows already present in
`account_journal` were kept by the restore and are skipped.

    python -m app.services.restore_recovery --log lines.txt            # dry run (default)
    python -m app.services.restore_recovery --log lines.txt --apply
    python -m app.services.restore_recovery --no-journal --apply        # log lines are lost

Only counts are printed: never an address, token or account identifier.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    AccountActionToken,
    AccountDeletion,
    AccountJournal,
    AuthRefreshRetry,
    AuthSession,
    GoogleChallenge,
    RecentAuthProof,
    User,
)
from app.services.account_deletion import CANCEL_WINDOW, PURGE_DEADLINE, subject_hmac
from app.services.account_journal import CREDENTIAL_EVENTS, JournalEvent, parse_line


@dataclass
class RestoreReport:
    applied: bool = False
    sessions_revoked: int = 0
    proofs_invalidated: int = 0
    events_read: int = 0
    events_already_in_database: int = 0
    events_unmatched: int = 0
    deletions_restored: int = 0
    purges_restored: int = 0
    cancels_applied: int = 0
    accounts_flagged: int = 0
    notes: list[str] = field(default_factory=list)


def read_events(lines: list[str]) -> list[JournalEvent]:
    events = [e for e in (parse_line(line) for line in lines) if e is not None]
    unique = {e.id: e for e in events}
    return sorted(unique.values(), key=lambda e: e.occurred_at)


async def _end_sessions_and_proofs(db: AsyncSession, now: datetime, report: RestoreReport) -> None:
    revoked = await db.execute(
        update(AuthSession)
        .where(AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revocation_reason="restore")
    )
    report.sessions_revoked = revoked.rowcount or 0
    await db.execute(delete(AuthRefreshRetry))
    invalidated = await db.execute(
        update(AccountActionToken)
        .where(AccountActionToken.consumed_at.is_(None), AccountActionToken.invalidated_at.is_(None))
        .values(invalidated_at=now)
    )
    proofs = await db.execute(
        update(RecentAuthProof).where(RecentAuthProof.consumed_at.is_(None)).values(consumed_at=now)
    )
    challenges = await db.execute(
        update(GoogleChallenge).where(GoogleChallenge.consumed_at.is_(None)).values(consumed_at=now)
    )
    report.proofs_invalidated = sum((r.rowcount or 0) for r in (invalidated, proofs, challenges))
    # Devices keep nothing stale: a new epoch makes every client pull from scratch.
    await db.execute(
        text(
            "INSERT INTO sync_epoch (id, epoch) VALUES (1, gen_random_uuid()) "
            "ON CONFLICT (id) DO UPDATE SET epoch = gen_random_uuid()"
        )
    )


def _new_deletion(user: User, event: JournalEvent, state: str) -> AccountDeletion:
    # The status secret of the lost request is unknown, so no caller can match these hashes.
    unusable = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    return AccountDeletion(
        id=event.process_id or uuid.uuid4(),
        user_id=user.id,
        subject_hmac=event.subject,
        subject_key_version=event.key_version,
        state=state,
        requested_at=event.occurred_at,
        cancel_until=event.occurred_at + CANCEL_WINDOW,
        purge_due_at=event.due_at or event.occurred_at + PURGE_DEADLINE,
        status_secret_hash=unusable,
        request_fingerprint=unusable,
        stage="grace" if state == "grace" else "llm",
        attempts=0,
    )


async def _apply_event(
    db: AsyncSession,
    event: JournalEvent,
    user: User,
    now: datetime,
    report: RestoreReport,
) -> None:
    deletion = (
        None
        if event.process_id is None
        else (
            await db.execute(
                select(AccountDeletion)
                .where(AccountDeletion.id == event.process_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
    )
    if event.type == "deletion_requested":
        if deletion is None and user.account_status == "active":
            db.add(_new_deletion(user, event, "grace"))
            user.account_status = "deletion_pending"
            user.lifecycle_revision = max(user.lifecycle_revision, event.lifecycle_revision or 0)
            report.deletions_restored += 1
    elif event.type in ("purge_required", "purge_completed"):
        # A purge that finished after the restore point left the restored account behind: do it again.
        if deletion is None:
            deletion = _new_deletion(user, event, "purging")
            db.add(deletion)
            report.purges_restored += 1
        elif deletion.state in ("grace", "cancelled"):
            deletion.state = "purging"
            deletion.stage = "llm"
            deletion.cancelled_at = None
            report.purges_restored += 1
        else:
            return
        deletion.purge_started_at = deletion.purge_started_at or now
        deletion.next_attempt_at = now
        user.account_status = "deleting"
        user.lifecycle_revision = max(user.lifecycle_revision, (event.lifecycle_revision or 0))
    elif event.type == "deletion_cancelled":
        expected = (event.lifecycle_revision or 0) - 1
        if deletion is not None and deletion.state == "grace" and user.lifecycle_revision == expected:
            deletion.state = "cancelled"
            deletion.stage = "cancelled"
            deletion.cancelled_at = event.occurred_at
            deletion.next_attempt_at = None
            user.account_status = "active"
            user.lifecycle_revision = event.lifecycle_revision or user.lifecycle_revision + 1
            report.cancels_applied += 1
        else:
            # The state in the database does not line up with this cancel: a person decides.
            user.restore_recovery_required = True
            report.notes.append("cancel_needs_manual_review")
    elif event.type in CREDENTIAL_EVENTS:
        lost = (event.credentials_revision or 0) > user.credentials_revision or (
            event.email_revision or 0
        ) > user.email_revision
        if lost:
            user.restore_recovery_required = True


async def recover(
    db: AsyncSession,
    lines: list[str] | None,
    *,
    apply: bool,
    now: datetime | None = None,
) -> RestoreReport:
    """Run recovery in the caller's transaction. `lines=None` means the log lines are lost."""
    clock = now or datetime.now(UTC)
    report = RestoreReport(applied=apply)
    await _end_sessions_and_proofs(db, clock, report)

    if lines is None:
        # Without the log nobody can tell whose credentials changed: everyone proves again.
        flagged = await db.execute(
            update(User)
            .where(User.restore_recovery_required.is_(False))
            .values(restore_recovery_required=True)
        )
        report.accounts_flagged = flagged.rowcount or 0
        report.notes.append("journal_lost_all_accounts_flagged")
    else:
        events = read_events(lines)
        report.events_read = len(events)
        known = set(
            (await db.execute(select(AccountJournal.id).where(AccountJournal.id.in_([e.id for e in events]))))
            .scalars()
            .all()
        ) if events else set()
        report.events_already_in_database = len(known)
        pending = [e for e in events if e.id not in known]
        if pending:
            settings = get_settings()
            by_subject: dict[str, User] = {}
            for user in (await db.execute(select(User))).scalars():
                by_subject[subject_hmac(user.id)[0]] = user
            for event in pending:
                user = by_subject.get(event.subject)
                if event.key_version != settings.account_erasure_key_version:
                    report.events_unmatched += 1
                elif user is None:
                    # No such account in the restored data (never existed or already gone).
                    continue
                else:
                    await _apply_event(db, event, user, clock, report)
                    # Kept in the journal so a second run does not apply the same event again.
                    db.add(
                        AccountJournal(
                            id=event.id,
                            process_id=event.process_id,
                            event_type=event.type,
                            subject_hmac=event.subject,
                            subject_key_version=event.key_version,
                            lifecycle_revision=event.lifecycle_revision,
                            credentials_revision=event.credentials_revision,
                            email_revision=event.email_revision,
                            occurred_at=event.occurred_at,
                            due_at=event.due_at,
                        )
                    )
        report.accounts_flagged = len(
            (
                await db.execute(select(User.id).where(User.restore_recovery_required.is_(True)))
            ).scalars().all()
        )

    if apply:
        await db.commit()
    else:
        await db.rollback()
    return report


def _format(report: RestoreReport) -> str:
    rows = [f"{k}={v}" for k, v in report.__dict__.items() if k != "notes"]
    rows.append("notes=" + ",".join(sorted(set(report.notes))))
    return "\n".join(rows)


async def _main(args: argparse.Namespace) -> int:
    from app.db import session as db_session

    if not args.no_journal and not args.log:
        print("give --log FILE or --no-journal")
        return 2
    lines = None
    if not args.no_journal:
        with open(args.log, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    async with db_session.async_session_factory() as db:
        report = await recover(db, lines, apply=args.apply)
    print(_format(report))
    print("APPLIED" if args.apply else "DRY RUN: nothing was changed (add --apply)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", help="file with the exported log lines")
    parser.add_argument("--no-journal", action="store_true", help="the log lines are lost")
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    raise SystemExit(asyncio.run(_main(parser.parse_args())))

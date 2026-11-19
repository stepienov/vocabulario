"""Account lifecycle/security journal (E-001/F-008/T-003).

Each event is written to `account_journal` in the SAME transaction as the change it describes
and, only after that transaction commits, to a structured log line. The log lives outside the
database, so a database restore can be reconciled against it (`restore_recovery`). A rolled-back
change leaves neither a row nor a line. Lines carry the keyed subject pseudonym, revisions and
times only: never an e-mail, token, Google subject, password hash or content.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AccountDeletion, AccountJournal, User

EVENT_TYPES = (
    "deletion_requested",
    "deletion_cancelled",
    "purge_required",
    "purge_completed",
    "password_reset",
    "password_change",
    "password_added",
    "google_linked",
    "email_changed",
)
# Events that make an older database copy unsafe to log into again without a new proof.
CREDENTIAL_EVENTS = frozenset(
    {"password_reset", "password_change", "password_added", "google_linked", "email_changed"}
)
LOG_PREFIX = "account_journal "
RETENTION = timedelta(days=45)

# Own handler: the app configures no root logging, and these lines must reach stdout.
_logger = logging.getLogger("vocabulario.account_journal")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

_PENDING = "account_journal_pending"


@dataclass(frozen=True)
class JournalEvent:
    id: uuid.UUID
    type: str
    subject: str
    key_version: int
    occurred_at: datetime
    process_id: uuid.UUID | None = None
    lifecycle_revision: int | None = None
    credentials_revision: int | None = None
    email_revision: int | None = None
    due_at: datetime | None = None

    def to_line(self) -> str:
        body = {
            "id": str(self.id),
            "type": self.type,
            "subject": self.subject,
            "kv": self.key_version,
            "at": self.occurred_at.astimezone(UTC).isoformat(),
            "process": str(self.process_id) if self.process_id else None,
            "lrev": self.lifecycle_revision,
            "crev": self.credentials_revision,
            "erev": self.email_revision,
            "due": self.due_at.astimezone(UTC).isoformat() if self.due_at else None,
        }
        return LOG_PREFIX + json.dumps(body, separators=(",", ":"))


def parse_line(line: str) -> JournalEvent | None:
    """Read one log line back; anything that is not a journal line yields None."""
    start = line.find(LOG_PREFIX)
    if start < 0:
        return None
    try:
        body = json.loads(line[start + len(LOG_PREFIX) :].strip())
        if body["type"] not in EVENT_TYPES:
            return None
        return JournalEvent(
            id=uuid.UUID(body["id"]),
            type=body["type"],
            subject=str(body["subject"]),
            key_version=int(body["kv"]),
            occurred_at=datetime.fromisoformat(body["at"]),
            process_id=uuid.UUID(body["process"]) if body.get("process") else None,
            lifecycle_revision=body.get("lrev"),
            credentials_revision=body.get("crev"),
            email_revision=body.get("erev"),
            due_at=datetime.fromisoformat(body["due"]) if body.get("due") else None,
        )
    except (KeyError, ValueError, TypeError):
        return None


def _subject(user: User | None, deletion: AccountDeletion | None) -> tuple[str, int] | None:
    if deletion is not None:
        return deletion.subject_hmac, deletion.subject_key_version
    if user is None or not get_settings().erasure_key_ready():
        return None
    from app.services.account_deletion import subject_hmac

    return subject_hmac(user.id)


def record(
    db: AsyncSession,
    event_type: str,
    *,
    user: User | None = None,
    deletion: AccountDeletion | None = None,
    now: datetime | None = None,
) -> JournalEvent | None:
    """Add the row to the caller's transaction and queue the log line for its commit.

    Without the erasure key (local development) there is no pseudonym and nothing is recorded.
    """
    assert event_type in EVENT_TYPES, event_type
    subject = _subject(user, deletion)
    if subject is None:
        return None
    entry = JournalEvent(
        id=uuid.uuid4(),
        type=event_type,
        subject=subject[0],
        key_version=subject[1],
        occurred_at=now or datetime.now(UTC),
        process_id=deletion.id if deletion is not None else None,
        lifecycle_revision=user.lifecycle_revision if user is not None else None,
        credentials_revision=user.credentials_revision if user is not None else None,
        email_revision=user.email_revision if user is not None else None,
        due_at=deletion.purge_due_at if deletion is not None else None,
    )
    db.add(
        AccountJournal(
            id=entry.id,
            process_id=entry.process_id,
            event_type=entry.type,
            subject_hmac=entry.subject,
            subject_key_version=entry.key_version,
            lifecycle_revision=entry.lifecycle_revision,
            credentials_revision=entry.credentials_revision,
            email_revision=entry.email_revision,
            occurred_at=entry.occurred_at,
            due_at=entry.due_at,
        )
    )
    sync = db.sync_session
    sync.info.setdefault(_PENDING, []).append(
        (entry, sync.get_nested_transaction() or sync.get_transaction())
    )
    return entry


@event.listens_for(Session, "after_commit")
def _emit_after_commit(session: Session) -> None:
    for entry, _tx in session.info.pop(_PENDING, []):
        _logger.info(entry.to_line())


@event.listens_for(Session, "after_soft_rollback")
def _drop_after_rollback(session: Session, previous_transaction) -> None:
    pending = session.info.get(_PENDING)
    if not pending:
        return
    if previous_transaction.nested:
        # A rolled-back savepoint only takes its own events with it.
        session.info[_PENDING] = [item for item in pending if item[1] is not previous_transaction]
    else:
        session.info.pop(_PENDING, None)


async def purge_old(db: AsyncSession, now: datetime | None = None) -> int:
    """Drop events past retention, keeping those of a deletion that is still running."""
    cutoff = (now or datetime.now(UTC)) - RETENTION
    active = select(AccountDeletion.id).where(AccountDeletion.state.in_(("grace", "purging")))
    result = await db.execute(
        delete(AccountJournal).where(
            AccountJournal.occurred_at < cutoff,
            (AccountJournal.process_id.is_(None)) | (AccountJournal.process_id.not_in(active)),
        )
    )
    return result.rowcount or 0

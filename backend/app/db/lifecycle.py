"""Write barrier for accounts that are being deleted (E-001/F-006/T-002).

Every flush that adds or changes owner data first checks the owner under a shared row lock
(`FOR SHARE` conflicts with the `FOR NO KEY UPDATE` of acceptance/cancel/purge), once per
transaction and owner. A background operation may also pin the `lifecycle_revision` it
started with; a cancelled-and-reactivated account then rejects its stale results too.
Bulk statements and deletes are not guarded: the purge worker itself uses them.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

from app.models import (
    AdminCardReview,
    AdminEscalation,
    AppLog,
    AppliedSyncMove,
    CardCorrection,
    CardHistoryEvent,
    ImportJob,
    LanguageProfile,
    LearningCard,
    LlmUsage,
    LookupEvent,
    LookupMoreOperation,
    ReviewLog,
    User,
    WordList,
)

OWNER_MODELS = (
    AdminCardReview,
    AdminEscalation,
    AppLog,
    AppliedSyncMove,
    CardCorrection,
    CardHistoryEvent,
    ImportJob,
    LanguageProfile,
    LearningCard,
    LlmUsage,
    LookupEvent,
    LookupMoreOperation,
    ReviewLog,
    WordList,
)
_CHECKED = "lifecycle_checked"
_PINNED: ContextVar[dict[UUID, int] | None] = ContextVar("lifecycle_pinned", default=None)


class LifecycleBlocked(Exception):
    """The owner is no longer active (or changed lifecycle); nothing may be written."""


def pin_revision(user_id: UUID, revision: int) -> None:
    """Remember the revision this task works under; later flushes must still match it."""
    pinned = dict(_PINNED.get() or {})
    pinned[user_id] = revision
    _PINNED.set(pinned)


async def pin_lifecycle(db: AsyncSession, user_id: UUID) -> None:
    """Read the owner's current lifecycle without locking it and pin it for this task."""
    row = (
        await db.execute(
            select(User.account_status, User.lifecycle_revision).where(User.id == user_id)
        )
    ).one_or_none()
    if row is None or row.account_status != "active":
        raise LifecycleBlocked()
    pin_revision(user_id, row.lifecycle_revision)


_LOOSE_MODELS = (AppLog, LlmUsage, LookupEvent)  # no FK to users: a missing user is an orphan


def _owners(session: Session) -> tuple[set[UUID], set[UUID]]:
    """Owners of changed rows; the second set holds those written without an FK."""
    owners: set[UUID] = set()
    loose: set[UUID] = set()
    for obj in (*session.new, *session.dirty):
        if isinstance(obj, OWNER_MODELS):
            owner = getattr(obj, "user_id", None)
            if owner is not None:
                owners.add(owner)
                if isinstance(obj, _LOOSE_MODELS):
                    loose.add(owner)
    return owners, loose


@event.listens_for(Session, "before_flush")
def _guard_owner_writes(session: Session, flush_context, instances) -> None:
    owners, loose = _owners(session)
    if not owners:
        return
    checked: set[UUID] = session.info.setdefault(_CHECKED, set())
    todo = owners - checked
    if not todo:
        return
    rows = session.execute(
        select(User.id, User.account_status, User.lifecycle_revision)
        .where(User.id.in_(todo))
        .with_for_update(read=True)
    ).all()
    found = {row.id: row for row in rows}
    pinned = _PINNED.get() or {}
    for owner in todo:
        row = found.get(owner)
        if row is None:
            # A user inserted by this very flush has no row yet; the FK guards real orphans.
            if owner in loose:
                raise LifecycleBlocked()
            continue
        if row.account_status != "active":
            raise LifecycleBlocked()
        if owner in pinned and pinned[owner] != row.lifecycle_revision:
            raise LifecycleBlocked()
    checked.update(todo)


@event.listens_for(Session, "after_transaction_end")
def _forget_checks(session: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is None:
        session.info.pop(_CHECKED, None)

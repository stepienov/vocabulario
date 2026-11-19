"""Irreversible part of account deletion (E-001/F-006/T-002).

After the cancel window a process moves grace -> purging under the user lock, then this worker
deletes the owner's data in bounded batches, leaf data first, and finally the user row. A
lease with a token keeps one worker per process; failures back off and keep only an error code.
`completed` is written in the same commit that deletes the user, after the manifest counted zero.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.db import session as db_session
from app.models import (
    AccountDeletion,
    AppLog,
    ImportJob,
    LanguageProfile,
    LearningCard,
    LexicalEntry,
    LlmCallPayload,
    LlmUsage,
    LookupEvent,
    User,
    WordList,
)

logger = logging.getLogger(__name__)

BATCH = 1000
CYCLE_PROCESSES = 10
LEASE = timedelta(seconds=60)
CYCLE_INTERVAL_S = 15 * 60
BACKOFF = (timedelta(minutes=15), timedelta(minutes=30), timedelta(hours=1), timedelta(hours=6))
SECRET_RETENTION = timedelta(days=30)
STAGES = ("llm", "logs", "lookups", "cards", "imports", "attribution", "account")


def _profile_ids(user_id: uuid.UUID):
    return select(LanguageProfile.id).where(LanguageProfile.user_id == user_id)


def _card_ids(user_id: uuid.UUID):
    return select(LearningCard.id).where(LearningCard.user_id == user_id)


def _llm_filter(user_id: uuid.UUID):
    return or_(
        LlmUsage.user_id == user_id,
        LlmUsage.profile_id.in_(_profile_ids(user_id)),
        LlmUsage.card_id.in_(_card_ids(user_id)),
    )


def _log_filter(user_id: uuid.UUID):
    return or_(AppLog.user_id == user_id, AppLog.profile_id.in_(_profile_ids(user_id)))


def _lookup_filter(user_id: uuid.UUID):
    return or_(
        LookupEvent.user_id == user_id, LookupEvent.profile_id.in_(_profile_ids(user_id))
    )


async def _batch_delete(db: AsyncSession, model, id_column, where) -> int:
    ids = select(id_column).where(where).limit(BATCH)
    result = await db.execute(delete(model).where(id_column.in_(ids)))
    return result.rowcount or 0


async def _stage_batch(db: AsyncSession, stage: str, user_id: uuid.UUID) -> int:
    """One bounded step of a stage; 0 means the stage has nothing left."""
    if stage == "llm":
        usage_ids = select(LlmUsage.id).where(_llm_filter(user_id)).limit(BATCH)
        # Payload rows go first (they cascade anyway) so one transaction stays small.
        await db.execute(delete(LlmCallPayload).where(LlmCallPayload.llm_usage_id.in_(usage_ids)))
        return await _batch_delete(db, LlmUsage, LlmUsage.id, _llm_filter(user_id))
    if stage == "logs":
        return await _batch_delete(db, AppLog, AppLog.id, _log_filter(user_id))
    if stage == "lookups":
        return await _batch_delete(db, LookupEvent, LookupEvent.id, _lookup_filter(user_id))
    if stage == "cards":
        return await _batch_delete(
            db, LearningCard, LearningCard.id, LearningCard.user_id == user_id
        )
    if stage == "imports":
        jobs = await _batch_delete(db, ImportJob, ImportJob.id, ImportJob.user_id == user_id)
        lists = await _batch_delete(db, WordList, WordList.id, WordList.user_id == user_id)
        return jobs + lists
    if stage == "attribution":
        ids = (
            select(LexicalEntry.id)
            .where(LexicalEntry.created_by_user_id == user_id)
            .limit(BATCH)
        )
        result = await db.execute(
            update(LexicalEntry)
            .where(LexicalEntry.id.in_(ids))
            .values(created_by_user_id=None)
        )
        return result.rowcount or 0
    raise ValueError(f"unknown purge stage: {stage}")


async def remaining(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Manifest check: owner records still present outside the user row and its cascades."""
    probes = (
        select(func.count()).select_from(LlmUsage).where(_llm_filter(user_id)),
        select(func.count()).select_from(AppLog).where(_log_filter(user_id)),
        select(func.count()).select_from(LookupEvent).where(_lookup_filter(user_id)),
        select(func.count()).select_from(LearningCard).where(LearningCard.user_id == user_id),
        select(func.count()).select_from(ImportJob).where(ImportJob.user_id == user_id),
        select(func.count()).select_from(WordList).where(WordList.user_id == user_id),
        select(func.count())
        .select_from(LexicalEntry)
        .where(LexicalEntry.created_by_user_id == user_id),
    )
    total = 0
    for probe in probes:
        total += (await db.execute(probe)).scalar_one()
    return total


async def start_due_processes(now: datetime, *, limit: int = CYCLE_PROCESSES) -> int:
    """grace -> purging after the cancel window, under the same lock as cancel."""
    started = 0
    async with db_session.async_session_factory() as db:
        due = (
            await db.execute(
                select(AccountDeletion.id, AccountDeletion.user_id)
                .where(
                    AccountDeletion.state == "grace",
                    AccountDeletion.cancel_until <= now,
                    AccountDeletion.user_id.is_not(None),
                )
                .order_by(AccountDeletion.cancel_until)
                .limit(limit)
            )
        ).all()
        await db.rollback()
    for deletion_id, user_id in due:
        async with db_session.async_session_factory() as db:
            user = (
                await db.execute(
                    select(User)
                    .where(User.id == user_id)
                    .with_for_update(key_share=True)
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            deletion = (
                await db.execute(
                    select(AccountDeletion)
                    .where(AccountDeletion.id == deletion_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if (
                user is None
                or deletion is None
                or deletion.state != "grace"
                or deletion.cancel_until > now
            ):
                await db.rollback()
                continue
            user.account_status = "deleting"
            user.lifecycle_revision = user.lifecycle_revision + 1
            deletion.state = "purging"
            deletion.stage = STAGES[0]
            deletion.purge_started_at = now
            deletion.next_attempt_at = now
            await db.commit()
            started += 1
    return started


async def _claim(now: datetime, *, limit: int = CYCLE_PROCESSES) -> list[tuple[uuid.UUID, uuid.UUID]]:
    claimed: list[tuple[uuid.UUID, uuid.UUID]] = []
    async with db_session.async_session_factory() as db:
        rows = (
            await db.execute(
                select(AccountDeletion)
                .where(
                    AccountDeletion.state == "purging",
                    or_(AccountDeletion.next_attempt_at.is_(None), AccountDeletion.next_attempt_at <= now),
                    or_(AccountDeletion.lease_until.is_(None), AccountDeletion.lease_until < now),
                )
                .order_by(AccountDeletion.next_attempt_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for row in rows:
            token = uuid.uuid4()
            row.lease_token = token
            row.lease_until = now + LEASE
            claimed.append((row.id, token))
        await db.commit()
    return claimed


async def _step(deletion_id: uuid.UUID, token: uuid.UUID, now: datetime) -> bool:
    """One transaction of work. True while more remains for this process."""
    async with db_session.async_session_factory() as db:
        deletion = (
            await db.execute(
                select(AccountDeletion)
                .where(AccountDeletion.id == deletion_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if (
            deletion is None
            or deletion.state != "purging"
            or deletion.lease_token != token
            or deletion.user_id is None
        ):
            await db.rollback()
            return False
        deletion.lease_until = now + LEASE
        user_id = deletion.user_id
        if deletion.stage == "account":
            await db.execute(
                select(User.id).where(User.id == user_id).with_for_update()
            )
            if await remaining(db, user_id):
                deletion.stage = STAGES[0]
                await db.commit()
                return True
            deletion.state = "completed"
            deletion.stage = "completed"
            deletion.completed_at = now
            deletion.lease_until = None
            deletion.lease_token = None
            deletion.next_attempt_at = None
            deletion.last_error_code = None
            await db.flush()
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
            return False
        affected = await _stage_batch(db, deletion.stage, user_id)
        if affected == 0:
            deletion.stage = STAGES[STAGES.index(deletion.stage) + 1]
        await db.commit()
        return True


async def _fail(deletion_id: uuid.UUID, token: uuid.UUID, exc: Exception, now: datetime) -> None:
    async with db_session.async_session_factory() as db:
        deletion = (
            await db.execute(
                select(AccountDeletion)
                .where(AccountDeletion.id == deletion_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if deletion is not None and deletion.lease_token == token and deletion.state == "purging":
            deletion.attempts = deletion.attempts + 1
            deletion.last_error_code = type(exc).__name__[:48]
            deletion.next_attempt_at = now + BACKOFF[min(deletion.attempts - 1, len(BACKOFF) - 1)]
            deletion.lease_until = None
            deletion.lease_token = None
        await db.commit()


async def purge_process(deletion_id: uuid.UUID, token: uuid.UUID, now: datetime | None = None) -> None:
    try:
        while await _step(deletion_id, token, now or now_utc()):
            pass
    except Exception as exc:  # noqa: BLE001 - keep only the error class, never data
        logger.error("account purge failed (%s)", type(exc).__name__)
        await _fail(deletion_id, token, exc, now or now_utc())


async def expire_secrets(now: datetime) -> int:
    """Status receipts stop working 30 days after a terminal state."""
    async with db_session.async_session_factory() as db:
        ended = func.coalesce(AccountDeletion.completed_at, AccountDeletion.cancelled_at)
        result = await db.execute(
            update(AccountDeletion)
            .where(
                AccountDeletion.state.in_(("completed", "cancelled")),
                AccountDeletion.status_secret_hash != "",
                ended < now - SECRET_RETENTION,
            )
            .values(status_secret_hash="")
        )
        await db.commit()
        return result.rowcount or 0


async def run_purge_cycle(now: datetime | None = None) -> int:
    clock = now or now_utc()
    await start_due_processes(clock)
    claimed = await _claim(clock)
    for deletion_id, token in claimed:
        await purge_process(deletion_id, token, now)
    await expire_secrets(clock)
    return len(claimed)


async def run_purge_worker() -> None:
    while True:
        try:
            await run_purge_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("account purge cycle failed")
        await asyncio.sleep(CYCLE_INTERVAL_S)

"""Bounded retention of lookup history, unused cache and completed import inputs."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImportJob, ImportJobEvent, ImportJobItem, LookupEvent, LookupQueryCache

LOOKUP_RETENTION = timedelta(days=30)
IMPORT_RETENTION = timedelta(days=30)
CACHE_RETENTION = timedelta(days=90)
_TERMINAL_IMPORTS = ("done", "failed", "cancelled")
_SCRUBBED = "retention_scrubbed"


async def purge_expired(db: AsyncSession, now: datetime) -> dict[str, int]:
    lookup_ids = (
        await db.execute(
            select(LookupEvent.id)
            .where(LookupEvent.created_at < now - LOOKUP_RETENTION)
            .order_by(LookupEvent.created_at)
            .limit(1000)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    if lookup_ids:
        await db.execute(delete(LookupEvent).where(LookupEvent.id.in_(lookup_ids)))

    cache_ids = (
        await db.execute(
            select(LookupQueryCache.id)
            .where(LookupQueryCache.updated_at < now - CACHE_RETENTION)
            .order_by(LookupQueryCache.updated_at)
            .limit(1000)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    if cache_ids:
        await db.execute(delete(LookupQueryCache).where(LookupQueryCache.id.in_(cache_ids)))

    ended_at = func.coalesce(ImportJob.finished_at, ImportJob.updated_at, ImportJob.created_at)
    job_ids = (
        await db.execute(
            select(ImportJob.id)
            .where(
                ImportJob.status.in_(_TERMINAL_IMPORTS),
                ended_at < now - IMPORT_RETENTION,
                ~ImportJob.input_meta.has_key(_SCRUBBED),
            )
            .order_by(ended_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    if job_ids:
        await db.execute(
            update(ImportJob)
            .where(ImportJob.id.in_(job_ids))
            .values(
                source_name="",
                current_label=None,
                error_message=None,
                input_sha256=None,
                input_meta={_SCRUBBED: True},
            )
        )
        await db.execute(
            update(ImportJobItem)
            .where(ImportJobItem.job_id.in_(job_ids))
            .values(raw_note=[], input_label="", reason_detail=None, last_error=None)
        )
        await db.execute(
            update(ImportJobEvent)
            .where(ImportJobEvent.job_id.in_(job_ids))
            .values(payload=None)
        )

    return {"lookups": len(lookup_ids), "cache": len(cache_ids), "imports": len(job_ids)}

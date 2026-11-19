"""Technical retention of auth records (E-001/F-004/T-003 section 4).

Bounded batches in the existing mail worker process; replicas do not block each other.
TTL checks in the API never depend on this having run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.core.security import now_utc
from app.db import session as db_session
from app.models import (
    AccountActionToken,
    AccountEmailChange,
    AppLog,
    GoogleChallenge,
    LlmCallPayload,
    LlmUsage,
    MailOutbox,
    MailProviderEvent,
    RecentAuthProof,
)
from app.services.auth_limits import cleanup_expired
from app.services.content_reports import purge_resolved_reports
from app.services.sync_pull import purge_sync_tombstones

logger = logging.getLogger(__name__)

BATCH = 100
DIAGNOSTICS_BATCH = 1000
_TERMINAL = ("accepted", "failed", "cancelled")


async def _delete_ids(model, id_column, where, limit: int) -> int:
    async with db_session.async_session_factory() as db:
        ids = (
            await db.execute(select(id_column).where(where).limit(limit).with_for_update(skip_locked=True))
        ).scalars().all()
        if ids:
            await db.execute(delete(model).where(id_column.in_(ids)))
        await db.commit()
        return len(ids)


async def purge_auth_records(*, now: datetime | None = None, limit: int = BATCH) -> dict[str, int]:
    now = now or now_utc()
    week = now - timedelta(days=7)
    counts: dict[str, int] = {}
    counts["rate_buckets"] = await cleanup_expired(limit=limit)
    counts["provider_events"] = await _delete_ids(
        MailProviderEvent,
        MailProviderEvent.svix_id,
        MailProviderEvent.received_at < week,
        limit,
    )
    async with db_session.async_session_factory() as db:
        # Payload (the link) goes first, metadata a week after the mail ended.
        wiped = await db.execute(
            update(MailOutbox)
            .where(
                MailOutbox.dispatch_state.in_(_TERMINAL),
                MailOutbox.created_at < now - timedelta(hours=24),
                MailOutbox.payload_ciphertext != b"",
            )
            .values(payload_ciphertext=b"")
        )
        await db.commit()
        counts["payloads_wiped"] = wiped.rowcount or 0
    counts["outbox"] = await _delete_ids(
        MailOutbox,
        MailOutbox.id,
        (MailOutbox.dispatch_state.in_(_TERMINAL)) & (MailOutbox.expires_at < week),
        limit,
    )
    counts["action_tokens"] = await _delete_ids(
        AccountActionToken,
        AccountActionToken.id,
        AccountActionToken.expires_at < week,
        limit,
    )
    counts["email_changes"] = await _delete_ids(
        AccountEmailChange,
        AccountEmailChange.id,
        AccountEmailChange.expires_at < week,
        limit,
    )
    counts["recent_auth"] = await _delete_ids(
        RecentAuthProof,
        RecentAuthProof.id,
        RecentAuthProof.expires_at < now - timedelta(days=1),
        limit,
    )
    counts["google_challenges"] = await _delete_ids(
        GoogleChallenge,
        GoogleChallenge.id,
        GoogleChallenge.expires_at < now - timedelta(days=1),
        limit,
    )
    # Tombstones synchronizacji (30 dni) czyszczone tym samym przebiegiem workera.
    counts["sync_tombstones"] = await purge_sync_tombstones(now=now)
    counts["content_reports"] = await purge_resolved_reports(now=now, limit=limit)
    counts.update(await purge_diagnostics(now=now))
    return counts


async def purge_diagnostics(*, now: datetime, limit: int = DIAGNOSTICS_BATCH) -> dict[str, int]:
    """Technical logs 7 days, cost metrics 30 days (F-007/T-001); independent of AI traffic."""
    settings = get_settings()
    logs_cutoff = now - timedelta(days=max(1, settings.app_log_retention_days))
    usage_cutoff = now - timedelta(days=max(1, settings.llm_usage_retention_days))
    payload_cutoff = now - timedelta(days=max(1, settings.llm_payload_ttl_days))
    return {
        "app_logs": await _delete_ids(AppLog, AppLog.id, AppLog.created_at < logs_cutoff, limit),
        "llm_payloads": await _delete_ids(
            LlmCallPayload,
            LlmCallPayload.llm_usage_id,
            LlmCallPayload.created_at < payload_cutoff,
            limit,
        ),
        "llm_usage": await _delete_ids(
            LlmUsage, LlmUsage.id, LlmUsage.created_at < usage_cutoff, limit
        ),
    }

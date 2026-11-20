"""Content reports: idempotent intake, owner view, operator transitions, retention (F-007/T-002).

A report never changes `learnable`/`ready`, never calls an LLM and is independent of
`CardCorrection`. The excerpt is a claim of the user, not evidence and not an instruction.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_errors import api_error
from app.core.security import now_utc
from app.db import session as db_session
from app.models import ContentReport, ContentReportReceipt, LanguageProfile, LearningCard, User
from app.schemas.content_reports import ContentReportCreate

logger = logging.getLogger(__name__)

RESOLUTION_CODES = ("fixed", "no_change", "duplicate", "not_actionable", "needs_followup")
# Privacy and safety first, then the oldest.
PRIORITY_REASONS = ("privacy", "offensive")
DETAIL_RETENTION = timedelta(days=30)
RESPONSE_TARGET_WORKING_DAYS = 2


@dataclass(frozen=True)
class ReportOutcome:
    report_id: UUID
    status: str
    received_at: datetime
    resolution_code: str | None
    created: bool


def fingerprint(body: ContentReportCreate) -> str:
    """Canonical hash of what the user wrote; the app version is not part of the request."""
    canonical = json.dumps(
        [
            str(body.profile_id),
            body.target_kind,
            str(body.target_id) if body.target_id else None,
            body.field,
            body.reason,
            body.excerpt,
            body.note,
        ],
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _conflict() -> Exception:
    return api_error(409, "report_request_conflict")


def _not_found() -> Exception:
    return api_error(404, "report_target_not_found")


async def _outcome_for_receipt(db: AsyncSession, receipt: ContentReportReceipt) -> ReportOutcome:
    report = None
    if receipt.expired_at is None:
        report = (
            await db.execute(select(ContentReport).where(ContentReport.id == receipt.report_id))
        ).scalar_one_or_none()
    if report is None:
        return ReportOutcome(receipt.report_id, "expired", receipt.received_at, None, False)
    return ReportOutcome(
        report.id, report.status, report.received_at, report.resolution_code, False
    )


async def _receipt(db: AsyncSession, user_id: UUID, client_id: UUID) -> ContentReportReceipt | None:
    return (
        await db.execute(
            select(ContentReportReceipt).where(
                ContentReportReceipt.user_id == user_id,
                ContentReportReceipt.client_report_id == client_id,
            )
        )
    ).scalar_one_or_none()


async def _replay(db: AsyncSession, receipt: ContentReportReceipt, print_: str) -> ReportOutcome:
    if receipt.fingerprint != print_:
        raise _conflict()
    return await _outcome_for_receipt(db, receipt)


async def submit_report(db: AsyncSession, user: User, body: ContentReportCreate) -> ReportOutcome:
    print_ = fingerprint(body)
    try:
        # Receipt first: a deleted target never turns an accepted retry into a 404.
        known = await _receipt(db, user.id, body.client_report_id)
        if known is not None:
            return await _replay(db, known, print_)
        profile = (
            await db.execute(
                select(LanguageProfile).where(
                    LanguageProfile.id == body.profile_id, LanguageProfile.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            raise _not_found()
        if body.target_kind == "card" and body.target_id is not None:
            owned = (
                await db.execute(
                    select(LearningCard.id).where(
                        LearningCard.id == body.target_id,
                        LearningCard.user_id == user.id,
                        LearningCard.profile_id == profile.id,
                    )
                )
            ).scalar_one_or_none()
            if owned is None:
                raise _not_found()
        now = now_utc()
        report = ContentReport(
            user_id=user.id,
            client_report_id=body.client_report_id,
            fingerprint=print_,
            profile_id=profile.id,
            app_lang=profile.app_lang,
            learning_lang=profile.learning_lang,
            target_kind=body.target_kind,
            target_id=body.target_id,
            field=body.field,
            reason=body.reason,
            excerpt=body.excerpt,
            note=body.note,
            app_version=body.app_version,
            received_at=now,
            status="received",
        )
        try:
            async with db.begin_nested():
                db.add(report)
                await db.flush()
                db.add(
                    ContentReportReceipt(
                        user_id=user.id,
                        client_report_id=body.client_report_id,
                        fingerprint=print_,
                        report_id=report.id,
                        received_at=now,
                    )
                )
                await db.flush()
        except IntegrityError:
            # A parallel identical request won the race: answer from its receipt.
            winner = await _receipt(db, user.id, body.client_report_id)
            if winner is None:
                raise
            return await _replay(db, winner, print_)
        outcome = ReportOutcome(report.id, "received", now, None, True)
        await db.commit()
        return outcome
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("content report store failed (%s)", type(exc).__name__)
        raise api_error(503, "report_temporarily_unavailable") from exc


async def owner_view(db: AsyncSession, user_id: UUID, report_id: UUID) -> ReportOutcome | None:
    report = (
        await db.execute(
            select(ContentReport).where(
                ContentReport.id == report_id, ContentReport.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if report is not None:
        return ReportOutcome(
            report.id, report.status, report.received_at, report.resolution_code, False
        )
    receipt = (
        await db.execute(
            select(ContentReportReceipt).where(
                ContentReportReceipt.report_id == report_id,
                ContentReportReceipt.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if receipt is None:
        return None
    return ReportOutcome(receipt.report_id, "expired", receipt.received_at, None, False)


async def list_reports(db: AsyncSession, *, status: str | None, page: int, size: int = 50):
    """Open work first: privacy/safety reasons, then the oldest; resolved ones last."""
    order = (
        case((ContentReport.status == "resolved", 1), else_=0),
        case((ContentReport.reason.in_(PRIORITY_REASONS), 0), else_=1),
        ContentReport.received_at.asc(),
    )
    query = select(ContentReport).order_by(*order)
    count = select(func.count()).select_from(ContentReport)
    if status:
        query = query.where(ContentReport.status == status)
        count = count.where(ContentReport.status == status)
    rows = (await db.execute(query.limit(size).offset(max(0, page - 1) * size))).scalars().all()
    total = (await db.execute(count)).scalar_one()
    return rows, total


def working_days_between(start: datetime, end: datetime) -> int:
    """Whole Monday-Friday days elapsed; the 2 working day response target is measured with it."""
    days, cursor = 0, start.date()
    while cursor < end.date():
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            days += 1
    return days


async def take_report(db: AsyncSession, report_id: UUID, operator: str) -> bool:
    now = now_utc()
    result = await db.execute(
        update(ContentReport)
        .where(ContentReport.id == report_id, ContentReport.status == "received")
        .values(status="in_review", in_review_at=now, operator=operator[:64])
    )
    return bool(result.rowcount)


async def resolve_report(
    db: AsyncSession, report_id: UUID, operator: str, code: str, note: str | None
) -> bool:
    if code not in RESOLUTION_CODES:
        raise ValueError("resolution_code")
    now = now_utc()
    result = await db.execute(
        update(ContentReport)
        .where(ContentReport.id == report_id, ContentReport.status == "in_review")
        .values(
            status="resolved",
            resolution_code=code,
            operator_note=(note or "").strip()[:1000] or None,
            operator=operator[:64],
            resolved_at=now,
        )
    )
    return bool(result.rowcount)


async def purge_resolved_reports(*, now: datetime | None = None, limit: int = 100) -> int:
    """Resolved + 30 days: the text goes, the receipt stays as `expired`."""
    now = now or now_utc()
    async with db_session.async_session_factory() as db:
        ids = (
            await db.execute(
                select(ContentReport.id)
                .where(
                    ContentReport.status == "resolved",
                    ContentReport.resolved_at < now - DETAIL_RETENTION,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        if ids:
            await db.execute(
                update(ContentReportReceipt)
                .where(ContentReportReceipt.report_id.in_(ids))
                .values(expired_at=now)
            )
            await db.execute(delete(ContentReport).where(ContentReport.id.in_(ids)))
        await db.commit()
        return len(ids)

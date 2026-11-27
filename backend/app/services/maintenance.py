"""Periodic operator maintenance, every 15 minutes (E-001/F-008/T-004).

Runs without any LLM call and with a fixed number of queries per cycle: heartbeat, AI cap review
and alerts, wake of cards parked by the cap, stale reservations, stuck mail/purge/report
checks and journal retention. Alerts are deduplicated per (environment, kind) in `ops_alerts`
and carry counts and amounts only, never an account, address or content.
"""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings, is_mail_address
from app.db import session as db_session
from app.models import AccountDeletion, ContentReport, MailOutbox, OpsAlert, OpsState
from app.services import account_journal, ai_budget, data_retention
from app.services.mail_transport import OutgoingMail, get_transport

logger = logging.getLogger(__name__)

CYCLE_INTERVAL_S = 15 * 60
HEARTBEAT_KEY = "maintenance_heartbeat"
HEARTBEAT_MAX_AGE = timedelta(minutes=30)
REMIND_EVERY = timedelta(hours=6)
MAIL_STUCK_AFTER = timedelta(minutes=10)
PURGE_STUCK_AFTER = timedelta(hours=1)
PURGE_DUE_SOON = timedelta(hours=24)
REPORT_OVERDUE_AFTER = timedelta(hours=36)
RESUME_MARGIN_USD = Decimal("0.05")
ACCOUNT_DAILY_WARN_USD = Decimal("2")

_WARN_LEVELS = ((Decimal("0.7"), 1), (Decimal("0.9"), 2))


async def beat(now: datetime | None = None) -> None:
    clock = now or datetime.now(UTC)
    async with db_session.async_session_factory() as db:
        await db.execute(
            pg_insert(OpsState)
            .values(key=HEARTBEAT_KEY, value_at=clock)
            .on_conflict_do_update(index_elements=["key"], set_={"value_at": clock})
        )
        await db.commit()


async def last_heartbeat() -> datetime | None:
    async with db_session.async_session_factory() as db:
        value = (
            await db.execute(select(OpsState.value_at).where(OpsState.key == HEARTBEAT_KEY))
        ).scalar_one_or_none()
        await db.rollback()
    return value


def budget_level(status: ai_budget.BudgetStatus) -> int:
    """0 none, 1 = 70% and 2 = 90% of WARN, 3 = above WARN, 4 = HARD reached (calls stopped)."""
    if status.hard > 0 and status.committed >= status.hard:
        return 4
    if status.warn > 0 and status.committed > status.warn:
        return 3
    level = 0
    for threshold, value in _WARN_LEVELS:
        if status.ratio >= threshold:
            level = value
    return level


def _recipient() -> str:
    settings = get_settings()
    for candidate in (settings.operator_alert_email, settings.support_email):
        if is_mail_address(candidate):
            return candidate.strip()
    return ""


async def _deliver(kind: str, level: int, message: str, now: datetime) -> bool:
    settings = get_settings()
    to = _recipient()
    if not to:
        logger.error("ops alert %s not sent: no operator address", kind)
        return False
    subject = f"[Vocabulario {settings.environment}] {kind} level {level}"
    body = f"{message}\n\nenvironment: {settings.environment}\nat: {now.isoformat()}"
    mail = OutgoingMail(
        to=to,
        sender=settings.mail_from,
        reply_to="",
        subject=subject,
        text=body,
        html=f"<pre>{html.escape(body)}</pre>",
        locale="en",
        template="ops_alert",
    )
    key = f"ops-{settings.environment}-{kind}-{level}-{int(now.timestamp())}"
    try:
        result = await get_transport().send(mail, key)
    except Exception as exc:  # noqa: BLE001 - alerting must never stop the cycle
        logger.error("ops alert %s failed (%s)", kind, type(exc).__name__)
        return False
    if result.outcome != "accepted":
        logger.error("ops alert %s not accepted (%s)", kind, result.error_code)
        return False
    return True


async def raise_alert(kind: str, level: int, message: str, now: datetime) -> bool:
    """Send on first sight, on a worse level, on recovery, or as a reminder every 6 hours."""
    environment = get_settings().environment[:16]
    async with db_session.async_session_factory() as db:
        row = (
            await db.execute(
                select(OpsAlert)
                .where(OpsAlert.environment == environment, OpsAlert.kind == kind)
                .with_for_update()
            )
        ).scalar_one_or_none()
        sent = False
        if row is None:
            if level == 0:
                await db.rollback()
                return False
            row = OpsAlert(
                environment=environment,
                kind=kind,
                severity="0",
                active=False,
                first_seen_at=now,
            )
            db.add(row)
        previous = int(row.severity) if row.active else 0
        due = False
        if level == 0:
            if row.active:
                if await _deliver(kind, 0, f"{kind}: back to normal", now):
                    row.active = False
                    row.severity = "0"
                    row.last_sent_at = now
                    sent = True
        else:
            if not row.active:
                row.first_seen_at = now
            due = (
                not row.active
                or level > previous
                or row.last_sent_at is None
                or now - row.last_sent_at >= REMIND_EVERY
            )
            if due:
                if await _deliver(kind, level, message, now):
                    row.active = True
                    row.severity = str(level)
                    row.last_sent_at = now
                    sent = True
            elif level != previous:
                row.severity = str(level)
        await db.commit()
        return sent


async def _review_budget(now: datetime) -> None:
    settings = get_settings()
    if not settings.ai_budget_enforced:
        return
    await ai_budget.sweep_stale(now)
    status = await ai_budget.status(now)
    level = budget_level(status)
    await raise_alert(
        "ai_budget",
        level,
        f"AI spend {status.period}: spent {status.spent} + reserved {status.reserved} + "
        f"unresolved {status.unresolved} of warn {status.warn} / hard {status.hard} USD."
        + (" New paid calls are stopped." if level == 4 else ""),
        now,
    )
    leftovers = status.unresolved + status.unresolved_older
    await raise_alert(
        "ai_unresolved",
        1 if leftovers > 0 else 0,
        f"{leftovers} USD of AI calls with unknown cost are counted conservatively; "
        "reconcile with the provider and clear them.",
        now,
    )
    if status.has_room(RESUME_MARGIN_USD):
        from app.services.card_jobs import resume_waiting_budget

        await resume_waiting_budget()
    max_account_cost, over_threshold = await ai_budget.daily_account_cost_status(
        ACCOUNT_DAILY_WARN_USD, now
    )
    await raise_alert(
        "ai_account_daily",
        1 if over_threshold else 0,
        f"{over_threshold} account(s) reached the daily AI warning threshold of "
        f"{ACCOUNT_DAILY_WARN_USD} USD; highest estimated spend is {max_account_cost} USD. "
        "No account is blocked.",
        now,
    )


async def _review_mail(now: datetime) -> None:
    async with db_session.async_session_factory() as db:
        oldest = (
            await db.execute(
                select(func.min(MailOutbox.created_at)).where(
                    MailOutbox.dispatch_state == "queued", MailOutbox.expires_at > now
                )
            )
        ).scalar_one_or_none()
        await db.rollback()
    stuck = oldest is not None and now - oldest > MAIL_STUCK_AFTER
    await raise_alert("mail_stuck", 1 if stuck else 0, "The oldest account e-mail is waiting over 10 minutes.", now)


async def _review_purge(now: datetime) -> None:
    async with db_session.async_session_factory() as db:
        stalled = (
            await db.execute(
                select(func.count()).where(
                    AccountDeletion.state == "purging",
                    AccountDeletion.last_error_code.is_not(None),
                    AccountDeletion.purge_started_at < now - PURGE_STUCK_AFTER,
                )
            )
        ).scalar_one()
        near_deadline = (
            await db.execute(
                select(func.count()).where(
                    AccountDeletion.state.in_(("grace", "purging")),
                    AccountDeletion.purge_due_at < now + PURGE_DUE_SOON,
                )
            )
        ).scalar_one()
        await db.rollback()
    level = 2 if near_deadline else (1 if stalled else 0)
    await raise_alert(
        "purge_stuck",
        level,
        f"Account deletion: {stalled} stalled process(es), {near_deadline} due within 24 hours.",
        now,
    )


async def _review_reports(now: datetime) -> None:
    async with db_session.async_session_factory() as db:
        overdue = (
            await db.execute(
                select(func.count()).where(
                    ContentReport.status == "received",
                    ContentReport.received_at < now - REPORT_OVERDUE_AFTER,
                )
            )
        ).scalar_one()
        await db.rollback()
    await raise_alert(
        "reports_overdue",
        1 if overdue else 0,
        f"{overdue} content report(s) have no answer for over 36 hours.",
        now,
    )


async def _retention(now: datetime) -> None:
    async with db_session.async_session_factory() as db:
        await account_journal.purge_old(db, now)
        await db.commit()


async def _privacy_retention(now: datetime) -> None:
    async with db_session.async_session_factory() as db:
        await data_retention.purge_expired(db, now)
        await db.commit()


async def run_cycle(now: datetime | None = None) -> None:
    """One pass. A failing step is logged by class and never blocks the others."""
    clock = now or datetime.now(UTC)
    steps = (
        beat, _review_budget, _review_mail, _review_purge, _review_reports,
        _retention, _privacy_retention, beat,
    )
    for step in steps:
        try:
            await step(clock)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("maintenance step %s failed (%s)", step.__name__, type(exc).__name__)


async def run_maintenance_worker() -> None:
    while True:
        await run_cycle()
        await asyncio.sleep(CYCLE_INTERVAL_S)

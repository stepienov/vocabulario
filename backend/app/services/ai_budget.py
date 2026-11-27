"""Monthly AI spend cap shared by every replica (E-001/F-008/T-004).

A paid call first reserves its worst-case cost in PostgreSQL; the external request runs outside
the transaction; the actual cost settles the reservation. A call whose cost is unknown (timeout,
missing usage) stays `unresolved` at the conservative amount until the operator reconciles it
with the provider, so it never silently frees budget. The cap is HARD; WARN only raises alerts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.db import session as db_session
from app.models import AiBudgetPeriod, AiBudgetReservation, LlmUsage
from app.services.llm_pricing import TokenUsage, estimate_cost_usd, estimate_max_cost_usd

logger = logging.getLogger(__name__)

# Applied to the estimate only when a call sets no output cap.
DEFAULT_OUTPUT_TOKENS = 8192
# A reservation that never settled (crashed worker) is treated as an unknown cost after this.
STALE_RESERVATION = timedelta(minutes=15)


class AiBudgetExhausted(Exception):
    """The monthly cap (or the provider balance) does not allow another paid call."""

    code = "ai_budget_exhausted"

    def __init__(self, *, provider_side: bool = False) -> None:
        super().__init__(self.code)
        self.provider_side = provider_side


class AiBudgetUnavailable(Exception):
    """The cap cannot be evaluated (unpriced model, database error): never a free fallback."""

    code = "ai_budget_unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True)
class Reservation:
    id: UUID
    period: str
    amount: Decimal


def period_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m")


async def reserve(
    model: str,
    purpose: str,
    prompt_chars: int,
    max_tokens: int | None,
    *,
    now: datetime | None = None,
) -> Reservation | None:
    """Reserve the worst-case cost of one call. None when the cap is not configured."""
    settings = get_settings()
    if not settings.ai_budget_enforced:
        return None
    estimate = estimate_max_cost_usd(model, prompt_chars, max_tokens or DEFAULT_OUTPUT_TOKENS)
    if estimate is None:
        logger.error("ai budget: no price for model %r", model)
        raise AiBudgetUnavailable()
    hard = settings.ai_monthly_hard_usd
    if estimate > hard:
        raise AiBudgetExhausted()
    period = period_key(now)
    try:
        async with db_session.async_session_factory() as db:
            await db.execute(
                pg_insert(AiBudgetPeriod)
                .values(period=period, spent_usd=0, reserved_usd=0, unresolved_usd=0)
                .on_conflict_do_nothing()
            )
            row = (
                await db.execute(
                    select(AiBudgetPeriod).where(AiBudgetPeriod.period == period).with_for_update()
                )
            ).scalar_one()
            committed = row.spent_usd + row.reserved_usd + row.unresolved_usd
            if committed + estimate > hard:
                await db.rollback()
                raise AiBudgetExhausted()
            row.reserved_usd = row.reserved_usd + estimate
            reservation = Reservation(uuid4(), period, estimate)
            db.add(
                AiBudgetReservation(
                    id=reservation.id,
                    period=period,
                    model=(model or "")[:64],
                    purpose=(purpose or "")[:32],
                    reserved_usd=estimate,
                    state="reserved",
                )
            )
            await db.commit()
            return reservation
    except AiBudgetExhausted:
        raise
    except Exception as exc:  # noqa: BLE001 - an unreadable cap must stop the call
        logger.error("ai budget reserve failed (%s)", type(exc).__name__)
        raise AiBudgetUnavailable() from exc


async def _close(
    reservation: Reservation,
    state: str,
    actual: Decimal | None,
    *,
    now: datetime | None = None,
) -> None:
    """Move one reserved amount to its final bucket; idempotent per reservation."""
    clock = now or datetime.now(UTC)
    try:
        async with db_session.async_session_factory() as db:
            period = (
                await db.execute(
                    select(AiBudgetPeriod)
                    .where(AiBudgetPeriod.period == reservation.period)
                    .with_for_update()
                )
            ).scalar_one()
            changed = await db.execute(
                update(AiBudgetReservation)
                .where(AiBudgetReservation.id == reservation.id, AiBudgetReservation.state == "reserved")
                .values(state=state, actual_usd=actual, settled_at=clock)
            )
            if changed.rowcount:
                period.reserved_usd = max(Decimal(0), period.reserved_usd - reservation.amount)
                if state == "settled" and actual is not None:
                    period.spent_usd = period.spent_usd + actual
                elif state == "unresolved":
                    period.unresolved_usd = period.unresolved_usd + reservation.amount
            await db.commit()
    except Exception as exc:  # noqa: BLE001 - the sweep turns a stuck reservation into unresolved
        logger.error("ai budget settle failed (%s)", type(exc).__name__)


async def settle(
    reservation: Reservation | None, model: str, usage: TokenUsage | None
) -> None:
    """The provider answered: charge the real cost; unknown usage stays unresolved."""
    if reservation is None:
        return
    cost = None
    if usage is not None and (usage.prompt_tokens or usage.completion_tokens):
        cost = estimate_cost_usd(model, usage)
    if cost is None:
        await _close(reservation, "unresolved", None)
    else:
        await _close(reservation, "settled", cost)


async def release(reservation: Reservation | None) -> None:
    """The provider certainly did not run the call (it answered with an error status)."""
    if reservation is not None:
        await _close(reservation, "released", None)


async def leave_unresolved(reservation: Reservation | None) -> None:
    """Timeout/connection loss after the request left: the cost may exist, so it stays counted."""
    if reservation is not None:
        await _close(reservation, "unresolved", None)


async def sweep_stale(now: datetime | None = None) -> int:
    """Reservations that never settled become unresolved; returns how many."""
    clock = now or datetime.now(UTC)
    async with db_session.async_session_factory() as db:
        stale = (
            await db.execute(
                select(AiBudgetReservation).where(
                    AiBudgetReservation.state == "reserved",
                    AiBudgetReservation.created_at < clock - STALE_RESERVATION,
                )
            )
        ).scalars().all()
        found = [Reservation(r.id, r.period, r.reserved_usd) for r in stale]
        await db.rollback()
    for item in found:
        await _close(item, "unresolved", None, now=clock)
    return len(found)


@dataclass(frozen=True)
class BudgetStatus:
    period: str
    spent: Decimal
    reserved: Decimal
    unresolved: Decimal
    warn: Decimal
    hard: Decimal
    unresolved_older: Decimal

    @property
    def committed(self) -> Decimal:
        return self.spent + self.reserved + self.unresolved

    @property
    def ratio(self) -> Decimal:
        return self.committed / self.warn if self.warn > 0 else Decimal(0)

    def has_room(self, amount: Decimal = Decimal("0")) -> bool:
        return self.hard > 0 and self.committed + amount <= self.hard


async def status(now: datetime | None = None) -> BudgetStatus:
    settings = get_settings()
    period = period_key(now)
    async with db_session.async_session_factory() as db:
        rows = (await db.execute(select(AiBudgetPeriod))).scalars().all()
        amounts = [
            (row.period, row.spent_usd, row.reserved_usd, row.unresolved_usd)
            for row in rows
        ]
        await db.rollback()
    current = next((row for row in amounts if row[0] == period), None)
    older = sum((row[3] for row in amounts if row[0] != period), Decimal())
    return BudgetStatus(
        period=period,
        spent=current[1] if current else Decimal(0),
        reserved=current[2] if current else Decimal(0),
        unresolved=current[3] if current else Decimal(0),
        warn=settings.ai_monthly_warn_usd,
        hard=settings.ai_monthly_hard_usd,
        unresolved_older=older,
    )


async def daily_account_cost_status(
    threshold: Decimal, now: datetime | None = None
) -> tuple[Decimal, int]:
    """Return max estimated UTC-day account spend and count above threshold, without IDs."""
    clock = now or datetime.now(UTC)
    day_start = clock.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    daily = (
        select(
            LlmUsage.user_id.label("user_id"),
            func.coalesce(func.sum(LlmUsage.estimated_cost_usd), Decimal(0)).label("cost"),
        )
        .where(LlmUsage.user_id.is_not(None), LlmUsage.created_at >= day_start)
        .group_by(LlmUsage.user_id)
        .subquery()
    )
    async with db_session.async_session_factory() as db:
        max_cost, over_threshold = (
            await db.execute(
                select(
                    func.coalesce(func.max(daily.c.cost), Decimal(0)),
                    func.count().filter(daily.c.cost >= threshold),
                )
            )
        ).one()
        await db.rollback()
    return max_cost, over_threshold


async def resolve_unresolved(period: str, actual_total_usd: Decimal) -> Decimal:
    """Operator reconciliation: replace the conservative unresolved amount with the real cost."""
    async with db_session.async_session_factory() as db:
        row = (
            await db.execute(
                select(AiBudgetPeriod).where(AiBudgetPeriod.period == period).with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            await db.rollback()
            return Decimal(0)
        cleared = row.unresolved_usd
        row.unresolved_usd = Decimal(0)
        row.spent_usd = row.spent_usd + actual_total_usd
        await db.execute(
            update(AiBudgetReservation)
            .where(AiBudgetReservation.period == period, AiBudgetReservation.state == "unresolved")
            .values(state="settled")
        )
        await db.commit()
        return cleared

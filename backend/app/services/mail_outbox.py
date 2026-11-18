"""Durable account mail queue (E-001/F-004/T-002).

`enqueue_mail` runs inside the caller's transaction (no commit), so the mail exists
exactly when the account change does. One worker loop per process claims single rows
with `FOR UPDATE SKIP LOCKED` and a 60 s lease, sends outside any transaction and keeps
the same idempotency key `auth-mail/<id>` for every attempt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import now_utc
from app.db import session as db_session
from app.models import MailOutbox
from app.services.action_tokens import action_token_is_current
from app.services.auth_limits import LimiterUnavailable, reserve_mail_send
from app.services.mail_transport import MailTransport, OutgoingMail, SendResult, get_transport

logger = logging.getLogger(__name__)

LEASE = timedelta(seconds=60)
BATCH_SIZE = 5
IDLE_WAKE_S = 30.0
PURGE_EVERY_S = 15 * 60.0
MAX_ATTEMPTS = 6
# Attempt n (0-based) is due this long after the mail was queued.
ATTEMPT_OFFSETS_S = (0, 30, 120, 300, 600, 1200)
# Mails that carry a one-time link; they are dropped once the link stops being valid.
LINK_KINDS = frozenset({"verify_email", "reset_password", "change_email"})

assert len(ATTEMPT_OFFSETS_S) == MAX_ATTEMPTS


class MailKeyError(RuntimeError):
    """MAIL_OUTBOX_KEY is missing in a deployed environment."""


@lru_cache
def _ephemeral_key() -> bytes:
    return Fernet.generate_key()


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.mail_outbox_key.strip()
    if key:
        return Fernet(key.encode("ascii"))
    if settings.is_deployed:
        raise MailKeyError("mail_outbox_key is not configured")
    # Local only: queued mails become undecryptable after a restart and end as failed.
    return Fernet(_ephemeral_key())


def compose_mail(
    *, to: str, subject: str, text: str, html: str, locale: str, template: str
) -> OutgoingMail:
    """Snapshot the configured sender/reply-to now; later config changes do not alter it."""
    settings = get_settings()
    return OutgoingMail(
        to=to,
        sender=settings.mail_from.strip(),
        reply_to=settings.mail_reply_to.strip(),
        subject=subject,
        text=text,
        html=html,
        locale=locale,
        template=template,
    )


async def enqueue_mail(
    db: AsyncSession,
    *,
    kind: str,
    mail: OutgoingMail,
    expires_at: datetime,
    user_id: UUID | None = None,
    action_token_id: UUID | None = None,
    now: datetime | None = None,
) -> MailOutbox:
    """Queue a mail in the caller's transaction. Call `wake_mail_worker()` after commit."""
    if kind in LINK_KINDS and action_token_id is None:
        raise ValueError(f"{kind} mail needs its action token")
    now = now or now_utc()
    payload = json.dumps(asdict(mail), ensure_ascii=False).encode("utf-8")
    row = MailOutbox(
        user_id=user_id,
        kind=kind,
        action_token_id=action_token_id,
        payload_ciphertext=_fernet().encrypt(payload),
        dispatch_state="queued",
        delivery_state="unknown",
        attempts=0,
        next_attempt_at=now,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return row


@dataclass(frozen=True)
class _Claim:
    id: UUID
    kind: str
    attempts: int
    created_at: datetime
    expires_at: datetime
    mail: OutgoingMail


def _end(row: MailOutbox, state: str, code: str) -> None:
    row.dispatch_state = state
    row.lease_until = None
    row.last_error_code = code
    log = logger.warning if state == "failed" else logger.info
    log("mail %s (%s) %s: %s", row.id, row.kind, state, code)


def _decrypt(row: MailOutbox) -> OutgoingMail | None:
    try:
        data = json.loads(_fernet().decrypt(row.payload_ciphertext))
        return OutgoingMail(**data)
    except (InvalidToken, MailKeyError, ValueError, TypeError):
        return None


async def _claim_one(now: datetime) -> tuple[_Claim | None, bool]:
    """Lease one due row. Returns (claim, found_any_row)."""
    async with db_session.async_session_factory() as db:
        row = (
            await db.execute(
                select(MailOutbox)
                .where(
                    or_(
                        and_(
                            MailOutbox.dispatch_state == "queued",
                            MailOutbox.next_attempt_at <= now,
                        ),
                        and_(
                            MailOutbox.dispatch_state == "leased",
                            MailOutbox.lease_until < now,
                        ),
                    )
                )
                .order_by(MailOutbox.next_attempt_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None:
            return None, False
        claim: _Claim | None = None
        if now >= row.expires_at:
            _end(row, "cancelled", "expired")
        elif row.attempts >= MAX_ATTEMPTS:
            _end(row, "failed", "attempts_exhausted")
        elif row.kind in LINK_KINDS and (
            row.action_token_id is None
            or not await action_token_is_current(db, row.action_token_id, now=now)
        ):
            _end(row, "cancelled", "stale_link")
        elif (mail := _decrypt(row)) is None:
            _end(row, "failed", "payload_key_unavailable")
        else:
            row.dispatch_state = "leased"
            row.lease_until = now + LEASE
            row.attempts += 1
            claim = _Claim(row.id, row.kind, row.attempts, row.created_at, row.expires_at, mail)
        await db.commit()
        return claim, True


def _next_attempt(claim: _Claim, result: SendResult, now: datetime) -> datetime:
    due = claim.created_at + timedelta(seconds=ATTEMPT_OFFSETS_S[claim.attempts])
    if result.retry_after_s is not None:
        due = max(due, now + timedelta(seconds=result.retry_after_s))
    return max(due, now)


async def _finish(claim: _Claim, result: SendResult, now: datetime) -> None:
    values: dict = {"lease_until": None}
    if result.outcome == "accepted":
        values |= {
            "dispatch_state": "accepted",
            "provider_message_id": result.provider_message_id,
            "last_error_code": None,
        }
    elif result.outcome == "retry" and claim.attempts < MAX_ATTEMPTS:
        due = _next_attempt(claim, result, now)
        if due >= claim.expires_at:
            values |= {"dispatch_state": "failed", "last_error_code": "expired_before_retry"}
        else:
            values |= {
                "dispatch_state": "queued",
                "next_attempt_at": due,
                "last_error_code": result.error_code,
            }
    else:
        values |= {"dispatch_state": "failed", "last_error_code": result.error_code}
    async with db_session.async_session_factory() as db:
        # Only the lease holder may record the outcome of its attempt.
        await db.execute(
            update(MailOutbox)
            .where(
                MailOutbox.id == claim.id,
                MailOutbox.dispatch_state == "leased",
                MailOutbox.attempts == claim.attempts,
            )
            .values(**values)
        )
        await db.commit()
    if values["dispatch_state"] == "failed":
        logger.warning("mail %s failed: %s", claim.id, values["last_error_code"])
    elif result.outcome == "accepted" and result.provider_message_id:
        # A webhook may have outrun this write; fold in what it already stored.
        from app.services.mail_events import apply_events

        await apply_events(result.provider_message_id)


async def _wait_for_budget(claim: _Claim, wait_s: int, now: datetime) -> None:
    """Give the claim back unspent: waiting for budget is not a delivery attempt."""
    due = now + timedelta(seconds=wait_s)
    if due >= claim.expires_at:
        state = "cancelled" if claim.kind in LINK_KINDS else "failed"
        values = {"dispatch_state": state, "last_error_code": "budget_exhausted"}
    else:
        values = {
            "dispatch_state": "queued",
            "next_attempt_at": due,
            "attempts": claim.attempts - 1,
        }
    async with db_session.async_session_factory() as db:
        await db.execute(
            update(MailOutbox)
            .where(
                MailOutbox.id == claim.id,
                MailOutbox.dispatch_state == "leased",
                MailOutbox.attempts == claim.attempts,
            )
            .values(lease_until=None, **values)
        )
        await db.commit()
    if values["dispatch_state"] != "queued":
        logger.warning("mail %s dropped: send budget exhausted until expiry", claim.id)


async def _budget_wait(claim: _Claim) -> int | None:
    try:
        return await reserve_mail_send(link=claim.kind in LINK_KINDS)
    except LimiterUnavailable:
        return 60


async def deliver_due_mail(
    *, transport: MailTransport | None = None, limit: int = BATCH_SIZE
) -> int:
    """Process up to `limit` due rows; returns how many rows were handled."""
    transport = transport or get_transport()
    handled = 0
    while handled < limit:
        claim, found = await _claim_one(now_utc())
        if not found:
            break
        handled += 1
        if claim is None:
            continue
        wait_s = await _budget_wait(claim)
        if wait_s is not None:
            await _wait_for_budget(claim, wait_s, now_utc())
            continue
        try:
            result = await transport.send(claim.mail, f"auth-mail/{claim.id}")
        except Exception:
            logger.exception("mail transport crashed for %s", claim.id)
            result = SendResult("retry", error_code="transport_exception")
        await _finish(claim, result, now_utc())
    return handled


_wake: asyncio.Event | None = None
_wake_loop: asyncio.AbstractEventLoop | None = None


def _wake_event() -> asyncio.Event:
    global _wake, _wake_loop
    loop = asyncio.get_running_loop()
    if _wake is None or _wake_loop is not loop:
        _wake = asyncio.Event()
        _wake_loop = loop
    return _wake


def wake_mail_worker() -> None:
    """Signal the worker after a commit that queued mail; no-op outside an event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    _wake_event().set()


async def run_mail_worker() -> None:
    last_purge = 0.0
    while True:
        event = _wake_event()
        event.clear()
        try:
            handled = await deliver_due_mail()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("mail worker pass failed")
            handled = 0
        if time.monotonic() - last_purge >= PURGE_EVERY_S:
            last_purge = time.monotonic()
            try:
                from app.services.auth_cleanup import purge_auth_records

                await purge_auth_records()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("auth record cleanup failed")
        if handled >= BATCH_SIZE:
            continue
        try:
            await asyncio.wait_for(event.wait(), timeout=IDLE_WAKE_S)
        except TimeoutError:
            pass

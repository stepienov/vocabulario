"""Change or correction of the app e-mail address (E-001/F-004/T-004).

Helpers run in the caller's transaction and never commit; the caller commits and then wakes
the mail worker. Lock order: user -> sessions -> email change -> action token -> outbox.
`User.email` only changes when the link sent to the new address is confirmed.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.models import AccountActionToken, AccountEmailChange, MailOutbox, User
from app.services.account_recovery import (
    NOTICE_TTL,
    CredentialError,
    MailRateLimited,
    account_link,
    delivery_summary,
    next_mail_allowed_at,
    profile_locale,
    queue_account_mail,
)
from app.services.action_tokens import (
    CHANGE_EMAIL,
    ActionTokenError,
    action_token_hash,
    consume_action_token,
    find_token_owner,
    invalidate_change_tokens,
    issue_action_token,
)
from app.services.auth_sessions import (
    AccessContext,
    SessionAuthError,
    lock_user,
    revoke_user_sessions,
)
from app.services.mail_templates import (
    normalize_locale,
    render_change_email,
    render_email_change_done,
    render_email_change_started,
)
from app.services.recent_auth import consume_recent_auth, recent_auth_hash

CHANGE_PATH = "/account/change-email"
CHANGE_TTL = timedelta(hours=24)
STARTED_KIND = "email_change_started"
DONE_KIND = "email_change_done"


def normalize_email(value: str) -> str:
    """Shared address key: edge whitespace removed, lowercase, nothing else merged."""
    return value.strip().lower()


@dataclass(frozen=True)
class EmailChangeView:
    change: AccountEmailChange
    status: str
    delivery_status: str
    delivery_delayed: bool
    resend_available_at: datetime | None


def effective_state(change: AccountEmailChange, user: User, now: datetime) -> str:
    """Real state of a change without mutating it (a stale pending is expired/cancelled)."""
    if change.state != "pending":
        return change.state
    if now >= change.expires_at:
        return "expired"
    if (
        change.email_revision != user.email_revision
        or change.credentials_revision != user.credentials_revision
    ):
        return "cancelled"
    return "pending"


async def _settle(
    db: AsyncSession, change: AccountEmailChange, user: User, now: datetime
) -> str:
    state = effective_state(change, user, now)
    if state != change.state:
        change.state = state
        change.finished_at = now
        await invalidate_change_tokens(db, change.id, now=now)
        await db.flush()
    return state


async def _owned_change(
    db: AsyncSession, user_id: UUID, change_id: UUID, *, lock: bool
) -> AccountEmailChange:
    query = select(AccountEmailChange).where(
        AccountEmailChange.id == change_id, AccountEmailChange.user_id == user_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    change = (await db.execute(query)).scalar_one_or_none()
    if change is None:
        raise CredentialError(404, "email_change_not_found")
    return change


async def request_known(db: AsyncSession, user_id: UUID, request_id: UUID) -> bool:
    """Whether this request id was already stored (an exact retry must not use the limit)."""
    return (
        await db.execute(
            select(AccountEmailChange.id).where(
                AccountEmailChange.user_id == user_id,
                AccountEmailChange.request_id == request_id,
            )
        )
    ).first() is not None


def _fingerprint(new_email: str, proof_token: str) -> str:
    return hashlib.sha256(f"{new_email}\n{recent_auth_hash(proof_token)}".encode()).hexdigest()


async def _queue_confirmation(
    db: AsyncSession, user: User, change: AccountEmailChange, now: datetime
) -> None:
    issued = await issue_action_token(
        db, user, CHANGE_EMAIL, now=now, email_change_id=change.id, expires_at=change.expires_at
    )
    hours = max(1, math.ceil((issued.row.expires_at - now).total_seconds() / 3600))
    locale = normalize_locale(await profile_locale(db, user.id))
    rendered = render_change_email(
        locale, account_link(CHANGE_PATH, issued.token, locale), hours=hours
    )
    await queue_account_mail(
        db,
        user,
        CHANGE_EMAIL,
        rendered,
        expires_at=issued.row.expires_at,
        now=now,
        action_token_id=issued.row.id,
        to=change.new_email,
    )


async def request_email_change(
    db: AsyncSession,
    user_id: UUID,
    ctx: AccessContext,
    *,
    new_email: str,
    proof_token: str,
    request_id: UUID,
    now: datetime | None = None,
) -> AccountEmailChange:
    now = now or now_utc()
    target = normalize_email(new_email)
    user = await lock_user(db, user_id)
    if user is None:
        raise SessionAuthError(401, "session_revoked")
    fingerprint = _fingerprint(target, proof_token)
    existing = (
        await db.execute(
            select(AccountEmailChange).where(
                AccountEmailChange.user_id == user.id,
                AccountEmailChange.request_id == request_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise CredentialError(409, "request_id_conflict")
        return existing
    if target == user.email:
        raise CredentialError(409, "email_unchanged")
    taken = (await db.execute(select(User.id).where(User.email == target))).first()
    if taken is not None:
        raise CredentialError(409, "email_unavailable")
    pending = (
        await db.execute(
            select(AccountEmailChange)
            .where(AccountEmailChange.user_id == user.id, AccountEmailChange.state == "pending")
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if pending is not None:
        await _settle(db, pending, user, now)
    await consume_recent_auth(db, user, ctx, proof_token, CHANGE_EMAIL, now=now)
    if pending is not None and pending.state == "pending":
        pending.state = "replaced"
        pending.finished_at = now
        await invalidate_change_tokens(db, pending.id, now=now)
        await db.flush()
    change = AccountEmailChange(
        user_id=user.id,
        request_id=request_id,
        request_fingerprint=fingerprint,
        mode="change" if user.email_verified_at is not None else "correction",
        new_email=target,
        email_revision=user.email_revision,
        credentials_revision=user.credentials_revision,
        state="pending",
        created_at=now,
        expires_at=now + CHANGE_TTL,
    )
    db.add(change)
    await db.flush()
    await _queue_confirmation(db, user, change, now)
    if change.mode == "change":
        # A typo correction would mail a possibly foreign mailbox, so only a real change notifies.
        locale = await profile_locale(db, user.id) or ""
        await queue_account_mail(
            db,
            user,
            STARTED_KIND,
            render_email_change_started(locale),
            expires_at=now + NOTICE_TTL,
            now=now,
        )
    return change


async def describe(
    db: AsyncSession, user: User, change: AccountEmailChange, *, now: datetime | None = None
) -> EmailChangeView:
    now = now or now_utc()
    status = effective_state(change, user, now)
    latest = (
        await db.execute(
            select(MailOutbox.dispatch_state, MailOutbox.delivery_state)
            .join(AccountActionToken, AccountActionToken.id == MailOutbox.action_token_id)
            .where(AccountActionToken.email_change_id == change.id)
            .order_by(MailOutbox.created_at.desc())
            .limit(1)
        )
    ).one_or_none()
    delivery, delayed = ("not_requested", False) if latest is None else delivery_summary(*latest)
    resend_at = None
    if status == "pending":
        resend_at = await next_mail_allowed_at(db, user.id, CHANGE_EMAIL, now)
        resend_at = resend_at or now
    return EmailChangeView(change, status, delivery, delayed, resend_at)


async def latest_change(
    db: AsyncSession, user: User, *, now: datetime | None = None
) -> EmailChangeView | None:
    change = (
        await db.execute(
            select(AccountEmailChange)
            .where(AccountEmailChange.user_id == user.id)
            .order_by(AccountEmailChange.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return None if change is None else await describe(db, user, change, now=now)


async def resend_email_change(
    db: AsyncSession, user_id: UUID, change_id: UUID, *, now: datetime | None = None
) -> AccountEmailChange:
    now = now or now_utc()
    user = await lock_user(db, user_id)
    if user is None:
        raise SessionAuthError(401, "session_revoked")
    change = await _owned_change(db, user.id, change_id, lock=True)
    state = await _settle(db, change, user, now)
    if state == "expired":
        raise CredentialError(410, "email_change_expired")
    if state != "pending":
        raise CredentialError(409, "email_change_inactive")
    retry_at = await next_mail_allowed_at(db, user.id, CHANGE_EMAIL, now)
    if retry_at is not None:
        raise MailRateLimited(retry_at)
    await _queue_confirmation(db, user, change, now)
    return change


async def cancel_email_change(
    db: AsyncSession, user_id: UUID, change_id: UUID, *, now: datetime | None = None
) -> str:
    """Cancel a pending change; anything already finished is reported as it really is."""
    now = now or now_utc()
    user = await lock_user(db, user_id)
    if user is None:
        raise SessionAuthError(401, "session_revoked")
    change = await _owned_change(db, user.id, change_id, lock=True)
    state = await _settle(db, change, user, now)
    if state == "confirmed":
        raise CredentialError(409, "email_change_completed")
    if state == "pending":
        change.state = "cancelled"
        change.finished_at = now
        await invalidate_change_tokens(db, change.id, now=now)
        await db.flush()
        return "cancelled"
    return state


async def confirm_email_change(
    db: AsyncSession, token: str, *, now: datetime | None = None
) -> None:
    """Switch the address, mark it proven and sign out every session of the account."""
    owner_id = await find_token_owner(db, token, CHANGE_EMAIL)
    now = now or now_utc()
    user = await lock_user(db, owner_id)
    if user is None:
        raise ActionTokenError(400, "action_token_invalid")
    await revoke_user_sessions(db, user.id, "email_changed", now=now)
    change_id = (
        await db.execute(
            select(AccountActionToken.email_change_id).where(
                AccountActionToken.token_hash == action_token_hash(token)
            )
        )
    ).scalar_one_or_none()
    change = (
        None
        if change_id is None
        else (
            await db.execute(
                select(AccountEmailChange)
                .where(AccountEmailChange.id == change_id, AccountEmailChange.user_id == user.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
    )
    if change is None:
        raise ActionTokenError(400, "action_token_invalid")
    await consume_action_token(db, user, token, CHANGE_EMAIL, now=now)
    state = effective_state(change, user, now)
    if state == "expired":
        raise ActionTokenError(410, "action_token_expired")
    if state != "pending":
        raise ActionTokenError(400, "action_token_invalid")
    old_email = user.email
    try:
        async with db.begin_nested():
            user.email = change.new_email
            await db.flush()
    except IntegrityError:
        raise ActionTokenError(409, "email_unavailable") from None
    user.email_revision += 1
    user.email_verified_at = now
    change.state = "confirmed"
    change.finished_at = now
    if change.mode == "change":
        locale = await profile_locale(db, user.id) or ""
        await queue_account_mail(
            db,
            user,
            DONE_KIND,
            render_email_change_done(locale),
            expires_at=now + NOTICE_TTL,
            now=now,
            to=old_email,
        )
    await db.flush()

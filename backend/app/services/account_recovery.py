"""Password reset by e-mail and password change (E-001/F-004/T-002).

Helpers run in the caller's transaction and never commit; the caller commits and then
wakes the mail worker. Expensive hashing happens before any row lock. Lock order:
user -> sessions -> action token -> outbox.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.passwords import hash_new_password, password_error, verify_current_password
from app.core.security import now_utc
from app.models import LanguageProfile, MailOutbox, User
from app.services.action_tokens import (
    RESET_PASSWORD,
    TOKEN_TTL,
    ActionTokenError,
    consume_action_token,
    find_token_owner,
    issue_action_token,
)
from app.services.auth_sessions import (
    IssuedSession,
    lock_user,
    renew_session,
    revoke_user_sessions,
)
from app.services.mail_outbox import compose_mail, enqueue_mail
from app.services.mail_templates import (
    RenderedMail,
    render_password_changed,
    render_reset_password,
)

PASSWORD_CHANGED = "password_changed"
RESET_PATH = "/account/reset-password"
# Per-recipient limits; IP and global budgets come with the shared limiter (T-003).
MAIL_COOLDOWN = timedelta(seconds=60)
MAIL_WINDOW = timedelta(minutes=60)
MAIL_MAX_PER_WINDOW = 3
NOTICE_TTL = timedelta(hours=24)
RETRY_AFTER_SECONDS = int(MAIL_COOLDOWN.total_seconds())
_LOCAL_ORIGIN = "http://localhost:8000"


class CredentialError(Exception):
    """Maps to the API error `code` with `status_code`; nothing was changed."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


def account_link(path: str, token: str) -> str:
    """Link under the configured public origin; the token stays in the fragment."""
    origin = get_settings().public_app_origin.strip().rstrip("/") or _LOCAL_ORIGIN
    return f"{origin}{path}#token={token}"


async def profile_locale(db: AsyncSession, user_id: UUID) -> str | None:
    """App language of the active (or most recently used) profile."""
    return (
        await db.execute(
            select(LanguageProfile.app_lang)
            .where(LanguageProfile.user_id == user_id)
            .order_by(
                LanguageProfile.is_active.desc(),
                LanguageProfile.last_used_at.desc().nulls_last(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def next_mail_allowed_at(
    db: AsyncSession, user_id: UUID, kind: str, now: datetime
) -> datetime | None:
    """When the next mail of `kind` may be queued for this user; None means now."""
    times = sorted(
        (
            await db.execute(
                select(MailOutbox.created_at).where(
                    MailOutbox.user_id == user_id,
                    MailOutbox.kind == kind,
                    MailOutbox.created_at > now - MAIL_WINDOW,
                )
            )
        ).scalars()
    )
    candidates = []
    if times and now - times[-1] < MAIL_COOLDOWN:
        candidates.append(times[-1] + MAIL_COOLDOWN)
    if len(times) >= MAIL_MAX_PER_WINDOW:
        candidates.append(times[-MAIL_MAX_PER_WINDOW] + MAIL_WINDOW)
    return max(candidates) if candidates else None


async def _queue(
    db: AsyncSession,
    user: User,
    kind: str,
    rendered: RenderedMail,
    *,
    expires_at: datetime,
    now: datetime,
    action_token_id: UUID | None = None,
) -> None:
    mail = compose_mail(
        to=user.email,
        subject=rendered.subject,
        text=rendered.text,
        html=rendered.html,
        locale=rendered.locale,
        template=rendered.template,
    )
    await enqueue_mail(
        db,
        kind=kind,
        mail=mail,
        expires_at=expires_at,
        user_id=user.id,
        action_token_id=action_token_id,
        now=now,
    )


async def _queue_password_changed(db: AsyncSession, user: User, now: datetime) -> None:
    rendered = render_password_changed(await profile_locale(db, user.id) or "")
    await _queue(db, user, PASSWORD_CHANGED, rendered, expires_at=now + NOTICE_TTL, now=now)


async def request_password_reset(
    db: AsyncSession, email: str, locale: str | None, *, now: datetime | None = None
) -> bool:
    """Queue a reset link when allowed. The caller answers the same way either way.

    Returns whether a mail was queued (only for waking the worker, never for the client).
    Unknown and Google-only addresses get nothing: no fake reset, no password for them.
    """
    now = now or now_utc()
    user_id = (
        await db.execute(
            select(User.id).where(User.email == email.lower(), User.password_hash.is_not(None))
        )
    ).scalar_one_or_none()
    if user_id is None:
        return False
    user = await lock_user(db, user_id)
    if user is None or not user.password_hash:
        return False
    if await next_mail_allowed_at(db, user.id, RESET_PASSWORD, now) is not None:
        return False
    issued = await issue_action_token(db, user, RESET_PASSWORD, now=now)
    minutes = int(TOKEN_TTL[RESET_PASSWORD].total_seconds() // 60)
    rendered = render_reset_password(
        locale or await profile_locale(db, user.id) or "",
        account_link(RESET_PATH, issued.token),
        minutes=minutes,
    )
    await _queue(
        db,
        user,
        RESET_PASSWORD,
        rendered,
        expires_at=issued.row.expires_at,
        now=now,
        action_token_id=issued.row.id,
    )
    return True


def _check_new_password(password: str) -> None:
    code = password_error(password, new=True)
    if code is not None:
        raise CredentialError(422, code.value)


async def confirm_password_reset(
    db: AsyncSession, token: str, new_password: str, *, now: datetime | None = None
) -> None:
    """Set the new password, prove the current address and sign out every session."""
    _check_new_password(new_password)
    owner_id = await find_token_owner(db, token, RESET_PASSWORD)
    new_hash = await hash_new_password(new_password)
    now = now or now_utc()
    user = await lock_user(db, owner_id)
    if user is None or not user.password_hash:
        raise ActionTokenError(400, "action_token_invalid")
    await revoke_user_sessions(db, user.id, "password_reset", now=now)
    await consume_action_token(db, user, token, RESET_PASSWORD, now=now)
    user.password_hash = new_hash
    user.credentials_revision += 1
    if user.email_verified_at is None:
        # The link reached the current address, which proves the mailbox.
        user.email_verified_at = now
    await _queue_password_changed(db, user, now)
    await db.flush()


async def change_password(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    current_password: str,
    new_password: str,
    *,
    now: datetime | None = None,
) -> IssuedSession:
    """Replace a known password; other sessions end and the caller's session is renewed."""
    stored_hash = user.password_hash
    if not stored_hash:
        raise CredentialError(403, "password_not_set")
    _check_new_password(new_password)
    if not await verify_current_password(current_password, stored_hash):
        raise CredentialError(403, "current_password_invalid")
    new_hash = await hash_new_password(new_password)
    now = now or now_utc()
    locked = await lock_user(db, user.id)
    if locked is None or locked.password_hash != stored_hash:
        # Changed or reset meanwhile; the proof no longer matches the stored password.
        raise CredentialError(403, "current_password_invalid")
    await revoke_user_sessions(
        db, locked.id, "password_change", keep_session_id=session_id, now=now
    )
    issued = await renew_session(db, locked.id, session_id, now=now)
    locked.password_hash = new_hash
    locked.credentials_revision += 1
    await _queue_password_changed(db, locked, now)
    await db.flush()
    return issued

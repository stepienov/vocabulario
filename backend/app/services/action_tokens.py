"""One-time e-mail link proofs (E-001/F-004/T-002).

Helpers never commit. A caller resolves the owner with `find_token_owner` (no locks),
then takes locks in the shared order user -> sessions -> action token -> outbox and
calls `consume_action_token`, which re-validates everything under the token row lock.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.models import ACTION_TOKEN_PURPOSES, AccountActionToken, User

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"
CHANGE_EMAIL = "change_email"
REQUEST_DELETION = "request_account_deletion"
CANCEL_DELETION = "cancel_account_deletion"

TOKEN_TTL: dict[str, timedelta] = {
    VERIFY_EMAIL: timedelta(hours=24),
    RESET_PASSWORD: timedelta(minutes=30),
    CHANGE_EMAIL: timedelta(hours=24),
    REQUEST_DELETION: timedelta(minutes=30),
    CANCEL_DELETION: timedelta(minutes=30),
}
DELETION_PURPOSES = frozenset({REQUEST_DELETION, CANCEL_DELETION})
# A reset, change or deletion proof must die once credentials change; e-mail verification must not.
_CREDENTIAL_BOUND = frozenset({RESET_PASSWORD, CHANGE_EMAIL}) | DELETION_PURPOSES
_MAX_TOKEN_CHARS = 128

assert set(TOKEN_TTL) == set(ACTION_TOKEN_PURPOSES)


class ActionTokenError(Exception):
    """Maps to the API error `code` with `status_code`; nothing was changed."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


def _invalid() -> ActionTokenError:
    return ActionTokenError(400, "action_token_invalid")


@dataclass(frozen=True)
class IssuedActionToken:
    token: str
    row: AccountActionToken


def action_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_action_token(
    db: AsyncSession,
    user: User,
    purpose: str,
    *,
    now: datetime | None = None,
    email_change_id: UUID | None = None,
    expires_at: datetime | None = None,
    proof_method: str | None = None,
    target_deletion_id: UUID | None = None,
) -> IssuedActionToken:
    """New link proof for the current address/credentials of an already locked user."""
    if purpose not in TOKEN_TTL:
        raise ValueError(f"unknown action token purpose: {purpose}")
    if (purpose in DELETION_PURPOSES) != (proof_method is not None):
        raise ValueError("deletion proofs need a proof method and nothing else does")
    now = now or now_utc()
    ends_at = now + TOKEN_TTL[purpose]
    token = secrets.token_urlsafe(32)
    row = AccountActionToken(
        user_id=user.id,
        email_change_id=email_change_id,
        purpose=purpose,
        token_hash=action_token_hash(token),
        email_revision=user.email_revision,
        credentials_revision=user.credentials_revision,
        proof_method=proof_method,
        lifecycle_revision=user.lifecycle_revision if proof_method else None,
        target_deletion_id=target_deletion_id,
        created_at=now,
        expires_at=min(expires_at, ends_at) if expires_at else ends_at,
    )
    db.add(row)
    await db.flush()
    return IssuedActionToken(token=token, row=row)


async def invalidate_change_tokens(
    db: AsyncSession, change_id: UUID, *, now: datetime
) -> None:
    """Kill every unused link of one e-mail change; queued mails for them are dropped by the worker."""
    await db.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.email_change_id == change_id,
            AccountActionToken.consumed_at.is_(None),
            AccountActionToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )


def _usable_hash(token: str) -> str | None:
    value = token or ""
    if not value or len(value) > _MAX_TOKEN_CHARS:
        return None
    return action_token_hash(value)


async def find_token_owner(db: AsyncSession, token: str, purpose: str) -> UUID:
    """Owner of a token for lock ordering; never trusts an address or id from the client."""
    digest = _usable_hash(token)
    if digest is None:
        raise _invalid()
    row = (
        await db.execute(
            select(AccountActionToken.user_id, AccountActionToken.purpose).where(
                AccountActionToken.token_hash == digest
            )
        )
    ).one_or_none()
    if row is None or row.purpose != purpose:
        raise _invalid()
    return row.user_id


def _check(
    row: AccountActionToken | None, digest: str, user: User, purpose: str, now: datetime
) -> None:
    if row is None or row.user_id != user.id or row.purpose != purpose:
        raise _invalid()
    if not hmac.compare_digest(row.token_hash.encode("ascii"), digest.encode("ascii")):
        raise _invalid()
    if row.consumed_at is not None:
        raise ActionTokenError(409, "action_token_used")
    if row.invalidated_at is not None or row.email_revision != user.email_revision:
        raise _invalid()
    if purpose in _CREDENTIAL_BOUND and row.credentials_revision != user.credentials_revision:
        raise _invalid()
    if row.lifecycle_revision is not None and row.lifecycle_revision != user.lifecycle_revision:
        raise _invalid()
    if now >= row.expires_at:
        raise ActionTokenError(410, "action_token_expired")


async def peek_action_token(
    db: AsyncSession,
    user: User,
    token: str,
    purpose: str,
    *,
    now: datetime | None = None,
) -> AccountActionToken:
    """Validate a token exactly like `consume_action_token`, but leave it unused."""
    now = now or now_utc()
    digest = _usable_hash(token)
    if digest is None:
        raise _invalid()
    row = (
        await db.execute(
            select(AccountActionToken).where(AccountActionToken.token_hash == digest)
        )
    ).scalar_one_or_none()
    _check(row, digest, user, purpose, now)
    return row


async def consume_action_token(
    db: AsyncSession,
    user: User,
    token: str,
    purpose: str,
    *,
    now: datetime | None = None,
) -> AccountActionToken:
    """Mark a token used. `user` must already be locked (e.g. via auth_sessions.lock_user)."""
    now = now or now_utc()
    digest = _usable_hash(token)
    if digest is None:
        raise _invalid()
    row = (
        await db.execute(
            select(AccountActionToken)
            .where(AccountActionToken.token_hash == digest)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    _check(row, digest, user, purpose, now)
    row.consumed_at = now
    await db.flush()
    return row


async def action_token_is_current(
    db: AsyncSession, token_id: UUID, *, now: datetime | None = None
) -> bool:
    """Whether a queued link may still be sent: unused, unexpired and matching the user."""
    now = now or now_utc()
    row = (
        await db.execute(
            select(AccountActionToken, User)
            .join(User, User.id == AccountActionToken.user_id)
            .where(AccountActionToken.id == token_id)
        )
    ).one_or_none()
    if row is None:
        return False
    token, user = row
    if token.consumed_at is not None or token.invalidated_at is not None:
        return False
    if now >= token.expires_at or token.email_revision != user.email_revision:
        return False
    if token.lifecycle_revision is not None and token.lifecycle_revision != user.lifecycle_revision:
        return False
    return not (
        token.purpose in _CREDENTIAL_BOUND
        and token.credentials_revision != user.credentials_revision
    )

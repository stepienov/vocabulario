"""One-use proof of a fresh identity check for sensitive account actions (E-001/F-004/T-004).

The proof is bound to the owner, the session and its version, one action and the account
revisions, and lives five minutes. Password proofs are issued here; the Google issuer
(F-005) calls `issue_recent_auth` after validating its own challenge. Helpers never commit
and expect the user row to be locked already.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.passwords import verify_current_password
from app.core.security import now_utc
from app.models import RECENT_AUTH_ACTIONS, AuthSession, RecentAuthProof, User
from app.services.account_errors import CredentialError
from app.services.auth_sessions import AccessContext, lock_user

RECENT_AUTH_TTL = timedelta(minutes=5)
PASSWORD_ACTIONS = frozenset({"change_email", "link_google"})
_MAX_TOKEN_CHARS = 128


def recent_auth_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _required() -> CredentialError:
    return CredentialError(403, "recent_auth_required")


async def issue_recent_auth(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    action: str,
    *,
    now: datetime | None = None,
) -> tuple[str, RecentAuthProof]:
    if action not in RECENT_AUTH_ACTIONS:
        raise ValueError(f"unknown recent-auth action: {action}")
    now = now or now_utc()
    token = secrets.token_urlsafe(32)
    row = RecentAuthProof(
        user_id=user.id,
        session_id=ctx.session_id,
        session_version=ctx.session_version,
        action=action,
        token_hash=recent_auth_hash(token),
        email_revision=user.email_revision,
        credentials_revision=user.credentials_revision,
        created_at=now,
        expires_at=now + RECENT_AUTH_TTL,
    )
    db.add(row)
    await db.flush()
    return token, row


async def issue_password_proof(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    action: str,
    password: str,
    *,
    now: datetime | None = None,
) -> tuple[str, RecentAuthProof]:
    """Check the current password (outside any lock), then issue the proof."""
    if action not in PASSWORD_ACTIONS:
        raise CredentialError(422, "recent_auth_action_invalid")
    stored_hash = user.password_hash
    if not stored_hash:
        raise CredentialError(403, "password_not_set")
    if not await verify_current_password(password, stored_hash):
        raise CredentialError(403, "current_password_invalid")
    locked = await lock_user(db, user.id)
    if locked is None or locked.password_hash != stored_hash:
        raise CredentialError(403, "current_password_invalid")
    return await issue_recent_auth(db, locked, ctx, action, now=now)


async def _valid_proof(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    token: str,
    action: str,
    now: datetime,
) -> RecentAuthProof:
    """Locked proof row that belongs to this owner, session, action and account state."""
    if not token or len(token) > _MAX_TOKEN_CHARS:
        raise _required()
    row = (
        await db.execute(
            select(RecentAuthProof)
            .where(RecentAuthProof.token_hash == recent_auth_hash(token))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if (
        row is None
        or row.user_id != user.id
        or row.action != action
        or row.session_id != ctx.session_id
        or row.session_version != ctx.session_version
    ):
        raise _required()
    if row.consumed_at is not None:
        raise CredentialError(409, "recent_auth_used")
    if (
        now >= row.expires_at
        or row.email_revision != user.email_revision
        or row.credentials_revision != user.credentials_revision
    ):
        raise _required()
    session = await _live_session(db, ctx.session_id)
    if session is None or session.version != ctx.session_version:
        raise _required()
    return row


async def check_recent_auth(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    token: str,
    action: str,
    *,
    now: datetime | None = None,
) -> RecentAuthProof:
    """Same checks as `consume_recent_auth`, but the proof stays usable."""
    return await _valid_proof(db, user, ctx, token, action, now or now_utc())


async def consume_recent_auth(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    token: str,
    action: str,
    *,
    now: datetime | None = None,
) -> None:
    """Spend the proof in the caller's transaction; any mismatch changes nothing."""
    now = now or now_utc()
    row = await _valid_proof(db, user, ctx, token, action, now)
    row.consumed_at = now
    await db.flush()


async def _live_session(db: AsyncSession, session_id: UUID) -> AuthSession | None:
    session = (
        await db.execute(
            select(AuthSession)
            .where(AuthSession.id == session_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    return session if session is not None and session.revoked_at is None else None

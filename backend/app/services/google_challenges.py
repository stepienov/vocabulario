"""One-use Google sign-in challenges (E-001/F-005/T-001).

A challenge carries the nonce the Android client must hand to Google. Only the SHA-256 of
the nonce is stored. Helpers run in the caller's transaction and never commit. Lock order of
the account flows: user -> sessions -> recent proof -> Google challenge -> email change ->
deletion process -> action tokens -> mail buckets -> outbox.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.models import GoogleChallenge, RecentAuthProof, User
from app.services.account_errors import CredentialError
from app.services.auth_sessions import AccessContext, lock_user
from app.services.google_identity import (
    GoogleIdentity,
    GoogleTokenInvalid,
    GoogleUnavailable,
    nonce_hash,
    verify_google_token,
)
from app.services.recent_auth import check_recent_auth, recent_auth_hash

CHALLENGE_TTL = timedelta(minutes=5)
RECENT_AUTH_GOOGLE_ACTIONS = frozenset({"change_email", "add_password"})


@dataclass(frozen=True)
class IssuedChallenge:
    id: UUID
    nonce: str
    expires_at: datetime


def invalid_challenge() -> CredentialError:
    return CredentialError(400, "auth_challenge_invalid")


def _issue(
    db: AsyncSession, *, purpose: str, now: datetime, expires_at: datetime, **fields
) -> IssuedChallenge:
    nonce = secrets.token_urlsafe(32)
    row = GoogleChallenge(
        id=uuid.uuid4(),
        nonce_hash=nonce_hash(nonce),
        purpose=purpose,
        created_at=now,
        expires_at=expires_at,
        **fields,
    )
    db.add(row)
    return IssuedChallenge(id=row.id, nonce=nonce, expires_at=expires_at)


async def issue_login_challenge(db: AsyncSession, *, now: datetime | None = None) -> IssuedChallenge:
    now = now or now_utc()
    challenge = _issue(db, purpose="login", now=now, expires_at=now + CHALLENGE_TTL)
    await db.flush()
    return challenge


async def issue_deletion_challenge(
    db: AsyncSession, action: str, *, now: datetime | None = None
) -> IssuedChallenge:
    """Public: ties a nonce to one deletion action; ownership is shown by the Google subject."""
    now = now or now_utc()
    challenge = _issue(
        db,
        purpose="account_deletion",
        action=action,
        now=now,
        expires_at=now + CHALLENGE_TTL,
    )
    await db.flush()
    return challenge



async def issue_link_challenge(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    proof_token: str,
    *,
    now: datetime | None = None,
) -> IssuedChallenge:
    """Needs a live password proof for `link_google`; the challenge never outlives it."""
    now = now or now_utc()
    locked = await _locked_owner(db, user)
    if locked.google_id:
        raise CredentialError(409, "google_method_already_present")
    proof: RecentAuthProof = await check_recent_auth(
        db, locked, ctx, proof_token, "link_google", now=now
    )
    challenge = _issue(
        db,
        purpose="link",
        now=now,
        expires_at=min(now + CHALLENGE_TTL, proof.expires_at),
        user_id=locked.id,
        session_id=ctx.session_id,
        session_version=ctx.session_version,
        email_revision=locked.email_revision,
        credentials_revision=locked.credentials_revision,
        proof_hash=recent_auth_hash(proof_token),
    )
    await db.flush()
    return challenge


async def issue_recent_auth_challenge(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    action: str,
    *,
    now: datetime | None = None,
) -> IssuedChallenge:
    now = now or now_utc()
    if action not in RECENT_AUTH_GOOGLE_ACTIONS:
        raise CredentialError(422, "recent_auth_action_invalid")
    locked = await _locked_owner(db, user)
    if not locked.google_id:
        raise CredentialError(403, "google_not_linked")
    if action == "add_password" and locked.password_hash:
        raise CredentialError(409, "password_already_set")
    challenge = _issue(
        db,
        purpose="recent_auth",
        action=action,
        now=now,
        expires_at=now + CHALLENGE_TTL,
        user_id=locked.id,
        session_id=ctx.session_id,
        session_version=ctx.session_version,
        email_revision=locked.email_revision,
        credentials_revision=locked.credentials_revision,
        expected_google_id=locked.google_id,
    )
    await db.flush()
    return challenge


async def _locked_owner(db: AsyncSession, user: User) -> User:
    locked = await lock_user(db, user.id)
    if locked is None or locked.account_status != "active":
        raise CredentialError(403, "account_deletion_pending")
    return locked


async def load_challenge(
    db: AsyncSession,
    challenge_id: UUID,
    purpose: str,
    *,
    ctx: AccessContext | None = None,
    user: User | None = None,
    now: datetime | None = None,
) -> GoogleChallenge:
    """Plain read before the slow signature check; the final claim re-checks under a lock."""
    now = now or now_utc()
    row = (
        await db.execute(
            select(GoogleChallenge)
            .where(GoogleChallenge.id == challenge_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is None or row.purpose != purpose:
        raise invalid_challenge()
    _check_owner(row, ctx, user)
    _check_usable(row, now)
    return row


def _check_owner(row: GoogleChallenge, ctx: AccessContext | None, user: User | None) -> None:
    if row.purpose in ("link", "recent_auth"):
        if (
            ctx is None
            or user is None
            or row.user_id != user.id
            or row.session_id != ctx.session_id
            or row.session_version != ctx.session_version
        ):
            raise invalid_challenge()
    elif row.user_id is not None:
        raise invalid_challenge()


def _check_usable(row: GoogleChallenge, now: datetime) -> None:
    if row.consumed_at is not None:
        raise CredentialError(409, "auth_challenge_used")
    if now >= row.expires_at:
        raise CredentialError(410, "auth_challenge_expired")


async def claim_challenge(
    db: AsyncSession,
    challenge_id: UUID,
    *,
    owner: User | None = None,
    now: datetime | None = None,
) -> GoogleChallenge:
    """Spend the challenge under a row lock; a second claim sees `consumed_at`."""
    now = now or now_utc()
    row = (
        await db.execute(
            select(GoogleChallenge)
            .where(GoogleChallenge.id == challenge_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is None:
        raise invalid_challenge()
    _check_usable(row, now)
    if owner is not None and (
        row.email_revision != owner.email_revision
        or row.credentials_revision != owner.credentials_revision
    ):
        raise invalid_challenge()
    row.consumed_at = now
    await db.flush()
    return row


async def verify_for_challenge(token: str, challenge: GoogleChallenge) -> GoogleIdentity:
    try:
        return await verify_google_token(token, challenge.nonce_hash)
    except GoogleTokenInvalid as exc:
        raise CredentialError(401, "invalid_google_token") from exc
    except GoogleUnavailable as exc:
        raise CredentialError(503, "google_temporarily_unavailable") from exc

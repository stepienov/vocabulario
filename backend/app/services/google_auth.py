"""Sign in, link and re-confirm with Google (E-001/F-005/T-001).

The Google subject (`sub`) is the only identity. An address never links or merges accounts.
Signature checks run before any lock; the challenge is spent in the same transaction that
creates the session or the proof. Helpers never commit; the caller commits and then wakes
the mail worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import now_utc
from app.models import RecentAuthProof, User, UserSettings
from app.services.account_errors import CredentialError
from app.services.account_recovery import (
    NOTICE_TTL,
    ensure_mail_available,
    profile_locale,
    queue_account_mail,
    queue_verification_mail,
)
from app.services.auth_sessions import (
    AccessContext,
    IssuedSession,
    SessionAuthError,
    create_session,
    lock_user,
    renew_session,
    revoke_user_sessions,
)
from app.services.google_challenges import (
    claim_challenge,
    load_challenge,
    verify_for_challenge,
)
from app.services.google_identity import GoogleIdentity
from app.services.mail_templates import render_google_linked
from app.services.recent_auth import consume_recent_auth, issue_recent_auth, recent_auth_hash

GOOGLE_LINKED = "google_linked"
MAX_EMAIL_CHARS = 320


@dataclass(frozen=True)
class GoogleLogin:
    issued: IssuedSession
    mail_queued: bool


def _conflict() -> CredentialError:
    return CredentialError(409, "google_sign_in_conflict")


def _pending() -> CredentialError:
    return CredentialError(403, "account_deletion_pending")


def _remember(user: User, identity: GoogleIdentity, now: datetime) -> None:
    """Keep the last address Google reported; a display hint, never the app address."""
    if identity.email and len(identity.email) <= MAX_EMAIL_CHARS:
        user.google_email = identity.email
        user.google_email_observed_at = now


def _confirm_address(user: User, identity: GoogleIdentity, now: datetime) -> None:
    """A Gmail/Workspace address Google verified may prove the current app address."""
    if (
        user.email_verified_at is None
        and identity.proves_address()
        and identity.email == user.email
    ):
        user.email_verified_at = now


async def _owner_of(db: AsyncSession, sub: str) -> User | None:
    return (await db.execute(select(User).where(User.google_id == sub))).scalar_one_or_none()


async def _existing_login(
    db: AsyncSession, user: User, identity: GoogleIdentity, challenge_id: UUID, now: datetime
) -> GoogleLogin:
    locked = await lock_user(db, user.id)
    if locked is None or locked.google_id != identity.sub:
        raise CredentialError(401, "invalid_google_token")
    if locked.account_status != "active":
        raise _pending()
    await claim_challenge(db, challenge_id, now=now)
    _remember(locked, identity, now)
    _confirm_address(locked, identity, now)
    issued = await create_session(db, locked.id, now=now)
    return GoogleLogin(issued, False)


async def google_login(
    db: AsyncSession,
    challenge_id: UUID,
    id_token: str,
    locale: str | None,
    *,
    now: datetime | None = None,
) -> GoogleLogin:
    now = now or now_utc()
    challenge = await load_challenge(db, challenge_id, "login", now=now)
    identity = await verify_for_challenge(id_token, challenge)
    known = await _owner_of(db, identity.sub)
    if known is not None:
        return await _existing_login(db, known, identity, challenge_id, now)
    if not identity.email or len(identity.email) > MAX_EMAIL_CHARS:
        raise CredentialError(401, "invalid_google_token")
    taken = (
        await db.execute(select(User.id).where(User.email == identity.email))
    ).scalar_one_or_none()
    if taken is not None:
        raise _conflict()
    proven = identity.proves_address()
    if not proven:
        await ensure_mail_available()
    user = User(
        email=identity.email,
        google_id=identity.sub,
        email_verified_at=now if proven else None,
    )
    _remember(user, identity, now)
    try:
        async with db.begin_nested():
            db.add(user)
            await db.flush()
    except IntegrityError as exc:
        # A parallel request won: decide again on the concrete conflict, not on "any error".
        detail = str(exc.orig)
        if "google_id" in detail:
            winner = await _owner_of(db, identity.sub)
            if winner is not None:
                return await _existing_login(db, winner, identity, challenge_id, now)
        if "email" in detail:
            raise _conflict() from exc
        raise
    db.add(UserSettings(user_id=user.id))
    await claim_challenge(db, challenge_id, now=now)
    issued = await create_session(db, user.id, now=now)
    if not proven:
        locked = await lock_user(db, user.id)
        await queue_verification_mail(db, locked, locale, now=now)
    return GoogleLogin(issued, not proven)


async def link_google(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    challenge_id: UUID,
    id_token: str,
    proof_token: str,
    *,
    now: datetime | None = None,
) -> IssuedSession:
    """Add Google to the signed-in account; other sessions end, the caller's renews."""
    now = now or now_utc()
    challenge = await load_challenge(db, challenge_id, "link", ctx=ctx, user=user, now=now)
    if challenge.proof_hash != recent_auth_hash(proof_token):
        raise CredentialError(400, "auth_challenge_invalid")
    identity = await verify_for_challenge(id_token, challenge)
    locked = await lock_user(db, user.id)
    if locked is None:
        raise SessionAuthError(401, "session_revoked")
    if locked.account_status != "active":
        raise _pending()
    if locked.google_id == identity.sub:
        raise CredentialError(409, "google_already_linked")
    if locked.google_id:
        raise CredentialError(409, "google_method_already_present")
    if await _owner_of(db, identity.sub) is not None:
        raise CredentialError(409, "google_link_unavailable")
    confirms = identity.proves_address() and identity.email == locked.email
    if locked.email_verified_at is None and not confirms:
        raise CredentialError(403, "email_verification_required")
    await revoke_user_sessions(db, locked.id, "google_linked", keep_session_id=ctx.session_id, now=now)
    await consume_recent_auth(db, locked, ctx, proof_token, "link_google", now=now)
    await claim_challenge(db, challenge_id, owner=locked, now=now)
    issued = await renew_session(db, locked.id, ctx.session_id, now=now)
    locked.google_id = identity.sub
    locked.credentials_revision += 1
    _remember(locked, identity, now)
    _confirm_address(locked, identity, now)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        if "google_id" in str(exc.orig):
            raise CredentialError(409, "google_link_unavailable") from exc
        raise
    rendered = render_google_linked(await profile_locale(db, locked.id) or "")
    await queue_account_mail(
        db, locked, GOOGLE_LINKED, rendered, expires_at=now + NOTICE_TTL, now=now
    )
    return issued


async def recent_auth_google(
    db: AsyncSession,
    user: User,
    ctx: AccessContext,
    challenge_id: UUID,
    id_token: str,
    action: str,
    *,
    now: datetime | None = None,
) -> tuple[str, RecentAuthProof]:
    """Fresh Google proof for `change_email` or `add_password`; only the linked subject counts."""
    now = now or now_utc()
    challenge = await load_challenge(db, challenge_id, "recent_auth", ctx=ctx, user=user, now=now)
    if challenge.action != action:
        raise CredentialError(400, "auth_challenge_invalid")
    identity = await verify_for_challenge(id_token, challenge)
    if identity.sub != challenge.expected_google_id:
        raise CredentialError(403, "google_account_mismatch")
    locked = await lock_user(db, user.id)
    if locked is None:
        raise SessionAuthError(401, "session_revoked")
    if locked.account_status != "active":
        raise _pending()
    if locked.google_id != identity.sub:
        raise CredentialError(403, "google_account_mismatch")
    if action == "add_password" and locked.password_hash:
        raise CredentialError(409, "password_already_set")
    await claim_challenge(db, challenge_id, owner=locked, now=now)
    _remember(locked, identity, now)
    _confirm_address(locked, identity, now)
    return await issue_recent_auth(db, locked, ctx, action, now=now)

"""Revocable server sessions (E-001/F-003/T-001).

Helpers work on the caller's AsyncSession and never commit. Lock order is
always: user row -> its sessions by id -> their refresh retry rows.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    ACCESS,
    REFRESH,
    TokenClaims,
    TokenError,
    TokenPair,
    issue_access_token,
    issue_token_pair,
    now_utc,
    read_token,
)
from app.models import AuthRefreshRetry, AuthSession, User

logger = logging.getLogger(__name__)

RETRY_WINDOW = timedelta(minutes=5)


class SessionAuthError(Exception):
    """Maps to an API error. `commit` means the caller must persist a revocation first."""

    def __init__(self, status_code: int, code: str, *, commit: bool = False) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.commit = commit


class RetryRecordError(RuntimeError):
    """Stored retry result cannot be decrypted or no longer matches the session."""


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    refresh_token: str
    user_id: UUID
    session_id: UUID
    access_expires_at: datetime

    def expires_in(self, now: datetime | None = None) -> int:
        remaining = (self.access_expires_at - (now or now_utc())).total_seconds()
        return max(0, int(remaining))


@dataclass(frozen=True)
class AccessContext:
    user_id: UUID
    session_id: UUID
    session_version: int


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _same_hash(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("ascii"), right.encode("ascii"))


@lru_cache
def _ephemeral_key() -> bytes:
    return Fernet.generate_key()


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.auth_refresh_retry_key.strip()
    if key:
        return Fernet(key.encode("ascii"))
    if settings.is_deployed:
        raise RetryRecordError("auth_refresh_retry_key is not configured")
    # Local only: retry results die with the process, which is acceptable for dev/tests.
    return Fernet(_ephemeral_key())


def _issued(pair: TokenPair) -> IssuedSession:
    if pair.access.expires_at is None:
        raise ValueError("access token must expire")
    return IssuedSession(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        user_id=pair.access.user_id,
        session_id=pair.access.session_id,
        access_expires_at=pair.access.expires_at,
    )


def _token_error(exc: TokenError, *, refresh: bool) -> SessionAuthError:
    if exc.reason == "legacy":
        return SessionAuthError(401, "session_upgrade_required")
    if exc.reason == "expired" and refresh:
        return SessionAuthError(401, "session_expired")
    return SessionAuthError(401, "invalid_refresh_token" if refresh else "invalid_token")


async def lock_user(db: AsyncSession, user_id: UUID) -> User | None:
    """Lock and re-read the user row; flush pending changes to it first."""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _lock_session(db: AsyncSession, session_id: UUID) -> AuthSession | None:
    result = await db.execute(
        select(AuthSession).where(AuthSession.id == session_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def _delete_retries(db: AsyncSession, session_ids: list[UUID]) -> None:
    if session_ids:
        await db.execute(
            delete(AuthRefreshRetry).where(AuthRefreshRetry.session_id.in_(session_ids))
        )


async def create_session(
    db: AsyncSession, user_id: UUID, *, now: datetime | None = None
) -> IssuedSession:
    """New session for an already authenticated and locked user."""
    now = now or now_utc()
    session_id = uuid4()
    pair = issue_token_pair(user_id, session_id, 1, now)
    db.add(
        AuthSession(
            id=session_id,
            user_id=user_id,
            version=1,
            refresh_token_hash=token_hash(pair.refresh_token),
            created_at=now,
            refreshed_at=now,
            expires_at=pair.refresh.expires_at,
        )
    )
    await db.flush()
    return _issued(pair)


def _revoke(session: AuthSession, reason: str, now: datetime) -> None:
    if session.revoked_at is None:
        session.revoked_at = now
        session.revocation_reason = reason


async def revoke_user_sessions(
    db: AsyncSession,
    user_id: UUID,
    reason: str,
    *,
    keep_session_id: UUID | None = None,
    now: datetime | None = None,
) -> int:
    """Revoke all active sessions of a locked user, optionally except the current one."""
    now = now or now_utc()
    result = await db.execute(
        select(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .order_by(AuthSession.id)
        .with_for_update()
    )
    revoked = [s for s in result.scalars() if s.id != keep_session_id]
    for session in revoked:
        _revoke(session, reason, now)
    await _delete_retries(db, [s.id for s in revoked])
    await db.flush()
    return len(revoked)


async def renew_session(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, now: datetime | None = None
) -> IssuedSession:
    """Bump the version of the caller's own session after a security change.

    Old access and refresh tokens of that session stop working; its retry rows go away.
    The session id must come from the verified request context, never from client JSON.
    """
    now = now or now_utc()
    session = await _lock_session(db, session_id)
    if session is None or session.user_id != user_id or session.revoked_at is not None:
        raise SessionAuthError(401, "session_revoked")
    session.version += 1
    pair = issue_token_pair(user_id, session.id, session.version, now)
    session.refresh_token_hash = token_hash(pair.refresh_token)
    session.refreshed_at = now
    session.expires_at = pair.refresh.expires_at
    await _delete_retries(db, [session.id])
    await db.flush()
    return _issued(pair)


async def _locked_refresh_session(
    db: AsyncSession, claims: TokenClaims, now: datetime
) -> AuthSession:
    user = await lock_user(db, claims.user_id)
    session = await _lock_session(db, claims.session_id) if user is not None else None
    if session is None:
        raise SessionAuthError(401, "session_revoked")
    if session.user_id != claims.user_id:
        raise SessionAuthError(401, "invalid_refresh_token")
    if session.revoked_at is not None:
        raise SessionAuthError(401, "session_revoked")
    if session.expires_at is not None and session.expires_at <= now:
        raise SessionAuthError(401, "session_expired")
    if session.version != claims.session_version:
        raise SessionAuthError(401, "invalid_refresh_token")
    return session


def _replayed_result(
    row: AuthRefreshRetry, session: AuthSession, now: datetime
) -> IssuedSession:
    try:
        data = json.loads(_fernet().decrypt(row.response_ciphertext))
        access = read_token(data["access_token"], ACCESS, now=row.created_at)
        refresh = read_token(
            data["refresh_token"], REFRESH, now=now, allow_expired_refresh=True
        )
    except (InvalidToken, TokenError, ValueError, KeyError, TypeError) as exc:
        raise RetryRecordError("refresh retry record is unreadable") from exc
    for claims in (access, refresh):
        if (
            claims.user_id != session.user_id
            or claims.session_id != session.id
            or claims.session_version != session.version
        ):
            raise RetryRecordError("refresh retry record does not match its session")
    if not _same_hash(token_hash(data["refresh_token"]), row.output_token_hash):
        raise RetryRecordError("refresh retry record does not match its hash")
    if access.expires_at is None:
        raise RetryRecordError("refresh retry access token has no expiry")
    access_token = data["access_token"]
    if access.expires_at <= now:
        access_token, access = issue_access_token(
            session.user_id, session.id, session.version, now
        )
        if access.expires_at is None:
            raise RetryRecordError("new access token has no expiry")
    return IssuedSession(
        access_token=access_token,
        refresh_token=data["refresh_token"],
        user_id=session.user_id,
        session_id=session.id,
        access_expires_at=access.expires_at,
    )


async def _rotate(
    db: AsyncSession,
    session: AuthSession,
    request_id: UUID,
    input_hash: str,
    now: datetime,
) -> IssuedSession:
    await db.execute(
        delete(AuthRefreshRetry).where(
            AuthRefreshRetry.session_id == session.id,
            AuthRefreshRetry.expires_at <= now,
        )
    )
    pair = issue_token_pair(session.user_id, session.id, session.version, now)
    output_hash = token_hash(pair.refresh_token)
    session.refresh_token_hash = output_hash
    session.refreshed_at = now
    session.expires_at = pair.refresh.expires_at
    payload = json.dumps(
        {"access_token": pair.access_token, "refresh_token": pair.refresh_token}
    ).encode("utf-8")
    db.add(
        AuthRefreshRetry(
            session_id=session.id,
            request_id=request_id,
            session_version=session.version,
            input_token_hash=input_hash,
            output_token_hash=output_hash,
            response_ciphertext=_fernet().encrypt(payload),
            created_at=now,
            expires_at=min(now + RETRY_WINDOW, _issued(pair).access_expires_at),
        )
    )
    await db.flush()
    return _issued(pair)


async def _revoke_replayed(
    db: AsyncSession, session: AuthSession, now: datetime
) -> SessionAuthError:
    _revoke(session, "refresh_reuse", now)
    await _delete_retries(db, [session.id])
    await db.flush()
    logger.warning("auth refresh token reuse; session revoked (session_id=%s)", session.id)
    return SessionAuthError(401, "session_revoked", commit=True)


async def refresh_session(
    db: AsyncSession,
    refresh_token: str,
    request_id: UUID,
    *,
    now: datetime | None = None,
) -> IssuedSession:
    """Rotate one session or recover its still-current result for the same request id.

    Raises SessionAuthError; when `commit` is set the caller commits the revocation
    before answering. On success the caller commits before returning tokens.
    """
    now = now or now_utc()
    try:
        claims = read_token(refresh_token, REFRESH, now=now, allow_expired_refresh=True)
    except TokenError as exc:
        raise _token_error(exc, refresh=True) from exc
    session = await _locked_refresh_session(db, claims, now)
    input_hash = token_hash(refresh_token)
    row = (
        await db.execute(
            select(AuthRefreshRetry)
            .where(
                AuthRefreshRetry.session_id == session.id,
                AuthRefreshRetry.request_id == request_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is not None:
        if not _same_hash(row.input_token_hash, input_hash):
            raise SessionAuthError(409, "refresh_conflict")
        if row.session_version != session.version or not _same_hash(
            row.output_token_hash, session.refresh_token_hash
        ):
            raise SessionAuthError(409, "refresh_conflict")
        return _replayed_result(row, session, now)
    if _same_hash(input_hash, session.refresh_token_hash):
        return await _rotate(db, session, request_id, input_hash, now)
    recently_used = (
        await db.execute(
            select(AuthRefreshRetry.request_id)
            .where(
                AuthRefreshRetry.session_id == session.id,
                AuthRefreshRetry.input_token_hash == input_hash,
                AuthRefreshRetry.expires_at > now,
            )
            .limit(1)
        )
    ).first()
    if recently_used is not None:
        raise SessionAuthError(409, "refresh_conflict")
    raise await _revoke_replayed(db, session, now)


async def logout_session(
    db: AsyncSession, refresh_token: str, *, now: datetime | None = None
) -> None:
    """Revoke only the session proven by its current refresh token; repeat is a no-op."""
    now = now or now_utc()
    try:
        claims = read_token(refresh_token, REFRESH, now=now, allow_expired_refresh=True)
    except TokenError as exc:
        raise _token_error(exc, refresh=True) from exc
    user = await lock_user(db, claims.user_id)
    session = await _lock_session(db, claims.session_id) if user is not None else None
    if session is None or session.revoked_at is not None:
        return
    if (
        session.user_id != claims.user_id
        or session.version != claims.session_version
        or (session.expires_at is not None and session.expires_at <= now)
        or not _same_hash(token_hash(refresh_token), session.refresh_token_hash)
    ):
        raise SessionAuthError(401, "invalid_refresh_token")
    _revoke(session, "logout", now)
    await _delete_retries(db, [session.id])
    await db.flush()


def access_claims(token: str, *, now: datetime | None = None) -> TokenClaims:
    try:
        return read_token(token, ACCESS, now=now)
    except TokenError as exc:
        raise _token_error(exc, refresh=False) from exc


def check_access_session(
    claims: TokenClaims, session: AuthSession | None, now: datetime | None = None
) -> AccessContext:
    """Every protected request: the access token must match a live session row."""
    now = now or now_utc()
    if session is None:
        raise SessionAuthError(401, "session_revoked")
    if session.user_id != claims.user_id:
        raise SessionAuthError(401, "invalid_token")
    if session.revoked_at is not None:
        raise SessionAuthError(401, "session_revoked")
    if session.expires_at is not None and session.expires_at <= now:
        raise SessionAuthError(401, "session_expired")
    if session.version != claims.session_version:
        raise SessionAuthError(401, "invalid_token")
    return AccessContext(
        user_id=session.user_id,
        session_id=session.id,
        session_version=session.version,
    )

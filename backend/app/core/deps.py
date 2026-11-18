import re
import unicodedata
from uuid import UUID

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.http_errors import api_error
from app.core.security import TokenClaims
from app.db.session import get_db
from app.models import AuthSession, User
from app.services.auth_sessions import (
    AccessContext,
    SessionAuthError,
    access_claims,
    check_access_session,
)

security = HTTPBearer(auto_error=False)


def _claims(credentials: HTTPAuthorizationCredentials | None) -> TokenClaims:
    if credentials is None:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "not_authenticated", "Not authenticated")
    try:
        return access_claims(credentials.credentials)
    except SessionAuthError as exc:
        raise api_error(exc.status_code, exc.code) from exc


def _context(request: Request, claims: TokenClaims, session: AuthSession | None) -> AccessContext:
    try:
        context = check_access_session(claims, session)
    except SessionAuthError as exc:
        raise api_error(exc.status_code, exc.code) from exc
    request.state.auth_context = context
    return context


async def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UUID:
    """Session check in a short own DB session, so long handlers do not hold a connection."""
    claims = _claims(credentials)
    cached: AccessContext | None = getattr(request.state, "auth_context", None)
    if cached is not None and cached.session_id == claims.session_id:
        return cached.user_id
    from app.db import session as db_session

    async with db_session.async_session_factory() as db:
        row = (
            await db.execute(
                select(AuthSession, User.email_verified_at)
                .join(User, User.id == AuthSession.user_id)
                .where(AuthSession.id == claims.session_id)
            )
        ).first()
    session, verified_at = row if row is not None else (None, None)
    context = _context(request, claims, session)
    request.state.email_verified = verified_at is not None
    return context.user_id


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """One joined read of the live session and its user per request."""
    claims = _claims(credentials)
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.id == claims.session_id)
        )
    ).first()
    session, user = row if row is not None else (None, None)
    _context(request, claims, session)
    request.state.email_verified = user.email_verified_at is not None
    return user


def _require_verified(request: Request) -> None:
    if get_settings().email_verification_gate and not request.state.email_verified:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "email_verification_required",
            "Confirm your e-mail address first",
        )


async def get_verified_user(request: Request, user: User = Depends(get_current_user)) -> User:
    """Learning API: a live session and, while the gate is on, a proven address."""
    _require_verified(request)
    return user


async def get_verified_user_id(
    request: Request, user_id: UUID = Depends(get_current_user_id)
) -> UUID:
    _require_verified(request)
    return user_id


async def get_admin_user(user: User = Depends(get_verified_user)) -> User:
    if (user.role or "").strip().lower() != "admin":
        raise api_error(status.HTTP_403_FORBIDDEN, "forbidden", "Admin only")
    return user


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return unicodedata.normalize("NFC", text)


def lang_pair_key(native: str, learning: str) -> str:
    return f"{native}>{learning}"

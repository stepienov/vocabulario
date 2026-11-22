"""Maps a dead session to the lifecycle answer (E-001/F-006/T-002).

Only a validly signed token plus matching server state may say "deletion pending" or
"deleted"; anything else stays a plain auth rejection and never tells a client to wipe data.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AccountDeletion, AuthSession, User


async def lifecycle_override(
    db: AsyncSession, user_id: UUID, session_id: UUID | None
) -> tuple[int, str] | None:
    """(status, code) for a signed token of a pending or erased account, else None."""
    user = await db.get(User, user_id)
    if user is not None:
        if user.account_status == "active" or session_id is None:
            return None
        session = (
            await db.execute(
                select(AuthSession.user_id, AuthSession.revocation_reason).where(
                    AuthSession.id == session_id
                )
            )
        ).one_or_none()
        if session and session.user_id == user_id and session.revocation_reason == "account_deleted":
            return 403, "account_deletion_pending"
        return None
    settings = get_settings()
    if not settings.erasure_key_ready():
        return None
    from app.services.account_deletion import subject_hmac

    digest, _version = subject_hmac(user_id)
    marker = (
        await db.execute(
            select(AccountDeletion.id).where(
                AccountDeletion.state == "completed", AccountDeletion.subject_hmac == digest
            )
        )
    ).first()
    return (401, "account_deleted") if marker is not None else None

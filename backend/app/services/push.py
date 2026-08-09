"""Push notification helpers (FCM when configured; otherwise no-op)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import DeviceToken, UserSettings

logger = logging.getLogger(__name__)


async def _user_tokens(db: AsyncSession, user_id: UUID) -> list[str]:
    result = await db.execute(
        select(DeviceToken.token).where(DeviceToken.user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def _cards_ready_enabled(db: AsyncSession, user_id: UUID) -> bool:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    return settings is None or settings.cards_ready_push_enabled


async def send_push_to_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    title: str,
    body: str,
    data_type: str,
    card_id: UUID | None = None,
) -> None:
    settings = get_settings()
    if not settings.fcm_server_key:
        logger.info("FCM not configured; skip push %s for user %s", data_type, user_id)
        return
    tokens = await _user_tokens(db, user_id)
    if not tokens:
        return
    # MVP: log intent; wire httpx to FCM legacy API when key is set in production.
    logger.info(
        "FCM push [%s] user=%s tokens=%d title=%r body=%r card=%s",
        data_type,
        user_id,
        len(tokens),
        title,
        body,
        card_id,
    )


async def notify_cards_ready(db: AsyncSession, user_id: UUID, count: int = 1) -> None:
    if not await _cards_ready_enabled(db, user_id):
        return
    await send_push_to_user(
        db,
        user_id,
        title="Cards ready",
        body=f"{count} word(s) ready to study",
        data_type="cards_ready",
    )


async def notify_correction_resolved(
    db: AsyncSession,
    user_id: UUID,
    card_id: UUID,
    status: str,
) -> None:
    if not await _cards_ready_enabled(db, user_id):
        return
    body = "Report accepted — card updated" if status == "accepted" else "Report reviewed"
    await send_push_to_user(
        db,
        user_id,
        title="Correction reviewed",
        body=body,
        data_type="correction_resolved",
        card_id=card_id,
    )

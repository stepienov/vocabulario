"""Device token registration for push notifications."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import DeviceToken, User
from app.schemas import DeviceRegisterRequest

router = APIRouter(tags=["devices"])


@router.post("/devices/register", status_code=204)
async def register_device(
    body: DeviceRegisterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.get(DeviceToken, body.token)
    now = datetime.now(UTC)
    if existing is not None:
        existing.user_id = user.id
        existing.platform = body.platform
        existing.updated_at = now
    else:
        db.add(
            DeviceToken(
                token=body.token,
                user_id=user.id,
                platform=body.platform,
                updated_at=now,
            )
        )
    await db.commit()


@router.delete("/devices/{token}", status_code=204)
async def unregister_device(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(row)
    await db.commit()

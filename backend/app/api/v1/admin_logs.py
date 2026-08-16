from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_admin_user
from app.db.session import get_db
from app.models import AppLog, User
from app.schemas import AppLogResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/logs", response_model=list[AppLogResponse])
async def list_app_logs(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
    level: str | None = Query(None),
    category: str | None = Query(None),
    event: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(AppLog).order_by(AppLog.created_at.desc()).limit(limit)
    if level:
        stmt = stmt.where(AppLog.level == level)
    if category:
        stmt = stmt.where(AppLog.category == category)
    if event:
        stmt = stmt.where(AppLog.event == event)
    if status:
        stmt = stmt.where(AppLog.status == status)
    rows = list((await db.execute(stmt)).scalars().all())
    return rows

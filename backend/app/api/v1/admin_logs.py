from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_admin_user
from app.db.session import get_db
from app.models import AppLog, LlmUsage, User
from app.schemas import AppLogResponse, LlmUsageListResponse

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


@router.get("/llm-usage", response_model=LlmUsageListResponse)
async def list_llm_usage(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
    lemma: str | None = Query(None),
    purpose: str | None = Query(None),
    operation_kind: str | None = Query(None),
    lang_pair: str | None = Query(None),
    query: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    filters = []
    if lemma:
        filters.append(LlmUsage.lemma == lemma)
    if purpose:
        filters.append(LlmUsage.purpose == purpose)
    if operation_kind:
        filters.append(LlmUsage.operation_kind == operation_kind)
    if lang_pair:
        filters.append(LlmUsage.lang_pair == lang_pair)
    if query:
        filters.append(LlmUsage.query == query)

    list_stmt = select(LlmUsage).order_by(LlmUsage.created_at.desc()).limit(limit)
    totals_stmt = select(
        func.count(LlmUsage.id),
        func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
        func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
        func.coalesce(func.sum(LlmUsage.cached_tokens), 0),
        func.sum(LlmUsage.estimated_cost_usd),
    )
    if filters:
        list_stmt = list_stmt.where(*filters)
        totals_stmt = totals_stmt.where(*filters)

    rows = list((await db.execute(list_stmt)).scalars().all())
    totals = (await db.execute(totals_stmt)).one()
    cost = totals[4]
    return LlmUsageListResponse(
        items=rows,
        total_calls=int(totals[0] or 0),
        total_prompt_tokens=int(totals[1] or 0),
        total_completion_tokens=int(totals[2] or 0),
        total_cached_tokens=int(totals[3] or 0),
        total_estimated_cost_usd=float(cost) if cost is not None else None,
    )


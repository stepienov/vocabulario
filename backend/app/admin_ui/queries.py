from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import cast
from sqlalchemy.types import Date

from app.models import (
    AdminEscalation,
    AppLog,
    ImportJob,
    ImportJobEvent,
    ImportJobItem,
    LanguageProfile,
    LearningCard,
    LexicalEntry,
    LlmCallPayload,
    LlmUsage,
    LookupEvent,
    LookupQueryCache,
    ReviewLog,
    SrsState,
    User,
    UserSettings,
    WordList,
)
from app.services.card_jobs import STATUS_PENDING, spawn_enrich

PAGE_SIZE = 50


async def overview_kpis(db: AsyncSession) -> dict:
    now = datetime.now(UTC)
    h24 = now - timedelta(hours=24)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)
    live = LearningCard.deleted_at.is_(None)

    users_total = int((await db.execute(select(func.count(User.id)))).scalar_one() or 0)
    users_new_24h = int(
        (await db.execute(select(func.count(User.id)).where(User.created_at >= h24))).scalar_one() or 0
    )
    active_7d = int(
        (
            await db.execute(
                select(func.count(func.distinct(ReviewLog.user_id))).where(ReviewLog.reviewed_at >= d7)
            )
        ).scalar_one()
        or 0
    )
    cards_live = int((await db.execute(select(func.count(LearningCard.id)).where(live))).scalar_one() or 0)
    cards_deleted = int(
        (
            await db.execute(select(func.count(LearningCard.id)).where(LearningCard.deleted_at.is_not(None)))
        ).scalar_one()
        or 0
    )

    async def _status_count(*statuses: str) -> int:
        return int(
            (
                await db.execute(
                    select(func.count(LearningCard.id)).where(
                        live, LearningCard.enrichment_status.in_(statuses)
                    )
                )
            ).scalar_one()
            or 0
        )

    lists_total = int(
        (await db.execute(select(func.count(WordList.id)).where(WordList.deleted_at.is_(None)))).scalar_one()
        or 0
    )
    reviews_24h = int(
        (await db.execute(select(func.count(ReviewLog.id)).where(ReviewLog.reviewed_at >= h24))).scalar_one()
        or 0
    )
    lookups_24h = int(
        (await db.execute(select(func.count(LookupEvent.id)).where(LookupEvent.created_at >= h24))).scalar_one()
        or 0
    )
    errors_24h = int(
        (
            await db.execute(
                select(func.count(AppLog.id)).where(AppLog.created_at >= h24, AppLog.level == "error")
            )
        ).scalar_one()
        or 0
    )
    llm_errors_24h = int(
        (
            await db.execute(
                select(func.count(LlmUsage.id)).where(
                    LlmUsage.created_at >= h24, LlmUsage.status == "error"
                )
            )
        ).scalar_one()
        or 0
    )

    async def _cost_since(since: datetime | None):
        stmt = select(
            func.coalesce(func.sum(LlmUsage.estimated_cost_usd), 0),
            func.count(LlmUsage.id),
            func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LlmUsage.cached_tokens), 0),
        )
        if since is not None:
            stmt = stmt.where(LlmUsage.created_at >= since)
        row = (await db.execute(stmt)).one()
        cost = float(row[0] or 0)
        calls = int(row[1] or 0)
        prompt = int(row[2] or 0)
        cached = int(row[3] or 0)
        hit = (cached / prompt * 100) if prompt else 0.0
        return cost, calls, hit

    cost_24h, calls_24h, cache_24h = await _cost_since(h24)
    cost_7d, calls_7d, _ = await _cost_since(d7)
    cost_30d, calls_30d, _ = await _cost_since(d30)
    cost_all, calls_all, cache_all = await _cost_since(None)

    last_errors = (
        (
            await db.execute(
                select(AppLog)
                .where(AppLog.level.in_(["error", "warn"]))
                .order_by(AppLog.created_at.desc())
                .limit(8)
            )
        )
        .scalars()
        .all()
    )
    last_users = (
        (await db.execute(select(User).order_by(User.created_at.desc()).limit(8))).scalars().all()
    )
    expensive = (
        await db.execute(
            select(
                LlmUsage.operation_id,
                LlmUsage.lemma,
                LlmUsage.query,
                LlmUsage.operation_kind,
                func.sum(LlmUsage.estimated_cost_usd).label("usd"),
                func.count(LlmUsage.id).label("calls"),
            )
            .where(LlmUsage.created_at >= h24, LlmUsage.operation_id.is_not(None))
            .group_by(
                LlmUsage.operation_id,
                LlmUsage.lemma,
                LlmUsage.query,
                LlmUsage.operation_kind,
            )
            .order_by(desc("usd"))
            .limit(8)
        )
    ).all()

    return {
        "users_total": users_total,
        "users_new_24h": users_new_24h,
        "active_7d": active_7d,
        "cards_live": cards_live,
        "cards_deleted": cards_deleted,
        "enrich_ready": await _status_count("ready"),
        "enrich_pending": await _status_count("pending", "preparing"),
        "enrich_failed": await _status_count("failed", "prep_problem"),
        "lists_total": lists_total,
        "reviews_24h": reviews_24h,
        "lookups_24h": lookups_24h,
        "errors_24h": errors_24h + llm_errors_24h,
        "cost_24h": cost_24h,
        "cost_7d": cost_7d,
        "cost_30d": cost_30d,
        "cost_all": cost_all,
        "calls_24h": calls_24h,
        "calls_7d": calls_7d,
        "calls_30d": calls_30d,
        "calls_all": calls_all,
        "cache_24h": cache_24h,
        "cache_all": cache_all,
        "last_errors": last_errors,
        "last_users": last_users,
        "expensive": expensive,
        "now": now,
    }


async def list_users(db: AsyncSession, *, q: str | None, page: int) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    card_count = (
        select(func.count(LearningCard.id))
        .where(LearningCard.user_id == User.id, LearningCard.deleted_at.is_(None))
        .correlate(User)
        .scalar_subquery()
    )
    list_count = (
        select(func.count(WordList.id))
        .where(WordList.user_id == User.id, WordList.deleted_at.is_(None))
        .correlate(User)
        .scalar_subquery()
    )
    last_rev = (
        select(func.max(ReviewLog.reviewed_at))
        .where(ReviewLog.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    stmt = select(
        User,
        card_count.label("cards"),
        list_count.label("lists"),
        last_rev.label("last_activity"),
    )
    if q and q.strip():
        stmt = stmt.where(User.email.ilike(f"%{q.strip()}%"))
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(stmt.order_by(User.created_at.desc()).offset(offset).limit(PAGE_SIZE))
    ).all()
    return rows, total


async def user_detail(db: AsyncSession, user_id: UUID) -> dict | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    profiles = (
        (
            await db.execute(
                select(LanguageProfile)
                .where(LanguageProfile.user_id == user_id)
                .order_by(LanguageProfile.last_used_at.desc().nulls_last())
            )
        )
        .scalars()
        .all()
    )
    settings = await db.get(UserSettings, user_id)
    lists = (
        (
            await db.execute(
                select(WordList)
                .where(WordList.user_id == user_id, WordList.deleted_at.is_(None))
                .order_by(WordList.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    cards = (
        (
            await db.execute(
                select(LearningCard)
                .where(LearningCard.user_id == user_id, LearningCard.deleted_at.is_(None))
                .order_by(LearningCard.created_at.desc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    reviews = (
        (
            await db.execute(
                select(ReviewLog)
                .where(ReviewLog.user_id == user_id)
                .order_by(ReviewLog.reviewed_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    lookups = (
        (
            await db.execute(
                select(LookupEvent)
                .where(LookupEvent.user_id == user_id)
                .order_by(LookupEvent.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    logs = (
        (
            await db.execute(
                select(AppLog).where(AppLog.user_id == user_id).order_by(AppLog.created_at.desc()).limit(20)
            )
        )
        .scalars()
        .all()
    )
    imports = (
        (
            await db.execute(
                select(ImportJob)
                .where(ImportJob.user_id == user_id)
                .order_by(ImportJob.created_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    cost_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(LlmUsage.estimated_cost_usd), 0),
                func.count(LlmUsage.id),
            ).where(LlmUsage.user_id == user_id)
        )
    ).one()
    usage_rows = (
        (
            await db.execute(
                select(LlmUsage)
                .where(LlmUsage.user_id == user_id)
                .order_by(LlmUsage.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return {
        "user": user,
        "profiles": profiles,
        "settings": settings,
        "lists": lists,
        "cards": cards,
        "reviews": reviews,
        "lookups": lookups,
        "logs": logs,
        "imports": imports,
        "cost_usd": float(cost_row[0] or 0),
        "cost_calls": int(cost_row[1] or 0),
        "usage_rows": usage_rows,
    }


async def list_word_lists(db: AsyncSession, *, q: str | None, page: int) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    card_count = (
        select(func.count(LearningCard.id))
        .where(
            LearningCard.deleted_at.is_(None),
            or_(
                and_(
                    WordList.is_system.is_(True),
                    LearningCard.deck_id.is_(None),
                    LearningCard.profile_id == WordList.profile_id,
                ),
                LearningCard.deck_id == WordList.id,
            ),
        )
        .correlate(WordList)
        .scalar_subquery()
    )
    stmt = (
        select(WordList, User.email, card_count.label("cards"))
        .join(User, User.id == WordList.user_id)
        .where(WordList.deleted_at.is_(None))
    )
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(WordList.name.ilike(like), User.email.ilike(like)))
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(stmt.order_by(WordList.created_at.desc()).offset(offset).limit(PAGE_SIZE))
    ).all()
    return rows, total


async def list_detail(db: AsyncSession, list_id: UUID) -> dict | None:
    wl = await db.get(WordList, list_id)
    if wl is None:
        return None
    user = await db.get(User, wl.user_id)
    if wl.is_system:
        cards = (
            (
                await db.execute(
                    select(LearningCard)
                    .where(
                        LearningCard.user_id == wl.user_id,
                        LearningCard.profile_id == wl.profile_id,
                        LearningCard.deck_id.is_(None),
                        LearningCard.deleted_at.is_(None),
                    )
                    .order_by(LearningCard.created_at.desc())
                    .limit(200)
                )
            )
            .scalars()
            .all()
        )
    else:
        cards = (
            (
                await db.execute(
                    select(LearningCard)
                    .where(LearningCard.deck_id == wl.id, LearningCard.deleted_at.is_(None))
                    .order_by(LearningCard.created_at.desc())
                    .limit(200)
                )
            )
            .scalars()
            .all()
        )
    return {"list": wl, "user": user, "cards": cards}


async def list_cards(
    db: AsyncSession,
    *,
    q: str | None,
    status: str | None,
    user_id: UUID | None,
    page: int,
) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = (
        select(LearningCard, User.email)
        .join(User, User.id == LearningCard.user_id)
        .where(LearningCard.deleted_at.is_(None))
    )
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(LearningCard.lemma_l2.ilike(like), LearningCard.gloss_primary.ilike(like))
        )
    if status:
        stmt = stmt.where(LearningCard.enrichment_status == status)
    if user_id:
        stmt = stmt.where(LearningCard.user_id == user_id)
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(stmt.order_by(LearningCard.created_at.desc()).offset(offset).limit(PAGE_SIZE))
    ).all()
    return rows, total


async def card_detail(db: AsyncSession, card_id: UUID) -> dict | None:
    card = await db.get(LearningCard, card_id)
    if card is None:
        return None
    user = await db.get(User, card.user_id)
    entry = await db.get(LexicalEntry, card.lexical_entry_id) if card.lexical_entry_id else None
    srs = (
        await db.execute(select(SrsState).where(SrsState.card_id == card.id, SrsState.scope == "main"))
    ).scalar_one_or_none()
    reviews = (
        (
            await db.execute(
                select(ReviewLog)
                .where(ReviewLog.card_id == card.id)
                .order_by(ReviewLog.reviewed_at.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )
    conds = [LlmUsage.card_id == card.id, LlmUsage.lemma == card.lemma_l2]
    if card.lookup_event_id:
        conds.append(LlmUsage.lookup_event_id == card.lookup_event_id)
    usage = (
        (
            await db.execute(
                select(LlmUsage)
                .where(or_(*conds))
                .order_by(LlmUsage.created_at.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )
    usage_ids = [u.id for u in usage]
    payloads: dict[UUID, LlmCallPayload] = {}
    if usage_ids:
        payload_rows = (
            (
                await db.execute(
                    select(LlmCallPayload).where(LlmCallPayload.llm_usage_id.in_(usage_ids))
                )
            )
            .scalars()
            .all()
        )
        payloads = {row.llm_usage_id: row for row in payload_rows}
    lookup_event = (
        await db.get(LookupEvent, card.lookup_event_id) if card.lookup_event_id else None
    )
    cost = (
        await db.execute(
            select(func.coalesce(func.sum(LlmUsage.estimated_cost_usd), 0)).where(
                LlmUsage.card_id == card.id
            )
        )
    ).scalar_one()
    return {
        "card": card,
        "user": user,
        "entry": entry,
        "srs": srs,
        "reviews": reviews,
        "usage": usage,
        "payloads": payloads,
        "lookup_event": lookup_event,
        "cost_usd": float(cost or 0),
    }


async def llm_usage_payload(db: AsyncSession, usage_id: UUID) -> dict | None:
    usage = await db.get(LlmUsage, usage_id)
    if usage is None:
        return None
    payload = await db.get(LlmCallPayload, usage_id)
    user = await db.get(User, usage.user_id) if usage.user_id else None
    return {"usage": usage, "payload": payload, "user": user}


async def admin_retry_enrichment(db: AsyncSession, card_id: UUID) -> LearningCard | None:
    card = await db.get(LearningCard, card_id)
    if card is None or card.deleted_at is not None:
        return None
    card.enrichment_status = STATUS_PENDING
    card.enrichment_error = None
    card.enrichment_manual_triggered = True
    await db.commit()
    spawn_enrich(card.id)
    return card


async def list_reviews(db: AsyncSession, *, q: str | None, page: int) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = (
        select(ReviewLog, User.email, LearningCard.lemma_l2)
        .join(User, User.id == ReviewLog.user_id)
        .join(LearningCard, LearningCard.id == ReviewLog.card_id)
    )
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(like), LearningCard.lemma_l2.ilike(like)))
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(stmt.order_by(ReviewLog.reviewed_at.desc()).offset(offset).limit(PAGE_SIZE))
    ).all()
    return rows, total


async def list_lookup_cache(db: AsyncSession, *, q: str | None, page: int) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = select(LookupQueryCache)
    if q and q.strip():
        stmt = stmt.where(LookupQueryCache.input_norm.ilike(f"%{q.strip()}%"))
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        (
            await db.execute(
                stmt.order_by(LookupQueryCache.hit_count.desc()).offset(offset).limit(PAGE_SIZE)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def list_lookup_events(
    db: AsyncSession, *, q: str | None, user_id: UUID | None, page: int
) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = select(LookupEvent, User.email).outerjoin(User, User.id == LookupEvent.user_id)
    if q and q.strip():
        stmt = stmt.where(
            or_(
                LookupEvent.query.ilike(f"%{q.strip()}%"),
                LookupEvent.query_norm.ilike(f"%{q.strip()}%"),
            )
        )
    if user_id:
        stmt = stmt.where(LookupEvent.user_id == user_id)
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(stmt.order_by(LookupEvent.created_at.desc()).offset(offset).limit(PAGE_SIZE))
    ).all()
    return rows, total


def _usage_filters(
    *,
    q: str | None,
    user_id: UUID | None,
    purpose: str | None,
    operation_kind: str | None,
    status: str | None,
    model: str | None,
    since: datetime | None,
    until: datetime | None,
    operation_id: UUID | None,
    card_id: UUID | None,
):
    filters = []
    if q and q.strip():
        like = f"%{q.strip()}%"
        filters.append(
            or_(LlmUsage.lemma.ilike(like), LlmUsage.query.ilike(like), LlmUsage.purpose.ilike(like))
        )
    if user_id:
        filters.append(LlmUsage.user_id == user_id)
    if purpose:
        filters.append(LlmUsage.purpose == purpose)
    if operation_kind:
        filters.append(LlmUsage.operation_kind == operation_kind)
    if status:
        filters.append(LlmUsage.status == status)
    if model:
        filters.append(LlmUsage.model == model)
    if since:
        filters.append(LlmUsage.created_at >= since)
    if until:
        filters.append(LlmUsage.created_at <= until)
    if operation_id:
        filters.append(LlmUsage.operation_id == operation_id)
    if card_id:
        filters.append(LlmUsage.card_id == card_id)
    return filters


async def list_llm_usage(db: AsyncSession, page: int = 1, **kwargs) -> tuple[list, int, dict]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    filters = _usage_filters(**kwargs)
    list_stmt = select(LlmUsage, User.email).outerjoin(User, User.id == LlmUsage.user_id)
    totals_stmt = select(
        func.count(LlmUsage.id),
        func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
        func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
        func.coalesce(func.sum(LlmUsage.cached_tokens), 0),
        func.sum(LlmUsage.estimated_cost_usd),
        func.count(case((LlmUsage.status == "error", 1))),
    )
    if filters:
        list_stmt = list_stmt.where(*filters)
        totals_stmt = totals_stmt.where(*filters)
    totals = (await db.execute(totals_stmt)).one()
    rows = (
        await db.execute(
            list_stmt.order_by(LlmUsage.created_at.desc()).offset(offset).limit(PAGE_SIZE)
        )
    ).all()
    cost = totals[4]
    prompt = int(totals[1] or 0)
    cached = int(totals[3] or 0)
    summary = {
        "total_calls": int(totals[0] or 0),
        "prompt_tokens": prompt,
        "completion_tokens": int(totals[2] or 0),
        "cached_tokens": cached,
        "cost_usd": float(cost) if cost is not None else 0.0,
        "errors": int(totals[5] or 0),
        "cache_pct": (cached / prompt * 100) if prompt else 0.0,
    }
    return rows, summary["total_calls"], summary


async def llm_usage_grouped(db: AsyncSession, group: str, **kwargs) -> list:
    filters = _usage_filters(**kwargs)
    if group == "purpose":
        key = LlmUsage.purpose
    elif group == "user":
        key = LlmUsage.user_id
    elif group == "lemma":
        key = LlmUsage.lemma
    elif group == "model":
        key = LlmUsage.model
    elif group == "operation_kind":
        key = LlmUsage.operation_kind
    else:
        key = cast(LlmUsage.created_at, Date)
    stmt = select(
        key.label("bucket"),
        func.count(LlmUsage.id).label("calls"),
        func.coalesce(func.sum(LlmUsage.estimated_cost_usd), 0).label("usd"),
        func.coalesce(func.sum(LlmUsage.prompt_tokens), 0).label("prompt"),
        func.coalesce(func.sum(LlmUsage.cached_tokens), 0).label("cached"),
    )
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.group_by(key).order_by(desc("usd")).limit(40)
    return list((await db.execute(stmt)).all())


async def list_errors(
    db: AsyncSession,
    *,
    q: str | None,
    level: str | None,
    page: int,
) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = select(AppLog)
    if level:
        stmt = stmt.where(AppLog.level == level)
    else:
        stmt = stmt.where(
            or_(
                AppLog.level.in_(["error", "warn"]),
                AppLog.status == "error",
                AppLog.http_status >= 400,
            )
        )
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                AppLog.message.ilike(like),
                AppLog.error_message.ilike(like),
                AppLog.http_path.ilike(like),
                AppLog.event.ilike(like),
            )
        )
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        (await db.execute(stmt.order_by(AppLog.created_at.desc()).offset(offset).limit(PAGE_SIZE)))
        .scalars()
        .all()
    )
    return rows, total


async def failed_cards(db: AsyncSession, page: int) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = (
        select(LearningCard, User.email)
        .join(User, User.id == LearningCard.user_id)
        .where(
            LearningCard.deleted_at.is_(None),
            LearningCard.enrichment_status.in_(["failed", "prep_problem"]),
        )
    )
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(stmt.order_by(LearningCard.updated_at.desc()).offset(offset).limit(PAGE_SIZE))
    ).all()
    return rows, total


async def list_imports(
    db: AsyncSession, *, q: str | None, status: str | None, page: int
) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = select(ImportJob, User.email).join(User, User.id == ImportJob.user_id)
    if status:
        stmt = stmt.where(ImportJob.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ImportJob.source_name.ilike(like),
                User.email.ilike(like),
                ImportJob.error_message.ilike(like),
            )
        )
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(stmt.order_by(ImportJob.created_at.desc()).offset(offset).limit(PAGE_SIZE))
    ).all()
    return rows, total


async def import_detail(db: AsyncSession, job_id: UUID) -> dict | None:
    job = await db.get(ImportJob, job_id)
    if job is None:
        return None
    user = await db.get(User, job.user_id)
    items = (
        (
            await db.execute(
                select(ImportJobItem)
                .where(ImportJobItem.job_id == job.id)
                .order_by(ImportJobItem.ordinal)
            )
        )
        .scalars()
        .all()
    )
    events = (
        (
            await db.execute(
                select(ImportJobEvent)
                .where(ImportJobEvent.job_id == job.id)
                .order_by(ImportJobEvent.at)
            )
        )
        .scalars()
        .all()
    )
    return {"job": job, "user": user, "items": items, "events": events}


async def content_reviews(db: AsyncSession, page: int) -> tuple[list, int]:
    offset = max(0, (page - 1) * PAGE_SIZE)
    stmt = (
        select(AdminEscalation, User.email, LearningCard.lemma_l2)
        .join(User, User.id == AdminEscalation.user_id)
        .join(LearningCard, LearningCard.id == AdminEscalation.card_id)
    )
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(
            stmt.order_by(AdminEscalation.created_at.desc()).offset(offset).limit(PAGE_SIZE)
        )
    ).all()
    return rows, total

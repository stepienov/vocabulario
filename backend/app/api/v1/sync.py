"""Offline sync: pull user learning data + push review outbox."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import LearningCard, ReviewLog, SrsState, User, UserSettings
from app.schemas import (
    SyncCardItem,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncSrsState,
    UserSettingsResponse,
)
from app.services.answer_check import check_answer, collect_acceptable_answers
from app.services.srs import apply_review

router = APIRouter(tags=["sync"])


def _srs_payload(card_id: UUID, state: SrsState) -> SyncSrsState:
    return SyncSrsState(
        card_id=card_id,
        status=state.status,
        ease=state.ease,
        interval_days=state.interval_days,
        repetitions=state.repetitions,
        lapses=state.lapses,
        next_review_at=state.next_review_at,
        last_reviewed_at=state.last_reviewed_at,
        last_grade=state.last_grade,
        stability=state.stability,
        difficulty=state.difficulty,
        fsrs_step=state.fsrs_step,
    )


@router.get("/sync/pull", response_model=SyncPullResponse)
async def sync_pull(
    profile_id: UUID = Query(...),
    since: datetime | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings = settings_result.scalar_one_or_none()
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        await db.flush()

    card_q = select(LearningCard, SrsState).outerjoin(
        SrsState,
        (SrsState.card_id == LearningCard.id) & (SrsState.scope == "main"),
    ).where(
        LearningCard.user_id == user.id,
        LearningCard.profile_id == profile_id,
    )
    if since is not None:
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        card_q = card_q.where(LearningCard.updated_at >= since)

    rows = (await db.execute(card_q)).all()
    cards: list[SyncCardItem] = []
    for card, state in rows:
        cards.append(
            SyncCardItem(
                id=card.id,
                profile_id=card.profile_id,
                deck_id=card.deck_id,
                lemma_l2=card.lemma_l2,
                pos=card.pos,
                gloss_primary=card.gloss_primary,
                content=dict(card.content or {}),
                enrichment_status=card.enrichment_status,
                updated_at=card.updated_at,
                srs=_srs_payload(card.id, state) if state is not None else None,
            )
        )

    await db.commit()
    return SyncPullResponse(
        server_time=datetime.now(UTC),
        settings=UserSettingsResponse.model_validate(settings),
        cards=cards,
        deleted_card_ids=[],
    )


@router.post("/sync/push", response_model=SyncPushResponse)
async def sync_push(
    body: SyncPushRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    applied = 0
    skipped = 0
    touched: dict[UUID, SrsState] = {}

    # Stable offline order
    reviews = sorted(body.reviews, key=lambda r: r.reviewed_at)

    settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings = settings_result.scalar_one_or_none()
    tolerance = settings.typing_tolerance if settings else "tolerate"

    for item in reviews:
        exists = await db.execute(
            select(ReviewLog.id).where(ReviewLog.client_id == item.client_id)
        )
        if exists.scalar_one_or_none() is not None:
            skipped += 1
            continue

        result = await db.execute(
            select(LearningCard, SrsState)
            .join(SrsState, SrsState.card_id == LearningCard.id)
            .where(
                LearningCard.id == item.card_id,
                LearningCard.user_id == user.id,
                SrsState.scope == "main",
            )
        )
        row = result.one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Card not found: {item.card_id}")
        card, state = row

        correct = item.correct
        if item.mode == "type" and item.answer is not None:
            answers = collect_acceptable_answers(card.content, item.direction)
            correct, _, _ = check_answer(item.answer, answers, tolerance)

        reviewed_at = (
            item.reviewed_at
            if item.reviewed_at.tzinfo
            else item.reviewed_at.replace(tzinfo=UTC)
        )
        state = apply_review(state, item.grade, correct, reviewed_at=reviewed_at)
        db.add(
            ReviewLog(
                card_id=card.id,
                user_id=user.id,
                grade=state.last_grade or item.grade,
                mode=item.mode,
                direction=item.direction,
                correct=correct,
                reviewed_at=reviewed_at,
                client_id=item.client_id,
            )
        )
        touched[card.id] = state
        applied += 1

    await db.commit()
    for state in touched.values():
        await db.refresh(state)

    return SyncPushResponse(
        applied=applied,
        skipped=skipped,
        srs=[_srs_payload(cid, st) for cid, st in touched.items()],
    )

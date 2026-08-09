"""Offline sync: pull user learning data + push review/move outbox."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import AppliedSyncMove, LearningCard, ReviewLog, SrsState, User, UserSettings, WordList
from app.schemas import (
    SyncCardItem,
    SyncListItem,
    SyncMoveResult,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncSrsState,
    UserSettingsResponse,
)
from app.services.answer_check import check_answer, collect_acceptable_answers
from app.services.srs import apply_review
from app.services.word_lists import ensure_system_list, list_word_lists

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


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


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

    await ensure_system_list(db, user.id, profile_id)
    lists_raw = await list_word_lists(db, user.id, profile_id)
    lists = [
        SyncListItem(
            id=wl.id,
            name=wl.name,
            is_system=wl.is_system,
            is_pending_inbox=bool(getattr(wl, "is_pending_inbox", False)),
            word_count=count,
            created_at=wl.created_at,
        )
        for wl, count in lists_raw
    ]

    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)

    card_q = select(LearningCard, SrsState).outerjoin(
        SrsState,
        (SrsState.card_id == LearningCard.id) & (SrsState.scope == "main"),
    ).where(
        LearningCard.user_id == user.id,
        LearningCard.profile_id == profile_id,
        LearningCard.deleted_at.is_(None),
    )
    if since is not None:
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
                content_review_status=card.content_review_status,
                card_activity_status=card.card_activity_status,
                has_content_changes=bool(card.has_content_changes),
                updated_at=card.updated_at,
                srs=_srs_payload(card.id, state) if state is not None else None,
            )
        )

    # Tombstones — tylko przy inkrementalnym pull (since); pełny replace i tak czyści lokalnie.
    deleted_card_ids: list[UUID] = []
    deleted_list_ids: list[UUID] = []
    if since is not None:
        dc = await db.execute(
            select(LearningCard.id).where(
                LearningCard.user_id == user.id,
                LearningCard.profile_id == profile_id,
                LearningCard.deleted_at.is_not(None),
                LearningCard.deleted_at >= since,
            )
        )
        deleted_card_ids = list(dc.scalars().all())
        dl = await db.execute(
            select(WordList.id).where(
                WordList.user_id == user.id,
                WordList.profile_id == profile_id,
                WordList.deleted_at.is_not(None),
                WordList.deleted_at >= since,
            )
        )
        deleted_list_ids = list(dl.scalars().all())

    await db.commit()
    return SyncPullResponse(
        server_time=datetime.now(UTC),
        settings=UserSettingsResponse.model_validate(settings),
        cards=cards,
        lists=lists,
        deleted_card_ids=deleted_card_ids,
        deleted_list_ids=deleted_list_ids,
    )


async def _apply_moves(
    db: AsyncSession,
    user: User,
    body: SyncPushRequest,
) -> tuple[int, int, list[SyncMoveResult]]:
    moves_applied = 0
    moves_skipped = 0
    results: list[SyncMoveResult] = []
    moves = sorted(body.moves, key=lambda m: _aware(m.moved_at))

    for item in moves:
        exists = await db.execute(
            select(AppliedSyncMove.client_id).where(AppliedSyncMove.client_id == item.client_id)
        )
        if exists.scalar_one_or_none() is not None:
            moves_skipped += 1
            continue

        newer = await db.execute(
            select(AppliedSyncMove.client_id).where(
                AppliedSyncMove.card_id == item.card_id,
                AppliedSyncMove.user_id == user.id,
                AppliedSyncMove.moved_at > _aware(item.moved_at),
            ).limit(1)
        )
        if newer.scalar_one_or_none() is not None:
            # Stale move — record client_id so retries are idempotent, don't change deck.
            db.add(
                AppliedSyncMove(
                    client_id=item.client_id,
                    user_id=user.id,
                    card_id=item.card_id,
                    moved_at=_aware(item.moved_at),
                )
            )
            moves_skipped += 1
            continue

        card = (
            await db.execute(
                select(LearningCard).where(
                    LearningCard.id == item.card_id,
                    LearningCard.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if card is None:
            # Card gone (deleted on another device). Skip — never abort the batch.
            # Cannot record AppliedSyncMove (FK → learning_cards would fail); on retry
            # the client drops skipped ops, so no reprocessing loop.
            moves_skipped += 1
            continue

        target: WordList | None = None
        if item.target_list_id is not None:
            target = (
                await db.execute(
                    select(WordList).where(
                        WordList.id == item.target_list_id,
                        WordList.user_id == user.id,
                        WordList.profile_id == card.profile_id,
                    )
                )
            ).scalar_one_or_none()
            if target is None:
                # Target list gone. Record idempotency (card still exists) and skip.
                db.add(
                    AppliedSyncMove(
                        client_id=item.client_id,
                        user_id=user.id,
                        card_id=card.id,
                        moved_at=_aware(item.moved_at),
                    )
                )
                moves_skipped += 1
                continue

        if target is None or target.is_system:
            card.deck_id = None
            srs_q = await db.execute(
                select(SrsState).where(SrsState.card_id == card.id, SrsState.scope == "main")
            )
            if srs_q.scalar_one_or_none() is None:
                db.add(SrsState(card_id=card.id, scope="main", status="new"))
        else:
            card.deck_id = target.id

        db.add(
            AppliedSyncMove(
                client_id=item.client_id,
                user_id=user.id,
                card_id=card.id,
                moved_at=_aware(item.moved_at),
            )
        )
        results.append(
            SyncMoveResult(client_id=item.client_id, card_id=card.id, deck_id=card.deck_id)
        )
        moves_applied += 1

    return moves_applied, moves_skipped, results


@router.post("/sync/push", response_model=SyncPushResponse)
async def sync_push(
    body: SyncPushRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    moves_applied, moves_skipped, move_results = await _apply_moves(db, user, body)

    applied = 0
    skipped = 0
    touched: dict[UUID, SrsState] = {}

    reviews = sorted(body.reviews, key=lambda r: _aware(r.reviewed_at))

    tolerance = "tolerate"

    for item in reviews:
        exists = await db.execute(
            select(ReviewLog.id).where(ReviewLog.client_id == item.client_id)
        )
        if exists.scalar_one_or_none() is not None:
            skipped += 1
            continue

        card = (
            await db.execute(
                select(LearningCard).where(
                    LearningCard.id == item.card_id,
                    LearningCard.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if card is None:
            # Card gone (deleted elsewhere). Skip — never abort the batch on a stale review.
            skipped += 1
            continue

        state = (
            await db.execute(
                select(SrsState).where(
                    SrsState.card_id == card.id, SrsState.scope == "main"
                )
            )
        ).scalar_one_or_none()
        if state is None:
            # Card without a main SRS row (legacy / imported). Create it before applying.
            state = SrsState(card_id=card.id, scope="main", status="new")
            db.add(state)
            await db.flush()

        correct = item.correct
        if item.mode == "type" and item.answer is not None:
            answers = collect_acceptable_answers(card.content, item.direction)
            correct, _, _ = check_answer(item.answer, answers, tolerance)

        reviewed_at = _aware(item.reviewed_at)
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
        moves_applied=moves_applied,
        moves_skipped=moves_skipped,
        moves=move_results,
    )

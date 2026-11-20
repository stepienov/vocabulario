"""Offline sync: pull user learning data + push review/move outbox (z jawnym ACK per operacja)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_verified_user
from app.db.session import get_db
from app.models import (
    AppliedReviewUndo,
    AppliedSyncMove,
    LearningCard,
    ReviewLog,
    SrsState,
    User,
    UserSettings,
    WordList,
)
from app.schemas import (
    SyncListItem,
    SyncMoveItem,
    SyncMoveResult,
    SyncOperationResult,
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncReviewItem,
    UserSettingsResponse,
)
from app.services import sync_pull
from app.services.answer_check import check_answer, collect_acceptable_answers
from app.services.srs import apply_review
from app.services.sync_pull import srs_payload as _srs_payload
from app.services.word_lists import ensure_system_list, list_word_lists

router = APIRouter(tags=["sync"])


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _ms(dt: datetime) -> int:
    return int(_aware(dt).timestamp() * 1000)


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def review_fingerprint(item: SyncReviewItem) -> str:
    return _digest(
        "review", item.card_id, item.grade, item.mode, item.direction,
        int(item.correct), item.answer or "", _ms(item.reviewed_at),
    )


def move_fingerprint(item: SyncMoveItem) -> str:
    return _digest("move", item.card_id, item.target_list_id or "", _ms(item.moved_at))


def _result(item, outcome: str, reason: str | None = None) -> SyncOperationResult:
    return SyncOperationResult(client_id=item.client_id, card_id=item.card_id, outcome=outcome, reason=reason)


@router.get("/sync/pull", response_model=SyncPullResponse)
async def sync_pull_legacy(
    profile_id: UUID = Query(...),
    since: datetime | None = Query(default=None),
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Zgodność ze starszym klientem; nowy klient używa POST /sync/pull z kursorem."""
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

    cards = [sync_pull.card_item(card, state) for card, state in (await db.execute(card_q)).all()]

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


@router.post("/sync/pull", response_model=SyncPullResponse)
async def sync_pull_cursor(
    body: SyncPullRequest,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    return await sync_pull.pull(db, user, body.profile_id, body.cursor)


async def _lock_cards(db: AsyncSession, user_id: UUID, card_ids: set[UUID]) -> dict[UUID, LearningCard]:
    """Wspólna, uporządkowana blokada kart: równoległe ponowienia i /srs/* serializują się na karcie."""
    if not card_ids:
        return {}
    rows = await db.execute(
        select(LearningCard)
        .where(LearningCard.id.in_(card_ids), LearningCard.user_id == user_id)
        .order_by(LearningCard.id)
        .with_for_update()
    )
    return {card.id: card for card in rows.scalars().all()}


def _foreign_or_changed(existing_user_id: UUID, existing_fp: str | None, user: User, fp: str) -> bool:
    return existing_user_id != user.id or (existing_fp is not None and existing_fp != fp)


async def _apply_moves(
    db: AsyncSession,
    user: User,
    body: SyncPushRequest,
    cards: dict[UUID, LearningCard],
) -> tuple[int, int, list[SyncMoveResult], list[SyncOperationResult]]:
    applied = 0
    skipped = 0
    results: list[SyncMoveResult] = []
    acks: list[SyncOperationResult] = []

    for item in sorted(body.moves, key=lambda m: _aware(m.moved_at)):
        fp = move_fingerprint(item)
        existing = (
            await db.execute(select(AppliedSyncMove).where(AppliedSyncMove.client_id == item.client_id))
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            if _foreign_or_changed(existing.user_id, existing.intent_fingerprint, user, fp):
                acks.append(_result(item, "conflict", "operation_id_conflict"))
            else:
                acks.append(_result(item, "duplicate"))
            continue

        card = cards.get(item.card_id)
        if card is None or card.deleted_at is not None:
            skipped += 1
            acks.append(_result(item, "not_found", "card_unavailable"))
            continue

        newer = await db.execute(
            select(AppliedSyncMove.client_id).where(
                AppliedSyncMove.card_id == item.card_id,
                AppliedSyncMove.user_id == user.id,
                AppliedSyncMove.moved_at > _aware(item.moved_at),
            ).limit(1)
        )
        if newer.scalar_one_or_none() is not None:
            # Starszy ruch przegrywa; zapis client_id czyni ponowienia idempotentnymi.
            db.add(
                AppliedSyncMove(
                    client_id=item.client_id, user_id=user.id, card_id=card.id,
                    moved_at=_aware(item.moved_at), intent_fingerprint=fp,
                )
            )
            skipped += 1
            acks.append(_result(item, "superseded"))
            continue

        target: WordList | None = None
        if item.target_list_id is not None:
            target = (
                await db.execute(
                    select(WordList).where(
                        WordList.id == item.target_list_id,
                        WordList.user_id == user.id,
                        WordList.profile_id == card.profile_id,
                        WordList.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if target is None:
                skipped += 1
                acks.append(_result(item, "not_found", "target_unavailable"))
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
                client_id=item.client_id, user_id=user.id, card_id=card.id,
                moved_at=_aware(item.moved_at), intent_fingerprint=fp,
            )
        )
        results.append(SyncMoveResult(client_id=item.client_id, card_id=card.id, deck_id=card.deck_id))
        acks.append(_result(item, "applied"))
        applied += 1

    return applied, skipped, results, acks


@router.post("/sync/push", response_model=SyncPushResponse)
async def sync_push(
    body: SyncPushRequest,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    cards = await _lock_cards(
        db, user.id, {m.card_id for m in body.moves} | {r.card_id for r in body.reviews}
    )
    moves_applied, moves_skipped, move_results, move_acks = await _apply_moves(db, user, body, cards)

    applied = 0
    skipped = 0
    touched: dict[UUID, SrsState] = {}
    review_acks: list[SyncOperationResult] = []

    for item in sorted(body.reviews, key=lambda r: _aware(r.reviewed_at)):
        fp = review_fingerprint(item)
        existing = (
            await db.execute(select(ReviewLog).where(ReviewLog.client_id == item.client_id))
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            if _foreign_or_changed(existing.user_id, existing.intent_fingerprint, user, fp):
                review_acks.append(_result(item, "conflict", "operation_id_conflict"))
            else:
                review_acks.append(_result(item, "duplicate"))
            continue

        marker = await db.get(AppliedReviewUndo, item.client_id)
        if marker is not None:
            skipped += 1
            if marker.user_id != user.id or marker.card_id != item.card_id:
                review_acks.append(_result(item, "conflict", "operation_id_conflict"))
            else:
                review_acks.append(_result(item, "superseded", "undo_already_applied"))
            continue

        card = cards.get(item.card_id)
        if card is None or card.deleted_at is not None:
            skipped += 1
            review_acks.append(_result(item, "not_found", "card_unavailable"))
            continue

        state = (
            await db.execute(
                select(SrsState).where(SrsState.card_id == card.id, SrsState.scope == "main")
            )
        ).scalar_one_or_none()
        if state is None:
            state = SrsState(card_id=card.id, scope="main", status="new")
            db.add(state)
            await db.flush()

        correct = item.correct
        if item.mode == "type" and item.answer is not None:
            answers = collect_acceptable_answers(card.content, item.direction)
            correct, _, _, _ = check_answer(item.answer, answers, "tolerate")

        reviewed_at = _aware(item.reviewed_at)
        state = apply_review(state, item.grade, correct, reviewed_at=reviewed_at)
        await db.flush()
        await db.refresh(state, ["review_revision"])
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
                applied_revision=state.review_revision,
                intent_fingerprint=fp,
            )
        )
        touched[card.id] = state
        review_acks.append(_result(item, "applied"))
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
        review_results=review_acks,
        move_results=move_acks,
    )



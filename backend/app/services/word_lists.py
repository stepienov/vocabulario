"""User word lists. System list 'Uczę się' = LearningCard.deck_id IS NULL."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningCard, WordList

LEARNING_LIST_NAME = "Uczę się"
PENDING_INBOX_NAME = "Pending"
RESERVED_LIST_NAMES = frozenset({LEARNING_LIST_NAME.lower(), PENDING_INBOX_NAME.lower(), "oczekujące"})


async def ensure_system_list(
    db: AsyncSession,
    user_id: UUID,
    profile_id: UUID,
) -> WordList:
    result = await db.execute(
        select(WordList).where(
            WordList.profile_id == profile_id,
            WordList.is_system.is_(True),
            WordList.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    wl = WordList(
        user_id=user_id,
        profile_id=profile_id,
        name=LEARNING_LIST_NAME,
        is_system=True,
        is_pending_inbox=False,
    )
    db.add(wl)
    await db.flush()
    return wl


async def ensure_pending_inbox_list(
    db: AsyncSession,
    user_id: UUID,
    profile_id: UUID,
) -> WordList:
    """Offline-search inbox — stable slug via is_pending_inbox (UI localizes the label)."""
    result = await db.execute(
        select(WordList).where(
            WordList.profile_id == profile_id,
            WordList.user_id == user_id,
            WordList.is_pending_inbox.is_(True),
            WordList.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    # Avoid UniqueConstraint(profile_id, name) clash if user already named a list "Pending".
    name = PENDING_INBOX_NAME
    clash = await db.execute(
        select(WordList).where(
            WordList.profile_id == profile_id,
            WordList.user_id == user_id,
            WordList.name == name,
            WordList.deleted_at.is_(None),
        )
    )
    if clash.scalar_one_or_none() is not None:
        name = f"{PENDING_INBOX_NAME} · inbox"
    wl = WordList(
        user_id=user_id,
        profile_id=profile_id,
        name=name,
        is_system=False,
        is_pending_inbox=True,
    )
    db.add(wl)
    await db.flush()
    return wl


async def list_word_lists(
    db: AsyncSession,
    user_id: UUID,
    profile_id: UUID,
) -> list[tuple[WordList, int]]:
    system = await ensure_system_list(db, user_id, profile_id)
    result = await db.execute(
        select(WordList)
        .where(
            WordList.profile_id == profile_id,
            WordList.user_id == user_id,
            WordList.deleted_at.is_(None),
        )
        .order_by(WordList.is_system.desc(), WordList.created_at.asc())
    )
    lists = list(result.scalars().all())
    if not any(wl.id == system.id for wl in lists):
        lists.insert(0, system)

    out: list[tuple[WordList, int]] = []
    for wl in lists:
        if wl.is_system:
            count_q = await db.execute(
                select(func.count())
                .select_from(LearningCard)
                .where(
                    LearningCard.user_id == user_id,
                    LearningCard.profile_id == profile_id,
                    LearningCard.deck_id.is_(None),
                    LearningCard.deleted_at.is_(None),
                )
            )
        else:
            count_q = await db.execute(
                select(func.count())
                .select_from(LearningCard)
                .where(
                    LearningCard.user_id == user_id,
                    LearningCard.profile_id == profile_id,
                    LearningCard.deck_id == wl.id,
                    LearningCard.deleted_at.is_(None),
                )
            )
        out.append((wl, int(count_q.scalar_one())))
    return out


async def find_card_anywhere(
    db: AsyncSession,
    user_id: UUID,
    profile_id: UUID,
    lemma: str,
    pos: str | None = None,
) -> LearningCard | None:
    q = select(LearningCard).where(
        LearningCard.user_id == user_id,
        LearningCard.profile_id == profile_id,
        LearningCard.lemma_l2 == lemma,
        LearningCard.deleted_at.is_(None),
    )
    if pos:
        q = q.where(LearningCard.pos == pos)
    result = await db.execute(q)
    return result.scalars().first()


async def resolve_list_for_card(
    db: AsyncSession,
    user_id: UUID,
    profile_id: UUID,
    card: LearningCard | None,
) -> tuple[UUID | None, str | None]:
    if card is None:
        return None, None
    system = await ensure_system_list(db, user_id, profile_id)
    if card.deck_id is None:
        return system.id, system.name
    result = await db.execute(select(WordList).where(WordList.id == card.deck_id))
    wl = result.scalar_one_or_none()
    if wl:
        return wl.id, wl.name
    return card.deck_id, "Lista"

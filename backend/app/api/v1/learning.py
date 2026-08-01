import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, normalize_text
from app.db.session import get_db
from app.models import FavoriteWord, LanguageProfile, LearningCard, ReviewLog, SrsState, User, UserSettings, WordList
from app.schemas import (
    CardCreateRequest,
    CardResponse,
    DashboardForecastDay,
    DashboardStatsResponse,
    FavoriteCreate,
    FavoriteResponse,
    LookupCandidate,
    LookupRequest,
    LookupResponse,
    ReviewRequest,
    ReviewResponse,
    SrsQueueItem,
    SrsQueueResponse,
    WordListAddWordRequest,
    WordListCreate,
    WordListUpdate,
    WordListResponse,
    WordMoveRequest,
)
from app.schemas.practice import CheckAnswerRequest, CheckAnswerResponse, ChoiceOption, DistractorsRequest, DistractorsResponse
from app.services.answer_check import check_answer, collect_acceptable_answers
from app.services.card_jobs import (
    STATUS_PENDING,
    STATUS_READY,
    build_pending_content,
    enrich_card,
    enrich_favorite,
)
from app.services.distractors import generate_choice_options
from app.services.lexical import LexicalService
from app.services.similar_words import ensure_similar_words
from app.services.srs import apply_review
from app.services.word_lists import ensure_system_list, find_card_anywhere, list_word_lists
from app.services.word_persistence import words_persistence_enabled

router = APIRouter(tags=["learning"])


async def _active_profile(db: AsyncSession, user_id: UUID, profile_id: UUID | None) -> LanguageProfile:
    if profile_id:
        result = await db.execute(
            select(LanguageProfile).where(
                LanguageProfile.id == profile_id,
                LanguageProfile.user_id == user_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile
    result = await db.execute(
        select(LanguageProfile).where(
            LanguageProfile.user_id == user_id,
            LanguageProfile.is_active.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=400, detail="No active language profile")
    return profile


@router.post("/lookup", response_model=LookupResponse)
async def lookup(
    body: LookupRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = LexicalService(db)
    try:
        raw, source = await service.lookup(user, body.profile_id, body.text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    candidates = [
        LookupCandidate(
            lemma=c["lemma"],
            pos=c.get("pos"),
            gloss=c.get("gloss", ""),
            lexical_entry_id=UUID(c["lexical_entry_id"]) if c.get("lexical_entry_id") else None,
            in_learning=c.get("in_learning", False),
            is_favorite=c.get("is_favorite", False),
            learning_card_id=UUID(c["learning_card_id"]) if c.get("learning_card_id") else None,
            list_id=UUID(c["list_id"]) if c.get("list_id") else None,
            list_name=c.get("list_name"),
            enrichment_status=c.get("enrichment_status"),
        )
        for c in raw
    ]
    await db.commit()
    return LookupResponse(candidates=candidates, source=source)


@router.post("/cards", response_model=CardResponse, status_code=201)
async def create_card(
    body: CardCreateRequest,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Zapisuje kartę od razu; pełną treść dociąga zadanie w tle."""
    service = LexicalService(db)
    try:
        profile = await service.get_profile(user.id, body.profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not words_persistence_enabled():
        try:
            entry = await service.get_or_create_entry(
                user, profile, body.lemma, body.pos, body.lexical_entry_id
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return CardResponse(
            id=entry.id,
            lemma_l2=entry.lemma_l2,
            pos=entry.pos,
            gloss_primary=entry.lemma_l1_primary,
            content=dict(entry.content or {}),
            lexical_entry_id=None,
            created_at=datetime.now(UTC),
            persisted=False,
        )

    existing = await find_card_anywhere(db, user.id, profile.id, body.lemma, body.pos)
    if existing is not None:
        raise HTTPException(status_code=409, detail="To słowo jest już na liście")

    card = LearningCard(
        user_id=user.id,
        profile_id=profile.id,
        lemma_l2=body.lemma,
        pos=body.pos,
        gloss_primary=body.gloss,
        content=build_pending_content(
            lemma=body.lemma,
            pos=body.pos,
            gloss=body.gloss,
            learning_lang=profile.learning_lang,
        ),
        enrichment_status=STATUS_PENDING,
    )
    db.add(card)
    await db.flush()
    db.add(SrsState(card_id=card.id, scope="main", status="new"))
    await db.commit()
    await db.refresh(card)

    background.add_task(enrich_card, card.id)
    return card


@router.get("/cards", response_model=list[CardResponse])
async def list_cards(
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningCard).where(
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile_id,
        ).order_by(LearningCard.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/favorites", response_model=FavoriteResponse, status_code=201)
async def add_favorite(
    body: FavoriteCreate,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ulubione pojawia się natychmiast; wpis słownikowy powstaje w tle."""
    if not words_persistence_enabled():
        raise HTTPException(
            status_code=503,
            detail="Zapis ulubionych wyłączony (PERSIST_WORDS=false)",
        )
    fav = FavoriteWord(
        user_id=user.id,
        profile_id=body.profile_id,
        lemma=body.lemma,
        pos=body.pos,
        gloss=body.gloss,
        enrichment_status=STATUS_PENDING,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)

    background.add_task(enrich_favorite, fav.id)
    return fav


@router.get("/favorites", response_model=list[FavoriteResponse])
async def list_favorites(
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FavoriteWord).where(
            FavoriteWord.user_id == user.id,
            FavoriteWord.profile_id == profile_id,
        )
    )
    return list(result.scalars().all())


def _resolve_direction(settings: UserSettings) -> str:
    pref = settings.practice_direction
    if pref == "random":
        return random.choice(["l2_to_l1", "l1_to_l2"])
    return pref


@router.get("/srs/queue", response_model=SrsQueueResponse)
async def srs_queue(
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC)
    settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings = settings_result.scalar_one_or_none()
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        await db.flush()

    due_result = await db.execute(
        select(LearningCard, SrsState)
        .join(SrsState, SrsState.card_id == LearningCard.id)
        .where(
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile_id,
            LearningCard.deck_id.is_(None),
            LearningCard.enrichment_status == STATUS_READY,
            SrsState.scope == "main",
            SrsState.status.in_(["learning", "review", "relearning"]),
            SrsState.next_review_at.is_not(None),
            SrsState.next_review_at <= now,
        )
        .order_by(SrsState.next_review_at.asc())
    )
    direction = _resolve_direction(settings)
    items: list[SrsQueueItem] = []
    for card, state in due_result.all():
        card_direction = (
            random.choice(["l2_to_l1", "l1_to_l2"])
            if settings.practice_direction == "random"
            else direction
        )
        items.append(
            SrsQueueItem(
                card_id=card.id,
                lemma_l2=card.lemma_l2,
                gloss_primary=card.gloss_primary,
                content=card.content,
                status=state.status,
                direction=card_direction,
            )
        )

    new_limit = settings.new_cards_per_day if settings.new_cards_per_day > 0 else None
    new_query = (
        select(LearningCard, SrsState)
        .join(SrsState, SrsState.card_id == LearningCard.id)
        .where(
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile_id,
            LearningCard.deck_id.is_(None),
            LearningCard.enrichment_status == STATUS_READY,
            SrsState.scope == "main",
            SrsState.status == "new",
        )
    )
    if new_limit is not None:
        new_query = new_query.limit(new_limit)
    new_result = await db.execute(new_query)
    new_items = []
    for card, state in new_result.all():
        card_direction = (
            random.choice(["l2_to_l1", "l1_to_l2"])
            if settings.practice_direction == "random"
            else direction
        )
        new_items.append(
            SrsQueueItem(
                card_id=card.id,
                lemma_l2=card.lemma_l2,
                gloss_primary=card.gloss_primary,
                content=card.content,
                status=state.status,
                direction=card_direction,
            )
        )

    return SrsQueueResponse(due=items, new=new_items, practice_direction=direction)


@router.post("/srs/distractors", response_model=DistractorsResponse)
async def srs_distractors(
    body: DistractorsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningCard).where(
            LearningCard.id == body.card_id,
            LearningCard.user_id == user.id,
            LearningCard.profile_id == body.profile_id,
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")

    profile_result = await db.execute(
        select(LanguageProfile).where(
            LanguageProfile.id == body.profile_id,
            LanguageProfile.user_id == user.id,
        )
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        content = await ensure_similar_words(
            dict(card.content or {}),
            profile,
            card.lemma_l2,
            card.pos,
        )
        if content != card.content:
            card.content = content
        raw_options = await generate_choice_options(
            db, user.id, body.profile_id, card, body.direction, profile
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await db.commit()
    options = [
        ChoiceOption(
            text=o["text"],
            lemma_l2=o.get("lemma_l2"),
            gloss=o.get("gloss"),
            pos=o.get("pos"),
            card_id=UUID(o["card_id"]) if o.get("card_id") else None,
            in_learning=o.get("in_learning", False),
            is_correct=o.get("is_correct", False),
        )
        for o in raw_options
    ]
    return DistractorsResponse(options=options, direction=body.direction)


@router.post("/srs/review", response_model=ReviewResponse)
async def srs_review(
    body: ReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningCard, SrsState)
        .join(SrsState, SrsState.card_id == LearningCard.id)
        .where(
            LearningCard.id == body.card_id,
            LearningCard.user_id == user.id,
            SrsState.scope == "main",
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Card not found")
    card, state = row

    settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings = settings_result.scalar_one_or_none()
    tolerance = settings.typing_tolerance if settings else "tolerate"

    correct = body.correct
    if body.mode == "type" and body.answer is not None:
        answers = collect_acceptable_answers(card.content, body.direction)
        correct, _, _ = check_answer(body.answer, answers, tolerance)

    state = apply_review(state, body.grade, correct)
    log = ReviewLog(
        card_id=card.id,
        user_id=user.id,
        grade=state.last_grade or body.grade,
        mode=body.mode,
        direction=body.direction,
        correct=correct,
    )
    db.add(log)
    await db.commit()
    await db.refresh(state)
    return ReviewResponse(
        next_review_at=state.next_review_at,
        status=state.status,
        interval_days=state.interval_days,
    )


@router.post("/srs/check-answer", response_model=CheckAnswerResponse)
async def check_typed_answer(
    body: CheckAnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_id = UUID(body.card_id)
    result = await db.execute(
        select(LearningCard).where(LearningCard.id == card_id, LearningCard.user_id == user.id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")

    settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings = settings_result.scalar_one_or_none()
    tolerance = settings.typing_tolerance if settings else "tolerate"

    answers = collect_acceptable_answers(card.content, body.direction)
    correct, canonical, accepted_as_typo = check_answer(body.answer, answers, tolerance)
    return CheckAnswerResponse(
        correct=correct,
        expected=canonical,
        accepted_as_typo=accepted_as_typo,
    )


@router.get("/lists", response_model=list[WordListResponse])
async def get_lists(
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _active_profile(db, user.id, profile_id)
    rows = await list_word_lists(db, user.id, profile_id)
    await db.commit()
    return [
        WordListResponse(
            id=wl.id,
            name=wl.name,
            is_system=wl.is_system,
            word_count=count,
            created_at=wl.created_at,
        )
        for wl, count in rows
    ]


@router.post("/lists", response_model=WordListResponse, status_code=201)
async def create_list(
    body: WordListCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, body.profile_id)
    await ensure_system_list(db, user.id, profile.id)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nazwa listy jest wymagana")
    if name.lower() == "uczę się":
        raise HTTPException(status_code=400, detail="Ta nazwa jest zarezerwowana")
    existing = await db.execute(
        select(WordList).where(
            WordList.profile_id == profile.id,
            func.lower(WordList.name) == name.lower(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Lista o tej nazwie już istnieje")
    wl = WordList(user_id=user.id, profile_id=profile.id, name=name, is_system=False)
    db.add(wl)
    await db.commit()
    await db.refresh(wl)
    return WordListResponse(
        id=wl.id,
        name=wl.name,
        is_system=False,
        word_count=0,
        created_at=wl.created_at,
    )


@router.patch("/lists/{list_id}", response_model=WordListResponse)
async def rename_list(
    list_id: UUID,
    body: WordListUpdate,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, profile_id)
    result = await db.execute(
        select(WordList).where(
            WordList.id == list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise HTTPException(status_code=404, detail="Lista nie znaleziona")
    if wl.is_system:
        raise HTTPException(status_code=400, detail="Tej listy nie można edytować")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nazwa listy jest wymagana")
    if name.lower() == "uczę się":
        raise HTTPException(status_code=400, detail="Ta nazwa jest zarezerwowana")
    clash = await db.execute(
        select(WordList).where(
            WordList.profile_id == profile.id,
            func.lower(WordList.name) == name.lower(),
            WordList.id != list_id,
        )
    )
    if clash.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Lista o tej nazwie już istnieje")
    wl.name = name
    await db.commit()
    await db.refresh(wl)
    count_q = await db.execute(
        select(func.count())
        .select_from(LearningCard)
        .where(
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile.id,
            LearningCard.deck_id == wl.id,
        )
    )
    return WordListResponse(
        id=wl.id,
        name=wl.name,
        is_system=False,
        word_count=int(count_q.scalar_one()),
        created_at=wl.created_at,
    )


@router.delete("/lists/{list_id}", status_code=204)
async def delete_list(
    list_id: UUID,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, profile_id)
    result = await db.execute(
        select(WordList).where(
            WordList.id == list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise HTTPException(status_code=404, detail="Lista nie znaleziona")
    if wl.is_system:
        raise HTTPException(status_code=400, detail="Tej listy nie można usunąć")
    cards = (
        await db.execute(
            select(LearningCard).where(
                LearningCard.user_id == user.id,
                LearningCard.profile_id == profile.id,
                LearningCard.deck_id == wl.id,
            )
        )
    ).scalars().all()
    for card in cards:
        await db.delete(card)
    await db.delete(wl)
    await db.commit()


@router.delete("/cards/{card_id}", status_code=204)
async def delete_card(
    card_id: UUID,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, profile_id)
    result = await db.execute(
        select(LearningCard).where(
            LearningCard.id == card_id,
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile.id,
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Karta nie znaleziona")
    await db.delete(card)
    await db.commit()


@router.post("/cards/{card_id}/move", response_model=CardResponse)
async def move_card(
    card_id: UUID,
    body: WordMoveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, body.profile_id)
    result = await db.execute(
        select(LearningCard).where(
            LearningCard.id == card_id,
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile.id,
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="Karta nie znaleziona")

    target_q = await db.execute(
        select(WordList).where(
            WordList.id == body.target_list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
        )
    )
    target = target_q.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Lista docelowa nie znaleziona")

    if target.is_system:
        card.deck_id = None
        srs_q = await db.execute(
            select(SrsState).where(SrsState.card_id == card.id, SrsState.scope == "main")
        )
        if srs_q.scalar_one_or_none() is None:
            db.add(SrsState(card_id=card.id, scope="main", status="new"))
    else:
        card.deck_id = target.id

    await db.commit()
    await db.refresh(card)
    srs_q = await db.execute(
        select(SrsState).where(SrsState.card_id == card.id, SrsState.scope == "main")
    )
    return _card_response(card, srs_q.scalar_one_or_none())


def _card_response(card: LearningCard, srs: SrsState | None = None) -> CardResponse:
    return CardResponse(
        id=card.id,
        lemma_l2=card.lemma_l2,
        pos=card.pos,
        gloss_primary=card.gloss_primary,
        content=dict(card.content or {}),
        lexical_entry_id=card.lexical_entry_id,
        created_at=card.created_at,
        persisted=True,
        enrichment_status=card.enrichment_status,
        enrichment_error=card.enrichment_error,
        srs_status=srs.status if srs else None,
        srs_interval_days=srs.interval_days if srs else None,
    )


@router.get("/lists/{list_id}/words", response_model=list[CardResponse])
async def list_words(
    list_id: UUID,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, profile_id)
    result = await db.execute(
        select(WordList).where(
            WordList.id == list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise HTTPException(status_code=404, detail="Lista nie znaleziona")
    if wl.is_system:
        cards_q = await db.execute(
            select(LearningCard)
            .where(
                LearningCard.user_id == user.id,
                LearningCard.profile_id == profile.id,
                LearningCard.deck_id.is_(None),
            )
            .order_by(LearningCard.created_at.desc())
        )
    else:
        cards_q = await db.execute(
            select(LearningCard)
            .where(
                LearningCard.user_id == user.id,
                LearningCard.profile_id == profile.id,
                LearningCard.deck_id == wl.id,
            )
            .order_by(LearningCard.created_at.desc())
        )
    cards = list(cards_q.scalars().all())
    if not cards:
        return []
    srs_q = await db.execute(
        select(SrsState).where(
            SrsState.card_id.in_([c.id for c in cards]),
            SrsState.scope == "main",
        )
    )
    srs_by_card = {s.card_id: s for s in srs_q.scalars().all()}
    return [_card_response(c, srs_by_card.get(c.id)) for c in cards]


@router.post("/lists/{list_id}/words", response_model=CardResponse, status_code=201)
async def add_word_to_list(
    list_id: UUID,
    body: WordListAddWordRequest,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, body.profile_id)
    result = await db.execute(
        select(WordList).where(
            WordList.id == list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise HTTPException(status_code=404, detail="Lista nie znaleziona")

    existing = await find_card_anywhere(db, user.id, profile.id, body.lemma, body.pos)
    if existing is not None:
        raise HTTPException(status_code=409, detail="To słowo jest już na liście")

    if wl.is_system:
        # Same as POST /cards
        card = LearningCard(
            user_id=user.id,
            profile_id=profile.id,
            lemma_l2=body.lemma,
            pos=body.pos,
            gloss_primary=body.gloss,
            content=build_pending_content(
                lemma=body.lemma,
                pos=body.pos,
                gloss=body.gloss,
                learning_lang=profile.learning_lang,
            ),
            enrichment_status=STATUS_PENDING,
        )
        db.add(card)
        await db.flush()
        db.add(SrsState(card_id=card.id, scope="main", status="new"))
    else:
        card = LearningCard(
            user_id=user.id,
            profile_id=profile.id,
            deck_id=wl.id,
            lemma_l2=body.lemma,
            pos=body.pos,
            gloss_primary=body.gloss,
            content=build_pending_content(
                lemma=body.lemma,
                pos=body.pos,
                gloss=body.gloss,
                learning_lang=profile.learning_lang,
            ),
            enrichment_status=STATUS_PENDING,
        )
        db.add(card)
        await db.flush()

    await db.commit()
    await db.refresh(card)
    background.add_task(enrich_card, card.id)
    return card


@router.get("/stats", response_model=DashboardStatsResponse)
async def dashboard_stats(
    profile_id: UUID = Query(...),
    days: int = Query(1, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, profile_id)
    settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings = settings_result.scalar_one_or_none()
    new_limit = settings.new_cards_per_day if settings else 20

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    mastered_interval = 21.0

    learning_filter = (
        LearningCard.user_id == user.id,
        LearningCard.profile_id == profile.id,
        LearningCard.deck_id.is_(None),
    )
    srs_base = (
        *learning_filter,
        SrsState.scope == "main",
    )

    due_q = await db.execute(
        select(func.count())
        .select_from(SrsState)
        .join(LearningCard, LearningCard.id == SrsState.card_id)
        .where(
            *srs_base,
            LearningCard.enrichment_status == STATUS_READY,
            SrsState.status.in_(["learning", "review", "relearning"]),
            SrsState.next_review_at.is_not(None),
            SrsState.next_review_at <= now,
        )
    )
    due_count = int(due_q.scalar_one())

    new_reserve_q = await db.execute(
        select(func.count())
        .select_from(SrsState)
        .join(LearningCard, LearningCard.id == SrsState.card_id)
        .where(
            *srs_base,
            LearningCard.enrichment_status == STATUS_READY,
            SrsState.status == "new",
        )
    )
    new_reserve = int(new_reserve_q.scalar_one())

    learning_q = await db.execute(
        select(func.count())
        .select_from(SrsState)
        .join(LearningCard, LearningCard.id == SrsState.card_id)
        .where(
            *srs_base,
            SrsState.status == "learning",
        )
    )
    # short-interval reviews also count as "w nauce"
    short_review_q = await db.execute(
        select(func.count())
        .select_from(SrsState)
        .join(LearningCard, LearningCard.id == SrsState.card_id)
        .where(
            *srs_base,
            SrsState.status == "review",
            SrsState.interval_days < mastered_interval,
        )
    )
    srs_learning = int(learning_q.scalar_one()) + int(short_review_q.scalar_one())

    mastered_q = await db.execute(
        select(func.count())
        .select_from(SrsState)
        .join(LearningCard, LearningCard.id == SrsState.card_id)
        .where(
            *srs_base,
            SrsState.status == "review",
            SrsState.interval_days >= mastered_interval,
        )
    )
    srs_mastered = int(mastered_q.scalar_one())

    # first review today ≈ new cards studied today
    first_review_sq = (
        select(
            ReviewLog.card_id.label("card_id"),
            func.min(ReviewLog.reviewed_at).label("first_at"),
        )
        .join(LearningCard, LearningCard.id == ReviewLog.card_id)
        .where(
            ReviewLog.user_id == user.id,
            LearningCard.profile_id == profile.id,
            LearningCard.deck_id.is_(None),
        )
        .group_by(ReviewLog.card_id)
        .subquery()
    )
    new_done_q = await db.execute(
        select(func.count()).select_from(first_review_sq).where(first_review_sq.c.first_at >= today_start)
    )
    new_done_today = int(new_done_q.scalar_one())
    new_remaining = max(0, new_limit - new_done_today)

    reviews_today_q = await db.execute(
        select(func.count())
        .select_from(ReviewLog)
        .join(LearningCard, LearningCard.id == ReviewLog.card_id)
        .where(
            ReviewLog.user_id == user.id,
            LearningCard.profile_id == profile.id,
            LearningCard.deck_id.is_(None),
            ReviewLog.reviewed_at >= today_start,
        )
    )
    reviews_done_today = int(reviews_today_q.scalar_one())

    total_q = await db.execute(
        select(func.count())
        .select_from(LearningCard)
        .where(*learning_filter)
    )
    cards_total = int(total_q.scalar_one())

    # 7 dni: dziś … +6; etykieta = skrót dnia tygodnia (pn–nd)
    weekday_pl = ("pn", "wt", "śr", "cz", "pt", "so", "nd")
    forecast: list[DashboardForecastDay] = []
    for offset in range(7):
        day_start = today_start + timedelta(days=offset)
        day_end = day_start + timedelta(days=1)
        fq = await db.execute(
            select(func.count())
            .select_from(SrsState)
            .join(LearningCard, LearningCard.id == SrsState.card_id)
            .where(
                *srs_base,
                LearningCard.enrichment_status == STATUS_READY,
                SrsState.status.in_(["learning", "review", "relearning"]),
                SrsState.next_review_at.is_not(None),
                SrsState.next_review_at >= day_start,
                SrsState.next_review_at < day_end,
            )
        )
        forecast.append(
            DashboardForecastDay(
                day_offset=offset,
                label=weekday_pl[day_start.weekday()],
                due_count=int(fq.scalar_one()),
            )
        )

    last_added_q = await db.execute(
        select(func.max(LearningCard.created_at)).where(*learning_filter)
    )
    last_reviewed_q = await db.execute(
        select(func.max(ReviewLog.reviewed_at))
        .select_from(ReviewLog)
        .join(LearningCard, LearningCard.id == ReviewLog.card_id)
        .where(
            ReviewLog.user_id == user.id,
            LearningCard.profile_id == profile.id,
            LearningCard.deck_id.is_(None),
        )
    )

    return DashboardStatsResponse(
        due_count=due_count,
        new_remaining=new_remaining,
        new_done_today=new_done_today,
        new_limit=new_limit,
        reviews_done_today=reviews_done_today,
        done_today=reviews_done_today,
        srs_new=new_reserve,
        srs_due=due_count,
        srs_learning=srs_learning,
        srs_mastered=srs_mastered,
        new_reserve=new_reserve,
        cards_total=cards_total,
        forecast=forecast,
        last_added_at=last_added_q.scalar_one_or_none(),
        last_reviewed_at=last_reviewed_q.scalar_one_or_none(),
        new_today=new_done_today,
        reviews_in_period=reviews_done_today,
        avg_words_per_day=float(new_done_today),
        period_days=days,
    )

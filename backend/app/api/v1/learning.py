import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, normalize_text
from app.core.http_errors import api_error
from app.db.session import get_db
from app.models import CardCorrection, CardHistoryEvent, LanguageProfile, LearningCard, LexicalEntry, ReviewLog, SrsState, User, UserSettings, WordList
from app.schemas import (
    CardCreateRequest,
    CardCorrectionCreate,
    CardCorrectionCreateResponse,
    CardCorrectionResponse,
    CorrectionQuotaResponse,
    CardHistoryEventResponse,
    CardHistoryResponse,
    CardResponse,
    CardRestoreRequest,
    CardSelfEditRequest,
    SelfEditValidateResponse,
    DashboardForecastDay,
    DashboardStatsResponse,
    ImportDisplayCommitRequest,
    ImportDisplayCommitResponse,
    ImportDisplayResponse,
    ImportIngestRequest,
    ImportValidateRequest,
    ImportValidateResponse,
    ImportValidWord,
    LookupCandidate,
    LookupRequest,
    LookupResponse,
    ReviewRequest,
    ReviewResponse,
    SrsUndoRequest,
    SrsUndoResponse,
    SyncSrsState,
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
from app.services.card_corrections import (
    CORRECTION_DAILY_LIMIT,
    apply_self_edit_content,
    count_corrections_today,
    create_correction_submitted_event,
    create_self_edit_history_event,
    history_event_response,
    process_correction,
    restore_card_from_history,
    review_self_edit,
    validate_self_edit_before_save,
    _validate_sections,
)
from app.services.card_jobs import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_READY,
    build_import_display_content,
    build_pending_content,
    content_is_complete,
    hydrate_from_lexical_cache,
    request_manual_enrichment_retry,
    spawn_enrich,
)
from app.services.distractors import generate_choice_options
from app.services.import_ai import resolve_import_words
from app.services.import_classify import resolve_import_vocabulario_entries
from app.services.import_display import resolve_import_display_cards
from app.services.import_package import ImportPackageError, load_raw_import, load_text_import
from app.services.import_urls import ImportUrlError, detect_import_url, fetch_words_from_url
from app.services.lexical import LexicalService
from app.services.lookup_candidates import has_confident_match
from app.services.similar_words import ensure_similar_words
from app.services.srs import apply_review
from app.services.word_lists import (
    RESERVED_LIST_NAMES,
    ensure_pending_inbox_list,
    ensure_system_list,
    find_card_anywhere,
    list_word_lists,
)
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
        raise api_error(400, "no_active_profile", "No active language profile")
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
            learning_card_id=UUID(c["learning_card_id"]) if c.get("learning_card_id") else None,
            list_id=UUID(c["list_id"]) if c.get("list_id") else None,
            list_name=c.get("list_name"),
            enrichment_status=c.get("enrichment_status"),
        )
        for c in raw
    ]
    confident = has_confident_match(raw, body.text)
    await db.commit()
    return LookupResponse(candidates=candidates, source=source, confident=confident)


def _import_validate_response(valid_raw: list[dict], invalid: list[str]) -> ImportValidateResponse:
    valid = [
        ImportValidWord(
            input=v["input"],
            lemma=v["lemma"],
            pos=v.get("pos"),
            gloss=v.get("gloss") or "",
            lexical_entry_id=UUID(v["lexical_entry_id"]) if v.get("lexical_entry_id") else None,
            entry_kind=v.get("entry_kind") or "lemma",
            base_lemma=v.get("base_lemma"),
            pattern=v.get("pattern"),
        )
        for v in valid_raw
    ]
    return ImportValidateResponse(valid=valid, invalid=invalid, mode="vocabulario")


@router.post("/imports/validate", response_model=ImportValidateResponse)
async def validate_import_words(
    body: ImportValidateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exact L1/L2 headwords only — no typo tolerance / autocorrect."""
    service = LexicalService(db)
    try:
        valid_raw, invalid = await service.validate_import_words(
            user, body.profile_id, body.words
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return _import_validate_response(valid_raw, invalid)


@router.post("/imports/ingest")
async def ingest_import_text(
    body: ImportIngestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Wklejka: URL Quizlet/AnkiWeb albo tekst.

    mode=vocabulario → klasyfikacja + bogate karty (słowa/zwroty/konstrukcje)
    mode=preserve → fiszki z layoutem UI (bez enrichmentu słownikowego)
    """
    service = LexicalService(db)
    mode = (body.mode or "vocabulario").strip().lower()
    url = detect_import_url(body.text)
    try:
        if mode == "preserve":
            if url:
                raise api_error(400, "import_preserve_no_url", "Preserve-cards mode works with paste/file, not a URL.")
            profile = await service.get_profile(user.id, body.profile_id)
            deck = load_text_import(body.text)
            result = await resolve_import_display_cards(
                deck,
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
            )
            await db.commit()
            return ImportDisplayResponse(**result)

        if url:
            words = await fetch_words_from_url(url)
            if not words:
                raise api_error(400, "import_empty", "No words to import")
            valid_raw, invalid = await service.validate_import_words(
                user, body.profile_id, words
            )
        else:
            profile = await service.get_profile(user.id, body.profile_id)
            deck = load_text_import(body.text)
            valid_raw, invalid = await resolve_import_vocabulario_entries(
                deck,
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
            )
            if not valid_raw and not invalid:
                raise api_error(400, "import_empty", "No words to import")
    except ImportPackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return _import_validate_response(valid_raw, invalid)


@router.post("/imports/file")
async def ingest_import_file(
    profile_id: UUID = Form(...),
    mode: str = Form("vocabulario"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import z pliku. mode=vocabulario|preserve."""
    data = await file.read()
    service = LexicalService(db)
    mode_n = (mode or "vocabulario").strip().lower()
    try:
        profile = await service.get_profile(user.id, profile_id)
        deck = load_raw_import(file.filename, data)
        if mode_n == "preserve":
            result = await resolve_import_display_cards(
                deck,
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
            )
            await db.commit()
            return ImportDisplayResponse(**result)

        valid_raw, invalid = await resolve_import_vocabulario_entries(
            deck,
            app_lang=profile.app_lang,
            learning_lang=profile.learning_lang,
        )
        if not valid_raw and not invalid:
            raise api_error(400, "import_empty", "No words to import")
    except ImportPackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return _import_validate_response(valid_raw, invalid)


@router.post("/imports/commit-display", response_model=ImportDisplayCommitResponse)
async def commit_import_display(
    body: ImportDisplayCommitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Zapisuje fiszki import_display.v1 na listę — bez enrichmentu AI."""
    profile = await _active_profile(db, user.id, body.profile_id)
    result = await db.execute(
        select(WordList).where(
            WordList.id == body.list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
            WordList.deleted_at.is_(None),
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise api_error(404, "list_not_found", "List not found")

    created = 0
    skipped = 0
    for card_in in body.cards:
        lemma = (card_in.lemma_l2 or "").strip()
        if not lemma:
            skipped += 1
            continue
        existing = await find_card_anywhere(db, user.id, profile.id, lemma, "imported")
        if existing is not None:
            # ta sama lista → skip; inna lista też skip (reguła jak dziś)
            skipped += 1
            continue
        content = build_import_display_content(
            lemma=lemma,
            gloss=card_in.gloss_primary,
            learning_lang=profile.learning_lang,
            display=card_in.display.model_dump(),
        )
        if wl.is_system:
            card = LearningCard(
                user_id=user.id,
                profile_id=profile.id,
                lemma_l2=lemma,
                pos="imported",
                gloss_primary=card_in.gloss_primary,
                content=content,
                enrichment_status=STATUS_READY,
            )
            db.add(card)
            await db.flush()
            db.add(SrsState(card_id=card.id, scope="main", status="new"))
        else:
            card = LearningCard(
                user_id=user.id,
                profile_id=profile.id,
                deck_id=wl.id,
                lemma_l2=lemma,
                pos="imported",
                gloss_primary=card_in.gloss_primary,
                content=content,
                enrichment_status=STATUS_READY,
            )
            db.add(card)
            await db.flush()
        created += 1

    await db.commit()
    return ImportDisplayCommitResponse(
        created=created, skipped=skipped, list_id=wl.id
    )


@router.post("/cards", response_model=CardResponse, status_code=201)
async def create_card(
    body: CardCreateRequest,
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
        raise api_error(409, "word_already_on_list", "This word is already on the list")

    card = LearningCard(
        user_id=user.id,
        profile_id=profile.id,
        lemma_l2=body.lemma,
        pos=body.pos,
        gloss_primary=body.gloss,
        lexical_entry_id=body.lexical_entry_id,
        content=build_pending_content(
            lemma=body.lemma,
            pos=body.pos,
            gloss=body.gloss,
            learning_lang=profile.learning_lang,
            entry_kind=getattr(body, "entry_kind", None) or "lemma",
            base_lemma=getattr(body, "base_lemma", None),
            pattern=getattr(body, "pattern", None),
        ),
        enrichment_status=STATUS_PENDING,
    )
    db.add(card)
    await db.flush()
    db.add(SrsState(card_id=card.id, scope="main", status="new"))
    await hydrate_from_lexical_cache(db, card, profile)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise api_error(409, "word_already_on_list", "This word is already on the list") from exc
    await db.refresh(card)

    if card.enrichment_status == STATUS_PENDING:
        spawn_enrich(card.id)
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
            LearningCard.deleted_at.is_(None),
        ).order_by(LearningCard.created_at.desc())
    )
    return list(result.scalars().all())


def _resolve_direction(settings: UserSettings) -> str:
    pref = settings.practice_direction
    if pref == "random":
        return random.choice(["l2_to_l1", "l1_to_l2"])
    return pref


def _card_queue_direction(settings: UserSettings, content: dict | None) -> str:
    """Preserve cards with bidirectional=false always practice L2→L1."""
    display = (content or {}).get("display") if isinstance(content, dict) else None
    if isinstance(display, dict) and display.get("bidirectional") is False:
        return "l2_to_l1"
    if (content or {}).get("schema_version") == "import_display.v1":
        # Missing flag → treat as unidirectional.
        if not isinstance(display, dict) or "bidirectional" not in display:
            return "l2_to_l1"
        if not display.get("bidirectional"):
            return "l2_to_l1"
    return _resolve_direction(settings)


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
            LearningCard.deleted_at.is_(None),
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
        card_direction = _card_queue_direction(settings, card.content)
        items.append(
            SrsQueueItem(
                card_id=card.id,
                lemma_l2=card.lemma_l2,
                gloss_primary=card.gloss_primary,
                content=card.content,
                status=state.status,
                direction=card_direction,
                card_activity_status=card.card_activity_status,
                has_content_changes=bool(card.has_content_changes),
            )
        )

    new_limit = settings.new_cards_per_day if settings.new_cards_per_day > 0 else None
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    first_review_sq = (
        select(
            ReviewLog.card_id.label("card_id"),
            func.min(ReviewLog.reviewed_at).label("first_at"),
        )
        .join(LearningCard, LearningCard.id == ReviewLog.card_id)
        .where(
            ReviewLog.user_id == user.id,
            LearningCard.profile_id == profile_id,
            LearningCard.deck_id.is_(None),
            LearningCard.deleted_at.is_(None),
        )
        .group_by(ReviewLog.card_id)
        .subquery()
    )
    new_done_q = await db.execute(
        select(func.count()).select_from(first_review_sq).where(first_review_sq.c.first_at >= today_start)
    )
    new_done_today = int(new_done_q.scalar_one())
    new_query = (
        select(LearningCard, SrsState)
        .join(SrsState, SrsState.card_id == LearningCard.id)
        .where(
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile_id,
            LearningCard.deck_id.is_(None),
            LearningCard.deleted_at.is_(None),
            LearningCard.enrichment_status == STATUS_READY,
            SrsState.scope == "main",
            SrsState.status == "new",
        )
    )
    if new_limit is not None:
        new_query = new_query.limit(max(0, new_limit - new_done_today))
    new_result = await db.execute(new_query)
    new_items = []
    for card, state in new_result.all():
        card_direction = _card_queue_direction(settings, card.content)
        new_items.append(
            SrsQueueItem(
                card_id=card.id,
                lemma_l2=card.lemma_l2,
                gloss_primary=card.gloss_primary,
                content=card.content,
                status=state.status,
                direction=card_direction,
                card_activity_status=card.card_activity_status,
                has_content_changes=bool(card.has_content_changes),
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
            LearningCard.deleted_at.is_(None),
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise api_error(404, "card_not_found", "Card not found")

    profile_result = await db.execute(
        select(LanguageProfile).where(
            LanguageProfile.id == body.profile_id,
            LanguageProfile.user_id == user.id,
        )
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise api_error(404, "profile_not_found", "Profile not found")

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
        raise api_error(404, "card_not_found", "Card not found")
    card, state = row

    tolerance = "tolerate"

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


def _apply_sync_srs_to_state(state: SrsState, srs: SyncSrsState) -> SrsState:
    state.status = srs.status
    state.ease = srs.ease
    state.interval_days = srs.interval_days
    state.repetitions = srs.repetitions
    state.lapses = srs.lapses
    state.next_review_at = srs.next_review_at
    state.last_reviewed_at = srs.last_reviewed_at
    state.last_grade = srs.last_grade
    state.stability = srs.stability
    state.difficulty = srs.difficulty
    state.fsrs_step = srs.fsrs_step
    return state


def _srs_state_to_sync(card_id: UUID, state: SrsState) -> SyncSrsState:
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


@router.post("/srs/undo", response_model=SrsUndoResponse)
async def srs_undo(
    body: SrsUndoRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_id = body.previous_srs.card_id
    result = await db.execute(
        select(LearningCard, SrsState)
        .join(SrsState, SrsState.card_id == LearningCard.id)
        .where(
            LearningCard.id == card_id,
            LearningCard.user_id == user.id,
            SrsState.scope == "main",
        )
    )
    row = result.one_or_none()
    if row is None:
        raise api_error(404, "card_not_found", "Card not found")
    card, state = row

    log_result = await db.execute(
        select(ReviewLog).where(
            ReviewLog.client_id == body.client_id,
            ReviewLog.user_id == user.id,
        )
    )
    log = log_result.scalar_one_or_none()
    if log is not None:
        if log.card_id != card.id:
            raise HTTPException(status_code=400, detail="client_id does not match card")
        await db.delete(log)

    _apply_sync_srs_to_state(state, body.previous_srs)
    await db.commit()
    await db.refresh(state)
    return SrsUndoResponse(srs=_srs_state_to_sync(card.id, state))


@router.post("/srs/check-answer", response_model=CheckAnswerResponse)
async def check_typed_answer(
    body: CheckAnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_id = UUID(body.card_id)
    result = await db.execute(
        select(LearningCard).where(
            LearningCard.id == card_id,
            LearningCard.user_id == user.id,
            LearningCard.deleted_at.is_(None),
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise api_error(404, "card_not_found", "Card not found")

    tolerance = "tolerate"

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
            is_pending_inbox=bool(getattr(wl, "is_pending_inbox", False)),
            word_count=count,
            created_at=wl.created_at,
        )
        for wl, count in rows
    ]


@router.post("/lists/pending-inbox/ensure", response_model=WordListResponse)
async def ensure_pending_inbox(
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, profile_id)
    wl = await ensure_pending_inbox_list(db, user.id, profile.id)
    count_q = await db.execute(
        select(func.count())
        .select_from(LearningCard)
        .where(
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile.id,
            LearningCard.deck_id == wl.id,
            LearningCard.deleted_at.is_(None),
        )
    )
    await db.commit()
    await db.refresh(wl)
    return WordListResponse(
        id=wl.id,
        name=wl.name,
        is_system=False,
        is_pending_inbox=True,
        word_count=int(count_q.scalar_one()),
        created_at=wl.created_at,
    )


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
        raise api_error(400, "empty_list_name", "List name is required")
    if name.lower() in RESERVED_LIST_NAMES:
        raise api_error(400, "list_name_reserved", "This name is reserved")
    existing = await db.execute(
        select(WordList).where(
            WordList.profile_id == profile.id,
            func.lower(WordList.name) == name.lower(),
            WordList.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise api_error(409, "list_name_taken", "A list with this name already exists")
    wl = WordList(
        user_id=user.id,
        profile_id=profile.id,
        name=name,
        is_system=False,
        is_pending_inbox=False,
    )
    db.add(wl)
    await db.commit()
    await db.refresh(wl)
    return WordListResponse(
        id=wl.id,
        name=wl.name,
        is_system=False,
        is_pending_inbox=wl.is_pending_inbox,
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
            WordList.deleted_at.is_(None),
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise api_error(404, "list_not_found", "List not found")
    if wl.is_system:
        raise api_error(400, "list_not_editable", "This list cannot be edited")
    name = body.name.strip()
    if not name:
        raise api_error(400, "empty_list_name", "List name is required")
    if name.lower() in RESERVED_LIST_NAMES:
        raise api_error(400, "list_name_reserved", "This name is reserved")
    clash = await db.execute(
        select(WordList).where(
            WordList.profile_id == profile.id,
            func.lower(WordList.name) == name.lower(),
            WordList.id != list_id,
            WordList.deleted_at.is_(None),
        )
    )
    if clash.scalar_one_or_none():
        raise api_error(409, "list_name_taken", "A list with this name already exists")
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
            LearningCard.deleted_at.is_(None),
        )
    )
    return WordListResponse(
        id=wl.id,
        name=wl.name,
        is_system=False,
        is_pending_inbox=bool(getattr(wl, "is_pending_inbox", False)),
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
            WordList.deleted_at.is_(None),
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        # Idempotent: already deleted → nothing to do (offline retry safe).
        return
    if wl.is_system or wl.is_pending_inbox:
        raise api_error(400, "list_not_deletable", "This list cannot be deleted")
    # Usunięcie listy soft-delete'uje też karty (nie wracają do „Uczę się”).
    now = datetime.now(UTC)
    cards = (
        await db.execute(
            select(LearningCard).where(
                LearningCard.user_id == user.id,
                LearningCard.profile_id == profile.id,
                LearningCard.deck_id == wl.id,
                LearningCard.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for card in cards:
        card.deleted_at = now
    wl.deleted_at = now
    await db.commit()


@router.post("/cards/{card_id}/retry-enrichment", response_model=CardResponse)
async def retry_card_enrichment(
    card_id: UUID,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ręczne ponowienie enrichmentu (max 3×) gdy status=prep_problem."""
    profile = await _active_profile(db, user.id, profile_id)
    result = await db.execute(
        select(LearningCard).where(
            LearningCard.id == card_id,
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile.id,
            LearningCard.deleted_at.is_(None),
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise api_error(404, "card_not_found", "Card not found")
    try:
        await request_manual_enrichment_retry(db, card)
    except ValueError as exc:
        code = str(exc)
        if code == "manual_retries_exhausted":
            raise api_error(
                409,
                "manual_retries_exhausted",
                "Maximum manual enrichment retries reached",
            ) from exc
        if code == "card_enrichment_failed":
            raise api_error(409, "card_enrichment_failed", "Card enrichment failed permanently") from exc
        raise api_error(409, "card_not_retryable", "Card is not awaiting enrichment retry") from exc
    await db.commit()
    await db.refresh(card)
    return card


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
            LearningCard.deleted_at.is_(None),
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        # Idempotent: already deleted → nothing to do (offline retry safe).
        return
    # Soft-delete = tombstone propagated via /sync/pull deleted_card_ids.
    card.deleted_at = datetime.now(UTC)
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
            LearningCard.deleted_at.is_(None),
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise api_error(404, "card_not_found", "Card not found")

    target_q = await db.execute(
        select(WordList).where(
            WordList.id == body.target_list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
            WordList.deleted_at.is_(None),
        )
    )
    target = target_q.scalar_one_or_none()
    if target is None:
        raise api_error(404, "target_list_not_found", "Target list not found")

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
        content_review_status=card.content_review_status,
        card_activity_status=card.card_activity_status,
        has_content_changes=bool(card.has_content_changes),
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
            WordList.deleted_at.is_(None),
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        return []
    if wl.is_system:
        cards_q = await db.execute(
            select(LearningCard)
            .where(
                LearningCard.user_id == user.id,
                LearningCard.profile_id == profile.id,
                LearningCard.deck_id.is_(None),
                LearningCard.deleted_at.is_(None),
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
                LearningCard.deleted_at.is_(None),
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _active_profile(db, user.id, body.profile_id)
    result = await db.execute(
        select(WordList).where(
            WordList.id == list_id,
            WordList.profile_id == profile.id,
            WordList.user_id == user.id,
            WordList.deleted_at.is_(None),
        )
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise api_error(404, "list_not_found", "List not found")

    lemma = body.lemma.strip()
    pos = body.pos
    gloss = body.gloss
    lexical_entry_id = body.lexical_entry_id
    # Jeśli klient przysłał JUŻ rozwiązaną propozycję (lexical_entry_id albo pos+gloss),
    # uszanuj ją w 100% — NIE re-resolvuj. Wcześniej „largo/adj/długi” było nadpisywane
    # przez best_lookup_candidate na „el largo/noun/długość”. Wybrana propozycja jest ostateczna.
    already_resolved = lexical_entry_id is not None or (bool(pos) and bool(gloss))
    if not already_resolved:
        # Normalizuj lemma dla surowych słów (offline „zloto” → „el oro”, „FIRANKA” → forma).
        resolved = await LexicalService(db).best_lookup_candidate(user, profile.id, lemma)
        if resolved:
            lemma = resolved.get("lemma") or lemma
            pos = resolved.get("pos") or pos
            gloss = resolved.get("gloss") or gloss
            if resolved.get("lexical_entry_id") and lexical_entry_id is None:
                lexical_entry_id = UUID(resolved["lexical_entry_id"])

    existing = await find_card_anywhere(db, user.id, profile.id, lemma, pos)
    if existing is not None:
        raise api_error(409, "word_already_on_list", "This word is already on the list")

    if wl.is_system:
        # Same as POST /cards
        card = LearningCard(
            user_id=user.id,
            profile_id=profile.id,
            lemma_l2=lemma,
            pos=pos,
            gloss_primary=gloss,
            lexical_entry_id=lexical_entry_id,
            content=build_pending_content(
                lemma=lemma,
                pos=pos,
                gloss=gloss,
                learning_lang=profile.learning_lang,
                entry_kind=body.entry_kind or "lemma",
                base_lemma=body.base_lemma,
                pattern=body.pattern,
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
            lemma_l2=lemma,
            pos=pos,
            gloss_primary=gloss,
            lexical_entry_id=lexical_entry_id,
            content=build_pending_content(
                lemma=lemma,
                pos=pos,
                gloss=gloss,
                learning_lang=profile.learning_lang,
                entry_kind=body.entry_kind or "lemma",
                base_lemma=body.base_lemma,
                pattern=body.pattern,
            ),
            enrichment_status=STATUS_PENDING,
        )
        db.add(card)
        await db.flush()

    await hydrate_from_lexical_cache(db, card, profile)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise api_error(409, "word_already_on_list", "This word is already on the list") from exc
    await db.refresh(card)
    if card.enrichment_status == STATUS_PENDING:
        spawn_enrich(card.id)
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
        LearningCard.deleted_at.is_(None),
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
            LearningCard.deleted_at.is_(None),
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
            LearningCard.deleted_at.is_(None),
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
            LearningCard.deleted_at.is_(None),
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


async def _user_card(
    db: AsyncSession,
    user_id: UUID,
    card_id: UUID,
    profile_id: UUID,
) -> LearningCard:
    profile = await _active_profile(db, user_id, profile_id)
    result = await db.execute(
        select(LearningCard).where(
            LearningCard.id == card_id,
            LearningCard.user_id == user_id,
            LearningCard.profile_id == profile.id,
            LearningCard.deleted_at.is_(None),
        )
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise api_error(404, "card_not_found", "Card not found")
    return card


@router.get("/corrections/quota", response_model=CorrectionQuotaResponse)
async def correction_quota(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    used = await count_corrections_today(db, user.id)
    return CorrectionQuotaResponse(
        used=used,
        limit=CORRECTION_DAILY_LIMIT,
        remaining=max(0, CORRECTION_DAILY_LIMIT - used),
    )


@router.post("/cards/{card_id}/corrections", response_model=CardCorrectionCreateResponse)
async def create_card_correction(
    card_id: UUID,
    body: CardCorrectionCreate,
    background_tasks: BackgroundTasks,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await _user_card(db, user.id, card_id, profile_id)
    used = await count_corrections_today(db, user.id)
    if used >= CORRECTION_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "correction_daily_limit",
                "limit": CORRECTION_DAILY_LIMIT,
                "message": f"Maximum {CORRECTION_DAILY_LIMIT} reports per day.",
            },
        )
    try:
        sections = _validate_sections(body.sections)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    correction = CardCorrection(
        user_id=user.id,
        card_id=card.id,
        sections=sections,
        note=(body.note or "").strip() or None,
        status="reported",
    )
    card.content_review_status = "correction_reported"
    card.card_activity_status = "correction_processing"
    db.add(correction)
    await create_correction_submitted_event(
        db,
        card=card,
        user_id=user.id,
        sections=sections,
        note=correction.note,
    )
    await db.commit()
    await db.refresh(correction)
    background_tasks.add_task(process_correction, correction.id)
    return CardCorrectionCreateResponse(correction_id=correction.id, status="reported")


@router.get("/cards/{card_id}/corrections/latest", response_model=CardCorrectionResponse | None)
async def latest_card_correction(
    card_id: UUID,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_card(db, user.id, card_id, profile_id)
    result = await db.execute(
        select(CardCorrection)
        .where(CardCorrection.card_id == card_id, CardCorrection.user_id == user.id)
        .order_by(CardCorrection.created_at.desc())
        .limit(1)
    )
    correction = result.scalar_one_or_none()
    if correction is None:
        return None
    return CardCorrectionResponse.model_validate(correction)


@router.post("/cards/{card_id}/self-edit/validate", response_model=SelfEditValidateResponse)
async def validate_self_edit_card(
    card_id: UUID,
    body: CardSelfEditRequest,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await _user_card(db, user.id, card_id, profile_id)
    profile = await db.get(LanguageProfile, profile_id)
    if profile is None:
        raise api_error(404, "profile_not_found", "Profile not found")
    try:
        result = await validate_self_edit_before_save(
            card=card,
            profile=profile,
            after_content=body.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SelfEditValidateResponse(**result)


@router.post("/cards/{card_id}/self-edit", response_model=CardResponse)
async def self_edit_card(
    card_id: UUID,
    body: CardSelfEditRequest,
    background_tasks: BackgroundTasks,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await _user_card(db, user.id, card_id, profile_id)
    try:
        before = apply_self_edit_content(card, body.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    event = await create_self_edit_history_event(db, card=card, user_id=user.id, before=before)
    await db.commit()
    await db.refresh(card)
    background_tasks.add_task(review_self_edit, event.id)
    srs_q = await db.execute(
        select(SrsState).where(SrsState.card_id == card.id, SrsState.scope == "main")
    )
    return _card_response(card, srs_q.scalar_one_or_none())


@router.get("/cards/{card_id}/history", response_model=CardHistoryResponse)
async def card_history(
    card_id: UUID,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_card(db, user.id, card_id, profile_id)
    result = await db.execute(
        select(CardHistoryEvent)
        .where(CardHistoryEvent.card_id == card_id, CardHistoryEvent.user_id == user.id)
        .order_by(CardHistoryEvent.created_at.desc())
    )
    events = list(result.scalars().all())
    asc_events = list(reversed(events))
    return CardHistoryResponse(
        events=[
            CardHistoryEventResponse(**history_event_response(e, asc_events))
            for e in events
        ]
    )


@router.post("/cards/{card_id}/restore", response_model=CardResponse)
async def restore_card(
    card_id: UUID,
    body: CardRestoreRequest,
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await _user_card(db, user.id, card_id, profile_id)
    try:
        await restore_card_from_history(
            db,
            card=card,
            user_id=user.id,
            history_event_id=body.history_event_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(card)
    srs_q = await db.execute(
        select(SrsState).where(SrsState.card_id == card.id, SrsState.scope == "main")
    )
    return _card_response(card, srs_q.scalar_one_or_none())

"""Lokalne endpointy testowe — tylko development."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import lang_pair_key
from app.db.session import get_db
from app.models import FavoriteWord, LanguageProfile, LearningCard, LexicalEntry, ReviewLog, SrsState, User
from app.services.card_jobs import STATUS_PENDING, build_pending_content, enrich_card
from app.services.distractors import generate_choice_options
from app.services.lexical import LexicalService
from app.services.word_persistence import words_persistence_enabled

router = APIRouter(prefix="/dev", tags=["dev"])


def _require_dev() -> None:
    if get_settings().environment != "development":
        raise HTTPException(status_code=404, detail="Not found")


def _entry_payload(entry) -> dict:
    content = entry.content if isinstance(entry.content, dict) else {}
    lang_pair = getattr(entry, "lang_pair", None)
    return {
        "id": str(entry.id),
        "lang_pair": lang_pair,
        "lemma_l2": entry.lemma_l2,
        "lemma_l1_primary": entry.lemma_l1_primary,
        "pos": entry.pos,
        "source": getattr(entry, "source", "ephemeral"),
        "usage_count": getattr(entry, "usage_count", 0),
        "content": content,
    }


def _card_payload(card: LearningCard) -> dict:
    return {
        "id": str(card.id),
        "lemma_l2": card.lemma_l2,
        "pos": card.pos,
        "gloss_primary": card.gloss_primary,
        "lexical_entry_id": str(card.lexical_entry_id) if card.lexical_entry_id else None,
        "enrichment_status": card.enrichment_status,
        "enrichment_error": card.enrichment_error,
        "content": card.content,
    }


async def _resolve_user_profile(
    db: AsyncSession,
    email: str | None,
    profile_id: UUID | None,
) -> tuple[User, LanguageProfile]:
    if email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail=f"User not found: {email}")
    else:
        result = await db.execute(select(User).order_by(User.created_at).limit(1))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=404,
                detail="Brak użytkownika w bazie — zarejestruj się w aplikacji najpierw",
            )

    if profile_id:
        result = await db.execute(
            select(LanguageProfile).where(
                LanguageProfile.id == profile_id,
                LanguageProfile.user_id == user.id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return user, profile

    result = await db.execute(
        select(LanguageProfile).where(
            LanguageProfile.user_id == user.id,
            LanguageProfile.is_active.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        result = await db.execute(
            select(LanguageProfile)
            .where(LanguageProfile.user_id == user.id)
            .order_by(LanguageProfile.last_used_at.desc().nullslast())
            .limit(1)
        )
        profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Brak profilu językowego dla użytkownika")
    return user, profile


@router.get("/search/{word}")
async def dev_search(
    word: str,
    email: str | None = Query(None, description="Email użytkownika (domyślnie: pierwszy w bazie)"),
    profile_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Lookup jak w aplikacji + pełny stan z bazy dla trafień."""
    _require_dev()
    user, profile = await _resolve_user_profile(db, email, profile_id)
    service = LexicalService(db)

    candidates, source = await service.lookup(user, profile.id, word)
    pair = lang_pair_key(profile.native_lang, profile.learning_lang)

    lemmas = [c["lemma"] for c in candidates if c.get("lemma")]
    lexical_entries: list[LexicalEntry] = []
    if lemmas:
        result = await db.execute(
            select(LexicalEntry).where(
                LexicalEntry.lang_pair == pair,
                LexicalEntry.lemma_l2.in_(lemmas),
            )
        )
        lexical_entries = list(result.scalars().all())

    learning_cards: list[LearningCard] = []
    if lemmas:
        result = await db.execute(
            select(LearningCard).where(
                LearningCard.user_id == user.id,
                LearningCard.profile_id == profile.id,
                LearningCard.lemma_l2.in_(lemmas),
            )
        )
        learning_cards = list(result.scalars().all())

    await db.commit()
    return {
        "query": word,
        "persist_words": words_persistence_enabled(),
        "user_email": user.email,
        "profile": {
            "id": str(profile.id),
            "native_lang": profile.native_lang,
            "learning_lang": profile.learning_lang,
            "cefr_level": profile.cefr_level,
        },
        "lookup": {"source": source, "candidates": candidates},
        "db": {
            "lexical_entries": [_entry_payload(e) for e in lexical_entries],
            "learning_cards": [_card_payload(c) for c in learning_cards],
        },
    }


@router.get("/add/{word}")
async def dev_add(
    word: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    pos: str | None = Query(None, description="Część mowy, np. verb"),
    gloss: str | None = Query(None, description="Tłumaczenie z lookupu"),
    email: str | None = Query(None),
    profile_id: UUID | None = Query(None),
    wait: bool = Query(
        False,
        description="true = poczekaj na pełny enrichment (jak kiedyś); false = PENDING + tło",
    ),
    preview_distractors: bool = Query(True, description="Pokaż 8 opcji do ćwiczeń (tylko wait=true)"),
):
    """Dodanie słowa jak ＋ w aplikacji. Domyślnie PENDING + enrichment w tle."""
    _require_dev()
    user, profile = await _resolve_user_profile(db, email, profile_id)

    if not words_persistence_enabled():
        service = LexicalService(db)
        try:
            entry = await service.get_or_create_entry(user, profile, word, pos, None)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "action": "preview_only",
            "persist_words": False,
            "lemma_l2": entry.lemma_l2,
            "user_email": user.email,
            "profile": {
                "id": str(profile.id),
                "native_lang": profile.native_lang,
                "learning_lang": profile.learning_lang,
            },
            "enrichment": _entry_payload(entry),
            "note": "Nic nie zapisano w bazie. Ustaw PERSIST_WORDS=true aby włączyć zapis. "
            "similar_words → enrichment.content.similar_words",
        }

    existing = await db.execute(
        select(LearningCard).where(
            LearningCard.user_id == user.id,
            LearningCard.profile_id == profile.id,
            LearningCard.lemma_l2 == word,
            LearningCard.deck_id.is_(None),
        )
    )
    card = existing.scalar_one_or_none()
    if card is not None:
        return {
            "action": "already_in_learning",
            "persist_words": True,
            "lemma_l2": card.lemma_l2,
            "user_email": user.email,
            "profile": {
                "id": str(profile.id),
                "native_lang": profile.native_lang,
                "learning_lang": profile.learning_lang,
            },
            "db": {"learning_card": _card_payload(card)},
            "note": f"enrichment_status={card.enrichment_status}",
        }

    if wait:
        service = LexicalService(db)
        try:
            entry = await service.get_or_create_entry(user, profile, word, pos, None)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        card = LearningCard(
            user_id=user.id,
            profile_id=profile.id,
            lexical_entry_id=entry.id,
            lemma_l2=entry.lemma_l2,
            pos=entry.pos,
            gloss_primary=entry.lemma_l1_primary,
            content=dict(entry.content or {}),
            enrichment_status="ready",
        )
        db.add(card)
        await db.flush()
        db.add(SrsState(card_id=card.id, scope="main", status="new"))
        distractors = None
        if preview_distractors:
            try:
                distractors = await generate_choice_options(
                    db, user.id, profile.id, card, "l2_to_l1", profile
                )
            except ValueError as exc:
                distractors = [{"error": str(exc)}]
        await db.commit()
        await db.refresh(card)
        return {
            "action": "created_sync",
            "persist_words": True,
            "lemma_l2": card.lemma_l2,
            "user_email": user.email,
            "profile": {
                "id": str(profile.id),
                "native_lang": profile.native_lang,
                "learning_lang": profile.learning_lang,
            },
            "db": {
                "lexical_entry": _entry_payload(entry),
                "learning_card": _card_payload(card),
            },
            "distractors_l2_to_l1": distractors,
        }

    card = LearningCard(
        user_id=user.id,
        profile_id=profile.id,
        lemma_l2=word,
        pos=pos,
        gloss_primary=gloss,
        content=build_pending_content(
            lemma=word,
            pos=pos,
            gloss=gloss,
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
    return {
        "action": "created_pending",
        "persist_words": True,
        "lemma_l2": card.lemma_l2,
        "user_email": user.email,
        "profile": {
            "id": str(profile.id),
            "native_lang": profile.native_lang,
            "learning_lang": profile.learning_lang,
        },
        "db": {"learning_card": _card_payload(card)},
        "note": "Karta PENDING — enrichment leci w tle. Odśwież listę kart za ~30–60 s. "
        "Albo użyj ?wait=true aby poczekać na pełną treść w tym requestcie.",
    }


@router.post("/clear-words")
async def dev_clear_words(db: AsyncSession = Depends(get_db)):
    """Usuwa wszystkie słówka z bazy (lexical + nauka + ulubione + SRS). Zostawia userów i profile."""
    _require_dev()
    review_result = await db.execute(select(ReviewLog))
    srs_result = await db.execute(select(SrsState))
    cards_result = await db.execute(select(LearningCard))
    fav_result = await db.execute(select(FavoriteWord))
    lex_result = await db.execute(select(LexicalEntry))

    counts = {
        "review_logs": len(list(review_result.scalars().all())),
        "srs_state": len(list(srs_result.scalars().all())),
        "learning_cards": len(list(cards_result.scalars().all())),
        "favorite_words": len(list(fav_result.scalars().all())),
        "lexical_entries": len(list(lex_result.scalars().all())),
    }

    await db.execute(delete(ReviewLog))
    await db.execute(delete(SrsState))
    await db.execute(delete(LearningCard))
    await db.execute(delete(FavoriteWord))
    await db.execute(delete(LexicalEntry))
    await db.commit()

    return {
        "cleared": True,
        "deleted": counts,
        "persist_words": words_persistence_enabled(),
    }

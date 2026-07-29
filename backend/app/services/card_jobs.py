"""Enrichment poza cyklem żądania.

Karta zapisuje się natychmiast ze statusem `pending`, więc użytkownik może dalej
korzystać z aplikacji. Pełną treść — znaczenia, przykłady, dystraktory,
koniugację — dociąga zadanie w tle i przestawia status na `ready`.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas.similar_words import MIN_SIMILAR_WORDS
from app.core.deps import lang_pair_key, normalize_text
from app.db.session import async_session_factory
from app.models import FavoriteWord, LanguageProfile, LearningCard, LexicalEntry
from app.services.enrichment import enrich_card_content
from app.services.similar_words import ensure_similar_words

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


def build_pending_content(
    *,
    lemma: str,
    pos: str | None,
    gloss: str | None,
    learning_lang: str,
) -> dict:
    """Minimalna treść karty z danych, które lookup zwrócił bez dodatkowego kosztu."""
    meanings = [{"gloss_l1": gloss, "synonyms_l1": [], "examples": [], "usages": []}] if gloss else []
    return {
        "schema_version": "1.0",
        "lemma": lemma,
        "language": learning_lang,
        "pos": pos,
        "ipa": None,
        "meanings": meanings,
        "synonyms_l2": [],
        "antonyms_l2": [],
        "similar_words": [],
        "conjugation": None,
    }


def content_is_complete(content: dict | None) -> bool:
    """Gotowa treść ma znaczenia z przykładami i pełny zestaw dystraktorów."""
    if not content:
        return False
    meanings = content.get("meanings") or []
    if not meanings:
        return False
    if not all(isinstance(m, dict) and m.get("examples") for m in meanings):
        return False
    return len(content.get("similar_words") or []) >= MIN_SIMILAR_WORDS


async def _find_ready_entry(
    db: AsyncSession,
    *,
    lang_pair: str,
    lemma: str,
    pos: str | None,
) -> LexicalEntry | None:
    stmt = select(LexicalEntry).where(
        LexicalEntry.lang_pair == lang_pair,
        LexicalEntry.lemma_l2.ilike(normalize_text(lemma)),
    )
    if pos:
        stmt = stmt.where(LexicalEntry.pos == pos)
    entry = (await db.execute(stmt)).scalars().first()
    return entry if entry and content_is_complete(entry.content) else None


async def _resolve_content(
    db: AsyncSession,
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    user_id: UUID | None,
) -> tuple[dict, LexicalEntry | None]:
    """Zwraca gotową treść — z bazy, jeśli ktoś już to słowo wzbogacił."""
    pair = lang_pair_key(profile.native_lang, profile.learning_lang)

    cached = await _find_ready_entry(db, lang_pair=pair, lemma=lemma, pos=pos)
    if cached is not None:
        cached.usage_count += 1
        return dict(cached.content), cached

    content = await enrich_card_content(profile, lemma, pos)
    content = await ensure_similar_words(
        content, profile, content.get("lemma") or lemma, content.get("pos") or pos
    )

    meanings = content.get("meanings") or []
    gloss = meanings[0].get("gloss_l1", "") if meanings else ""
    entry = LexicalEntry(
        lang_pair=pair,
        lemma_l2=content.get("lemma") or lemma,
        lemma_l1_primary=gloss,
        pos=content.get("pos") or pos,
        cefr=profile.cefr_level,
        content=content,
        source="ai",
        created_by_user_id=user_id,
        usage_count=1,
    )
    db.add(entry)
    await db.flush()
    return content, entry


async def enrich_card(card_id: UUID) -> None:
    """Zadanie w tle dla karty dodanej do nauki."""
    async with async_session_factory() as db:
        card = (
            await db.execute(select(LearningCard).where(LearningCard.id == card_id))
        ).scalar_one_or_none()
        if card is None or card.enrichment_status == STATUS_READY:
            return

        profile = (
            await db.execute(
                select(LanguageProfile).where(LanguageProfile.id == card.profile_id)
            )
        ).scalar_one_or_none()
        if profile is None:
            return

        try:
            content, entry = await _resolve_content(
                db, profile, card.lemma_l2, card.pos, user_id=card.user_id
            )
        except Exception as exc:
            logger.exception("Enrichment karty %s nie powiódł się", card_id)
            card.enrichment_status = STATUS_FAILED
            card.enrichment_error = str(exc)[:500]
            await db.commit()
            return

        meanings = content.get("meanings") or []
        card.content = content
        card.pos = content.get("pos") or card.pos
        card.gloss_primary = (
            meanings[0].get("gloss_l1") if meanings else card.gloss_primary
        )
        if entry is not None:
            card.lexical_entry_id = entry.id
        card.enrichment_status = STATUS_READY
        card.enrichment_error = None
        await db.commit()


async def enrich_favorite(favorite_id: UUID) -> None:
    """Zadanie w tle dla ulubionego — buduje wpis słownikowy na później."""
    async with async_session_factory() as db:
        favorite = (
            await db.execute(select(FavoriteWord).where(FavoriteWord.id == favorite_id))
        ).scalar_one_or_none()
        if favorite is None or favorite.enrichment_status == STATUS_READY:
            return

        profile = (
            await db.execute(
                select(LanguageProfile).where(LanguageProfile.id == favorite.profile_id)
            )
        ).scalar_one_or_none()
        if profile is None:
            return

        try:
            await _resolve_content(
                db, profile, favorite.lemma, favorite.pos, user_id=favorite.user_id
            )
        except Exception:
            logger.exception("Enrichment ulubionego %s nie powiódł się", favorite_id)
            favorite.enrichment_status = STATUS_FAILED
            await db.commit()
            return

        favorite.enrichment_status = STATUS_READY
        await db.commit()

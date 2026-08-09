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
from app.models import LanguageProfile, LearningCard, LexicalEntry, User
from app.services.enrichment import enrich_adaptive_card_content, enrich_card_content
from app.services.lexical import LexicalService
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
    entry_kind: str = "lemma",
    base_lemma: str | None = None,
    pattern: str | None = None,
) -> dict:
    """Minimalna treść karty z danych, które lookup zwrócił bez dodatkowego kosztu."""
    meanings = [{"gloss_l1": gloss, "synonyms_l1": [], "examples": [], "usages": []}] if gloss else []
    kind = (entry_kind or "lemma").strip().lower()
    base: dict = {
        "schema_version": "vocabulario.card.v1" if kind == "lemma" else "vocabulario.adaptive.v1",
        "lemma": lemma,
        "language": learning_lang,
        "pos": pos,
        "ipa": None,
        "meanings": meanings,
        "synonyms_l2": [],
        "antonyms_l2": [],
        "similar_words": [],
        "inflection": None,
        "conjugation": None,
    }
    if kind != "lemma":
        base["entry_kind"] = kind
        base["pattern"] = pattern
        base["related_lemma"] = base_lemma
        base["source_import"] = {
            "gloss_hint": gloss,
            "base_lemma": base_lemma,
            "pattern": pattern,
        }
    return base


def build_import_display_content(
    *,
    lemma: str,
    gloss: str | None,
    learning_lang: str,
    display: dict,
) -> dict:
    """Treść fiszki zachowanej z importu — gotowa do renderu bloków, bez enrichmentu."""
    return {
        "schema_version": "import_display.v1",
        "card_kind": "imported",
        "lemma": lemma,
        "language": learning_lang,
        "pos": "imported",
        "ipa": None,
        "meanings": (
            [{"gloss_l1": gloss, "synonyms_l1": [], "examples": [], "usages": []}]
            if gloss
            else []
        ),
        "synonyms_l2": [],
        "antonyms_l2": [],
        "similar_words": [],
        "conjugation": None,
        "display": display,
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
    # Adaptive: bez similar_words / conjugation
    if content.get("schema_version") == "vocabulario.adaptive.v1":
        return True
    if content.get("schema_version") == "vocabulario.card.v1":
        inf = content.get("inflection") or {}
        verbs = inf.get("verbs") if isinstance(inf, dict) else None
        has_inflection = isinstance(verbs, dict) and (
            verbs.get("tenses") or verbs.get("non_finite")
        )
        if content.get("pos") == "verb" and not has_inflection and not content.get("conjugation"):
            return False
        return len(content.get("similar_words") or []) >= MIN_SIMILAR_WORDS
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
    pair = lang_pair_key(profile.app_lang, profile.learning_lang)

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
        if card is None:
            return
        if card.enrichment_status == STATUS_READY and content_is_complete(card.content):
            return

        content0 = dict(card.content or {})
        if content0.get("schema_version") == "import_display.v1":
            card.enrichment_status = STATUS_READY
            card.enrichment_error = None
            await db.commit()
            from app.services.push import notify_cards_ready

            await notify_cards_ready(db, card.user_id)
            return

        profile = (
            await db.execute(
                select(LanguageProfile).where(LanguageProfile.id == card.profile_id)
            )
        ).scalar_one_or_none()
        if profile is None:
            return

        if not (card.gloss_primary or "").strip():
            user = (
                await db.execute(select(User).where(User.id == card.user_id))
            ).scalar_one_or_none()
            if user is not None:
                resolved = await LexicalService(db).best_lookup_candidate(
                    user, card.profile_id, card.lemma_l2
                )
                if resolved:
                    card.lemma_l2 = resolved.get("lemma") or card.lemma_l2
                    card.pos = resolved.get("pos") or card.pos
                    card.gloss_primary = resolved.get("gloss") or card.gloss_primary
                    if resolved.get("lexical_entry_id"):
                        card.lexical_entry_id = UUID(resolved["lexical_entry_id"])
                    card.content = build_pending_content(
                        lemma=card.lemma_l2,
                        pos=card.pos,
                        gloss=card.gloss_primary,
                        learning_lang=profile.learning_lang,
                    )
                    content0 = dict(card.content or {})

        try:
            entry_kind = (content0.get("entry_kind") or "lemma").strip().lower()
            schema0 = content0.get("schema_version") or "vocabulario.card.v1"
            if schema0 == "vocabulario.adaptive.v1" or entry_kind in {
                "phrase",
                "construction",
                "sentence",
                "other",
            }:
                src = content0.get("source_import") or {}
                content = await enrich_adaptive_card_content(
                    profile,
                    headword=card.lemma_l2,
                    entry_kind=entry_kind if entry_kind != "lemma" else "other",
                    gloss=card.gloss_primary or src.get("gloss_hint"),
                    pos=card.pos,
                    base_lemma=src.get("base_lemma") or content0.get("related_lemma"),
                    pattern=src.get("pattern") or content0.get("pattern"),
                )
                entry = None
            else:
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
        from app.services.push import notify_cards_ready

        await notify_cards_ready(db, card.user_id)

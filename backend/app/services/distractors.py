from __future__ import annotations

import random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lsp.lang_utils import articles_for
from app.models import LanguageProfile, LearningCard


def _lemma_key(raw: str | None, articles: frozenset[str]) -> str:
    lower = (raw or "").strip().lower()
    if not lower:
        return ""
    parts = lower.split()
    rest = " ".join(parts[1:]) if len(parts) > 1 and parts[0] in articles else lower
    return rest.removeprefix("l'").removeprefix("l’")


def lemma_keys(raw: str | None, articles: frozenset[str]) -> set[str]:
    exact = (raw or "").strip().lower()
    if not exact:
        return set()
    return {key for key in (exact, _lemma_key(exact, articles)) if key}


def in_learning_lemma(raw: str | None, learning_keys: set[str], articles: frozenset[str]) -> bool:
    keys = lemma_keys(raw, articles)
    return bool(keys and keys & learning_keys)


def similar_words_from_content(content: dict) -> list[dict]:
    raw = content.get("similar_words") or []
    result: list[dict] = []
    for item in raw:
        if isinstance(item, dict) and item.get("lemma"):
            result.append(item)
    return result


async def generate_choice_options(
    db: AsyncSession,
    user_id: UUID,
    profile_id: UUID,
    card: LearningCard,
    direction: str,
    profile: LanguageProfile,
) -> list[dict]:
    """Zawsze 8 opcji: 1 poprawna + do 3 z nauki (ta sama POS) + reszta z similar_words (12 z karty)."""
    content = card.content or {}
    similar_pool = [
        s
        for s in similar_words_from_content(content)
        if s.get("lemma", "").lower() != card.lemma_l2.lower()
    ]
    random.shuffle(similar_pool)

    result = await db.execute(
        select(LearningCard).where(
            LearningCard.user_id == user_id,
            LearningCard.profile_id == profile_id,
            LearningCard.id != card.id,
        )
    )
    others = list(result.scalars().all())
    same_pos = [c for c in others if c.pos == card.pos] if card.pos else list(others)
    articles = articles_for(profile.learning_lang)
    learning_keys: set[str] = set()
    for learned in others:
        learning_keys |= lemma_keys(learned.lemma_l2, articles)
    learning_keys |= lemma_keys(card.lemma_l2, articles)

    if direction == "l2_to_l1":
        correct_text = card.gloss_primary or ""

        def from_learned(c: LearningCard) -> dict:
            return {
                "text": c.gloss_primary or "?",
                "lemma_l2": c.lemma_l2,
                "gloss": c.gloss_primary,
                "pos": c.pos,
                "card_id": str(c.id),
                "in_learning": True,
            }

        def from_similar(s: dict) -> dict:
            gloss = s.get("gloss_l1") or "?"
            lemma = s.get("lemma") or "?"
            return {
                "text": gloss,
                "lemma_l2": lemma,
                "gloss": gloss,
                "pos": s.get("pos") or card.pos,
                "card_id": None,
                "in_learning": in_learning_lemma(lemma, learning_keys, articles),
            }
    else:
        correct_text = card.lemma_l2

        def from_learned(c: LearningCard) -> dict:
            return {
                "text": c.lemma_l2,
                "lemma_l2": c.lemma_l2,
                "gloss": c.gloss_primary,
                "pos": c.pos,
                "card_id": str(c.id),
                "in_learning": True,
            }

        def from_similar(s: dict) -> dict:
            lemma = s.get("lemma") or "?"
            return {
                "text": lemma,
                "lemma_l2": lemma,
                "gloss": s.get("gloss_l1"),
                "pos": s.get("pos") or card.pos,
                "card_id": None,
                "in_learning": in_learning_lemma(lemma, learning_keys, articles),
            }

    distractors: list[dict] = []
    used_texts: set[str] = {correct_text.lower()}

    def try_add(option: dict) -> bool:
        text = (option.get("text") or "").strip()
        if not text or text == "?" or text.lower() in used_texts:
            return False
        distractors.append(option)
        used_texts.add(text.lower())
        return True

    from_learning = random.sample(same_pos, min(3, len(same_pos)))
    for c in from_learning:
        try_add(from_learned(c))

    for s in similar_pool:
        if len(distractors) >= 7:
            break
        try_add(from_similar(s))

    if len(distractors) < 7:
        for s in similar_pool:
            if len(distractors) >= 7:
                break
            lemma = s.get("lemma") or "?"
            gloss = s.get("gloss_l1") or "?"
            if direction == "l2_to_l1":
                alt = f"{gloss} ({lemma})"
                opt = from_similar(s)
                opt["text"] = alt
                try_add(opt)
            else:
                try_add(from_similar(s))

    if len(distractors) < 7:
        raise ValueError(
            f"Karta „{card.lemma_l2}” nie ma wystarczającej listy similar_words "
            f"({len(similar_pool)} pozycji, potrzeba {7 - len(distractors)} więcej). "
            "Dodaj słowo ponownie lub uruchom uzupełnienie karty."
        )

    correct_option = {
        "text": correct_text,
        "lemma_l2": card.lemma_l2,
        "gloss": card.gloss_primary,
        "pos": card.pos,
        "card_id": str(card.id),
        "in_learning": True,
        "is_correct": True,
    }
    options = distractors[:7] + [correct_option]
    random.shuffle(options)
    return options

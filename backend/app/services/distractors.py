from __future__ import annotations

import random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LanguageProfile, LearningCard


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
                "in_learning": False,
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
                "in_learning": False,
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

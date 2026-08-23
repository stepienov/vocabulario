from __future__ import annotations

import random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lsp.lang_utils import articles_for
from app.models import LanguageProfile, LearningCard
from app.services.pos_normalize import normalize_pos_bucket


def _lemma_key(raw: str | None, articles: frozenset[str]) -> str:
    lower = (raw or "").strip().lower()
    if not lower:
        return ""
    parts = lower.split()
    rest = " ".join(parts[1:]) if len(parts) > 1 and parts[0] in articles else lower
    return rest.removeprefix("l'").removeprefix("l’").removeprefix("ال")


def lemma_keys(raw: str | None, articles: frozenset[str]) -> set[str]:
    exact = (raw or "").strip().lower()
    if not exact:
        return set()
    return {key for key in (exact, _lemma_key(exact, articles)) if key}


def in_learning_lemma(raw: str | None, learning_keys: set[str], articles: frozenset[str]) -> bool:
    keys = lemma_keys(raw, articles)
    return bool(keys and keys & learning_keys)


_VERBAL_QUIZ_POS = frozenset({"verb", "phrase", "construction"})
_PHRASE_LIKE_QUIZ_POS = frozenset({"phrase", "construction"})


def quiz_pos_matches(want_pos: str, candidate_pos: str | None, *, family: bool = False) -> bool:
    """Unknown never matches everything. Phrase/construction may fill from verbs."""
    want = normalize_pos_bucket(want_pos)
    got = normalize_pos_bucket(candidate_pos)
    if want == "unknown" or got == "unknown":
        return False
    if got == want:
        return True
    if not family:
        return False
    return want in _PHRASE_LIKE_QUIZ_POS and got in _VERBAL_QUIZ_POS


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
    want_pos = normalize_pos_bucket(card.pos)
    similar_all = [
        s
        for s in similar_words_from_content(content)
        if s.get("lemma", "").lower() != card.lemma_l2.lower()
    ]
    similar_exact = [s for s in similar_all if quiz_pos_matches(want_pos, s.get("pos"), family=False)]
    similar_family = [s for s in similar_all if quiz_pos_matches(want_pos, s.get("pos"), family=True)]
    random.shuffle(similar_exact)
    random.shuffle(similar_family)

    result = await db.execute(
        select(LearningCard).where(
            LearningCard.user_id == user_id,
            LearningCard.profile_id == profile_id,
            LearningCard.id != card.id,
        )
    )
    others = list(result.scalars().all())
    exact_pos = [c for c in others if quiz_pos_matches(want_pos, c.pos, family=False)]
    family_pos = [c for c in others if quiz_pos_matches(want_pos, c.pos, family=True)]
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

    from_learning = random.sample(exact_pos, min(3, len(exact_pos)))
    for c in from_learning:
        try_add(from_learned(c))

    def add_similar(pool: list[dict], *, alt_text: bool = False) -> None:
        for s in pool:
            if len(distractors) >= 7:
                break
            if not alt_text:
                try_add(from_similar(s))
                continue
            lemma = s.get("lemma") or "?"
            gloss = s.get("gloss_l1") or "?"
            if direction == "l2_to_l1":
                opt = from_similar(s)
                opt["text"] = f"{gloss} ({lemma})"
                try_add(opt)
            else:
                try_add(from_similar(s))

    add_similar(similar_exact)
    for c in exact_pos:
        if len(distractors) >= 7:
            break
        try_add(from_learned(c))
    add_similar(similar_family)
    for c in family_pos:
        if len(distractors) >= 7:
            break
        try_add(from_learned(c))
    if len(distractors) < 7:
        add_similar(similar_exact, alt_text=True)

    if len(distractors) < 7:
        raise ValueError(
            f"Karta „{card.lemma_l2}” nie ma wystarczającej listy similar_words "
            f"({len(similar_exact)} pozycji, potrzeba {7 - len(distractors)} więcej). "
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

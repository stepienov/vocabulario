from __future__ import annotations

from app.ai.schemas.similar_words import (
    FILL_POOL_SIZE,
    MIN_SIMILAR_FOR_QUIZ,
    MIN_SIMILAR_WORDS,
)
from app.models import LanguageProfile
from app.services.llm import LLMService


def _clean_lemma(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_entry(item: dict, pos: str | None) -> dict | None:
    lemma = _clean_lemma(item.get("lemma"))
    if not lemma or any(char.isdigit() for char in lemma):
        return None
    entry = {
        "lemma": lemma,
        "gloss_l1": item.get("gloss_l1") or item.get("gloss") or "?",
    }
    resolved_pos = item.get("pos") or pos
    if resolved_pos:
        entry["pos"] = resolved_pos
    return entry


def _collect(
    batches: list[list[dict]],
    target_lemma: str,
    pos: str | None,
    *,
    limit: int,
) -> list[dict]:
    """Scala partie w unikalną listę — bez słowa docelowego i bez powtórzeń."""
    seen = {target_lemma.strip().lower()}
    collected: list[dict] = []
    for batch in batches:
        for item in batch:
            if not isinstance(item, dict):
                continue
            entry = _as_entry(item, pos)
            if entry is None:
                continue
            key = entry["lemma"].lower()
            if key in seen:
                continue
            seen.add(key)
            collected.append(entry)
            if len(collected) >= limit:
                return collected
    return collected


def similar_words_from_content(content: dict) -> list[dict]:
    raw = content.get("similar_words") or []
    result: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("lemma"):
            continue
        entry = {
            "lemma": item["lemma"],
            "gloss_l1": item.get("gloss_l1") or item.get("gloss") or "?",
        }
        if item.get("pos"):
            entry["pos"] = item["pos"]
        result.append(entry)
    return result


def sanitize_similar_words(
    items: list[dict],
    target_lemma: str,
    pos: str | None,
) -> list[dict]:
    return _collect([items], target_lemma, pos, limit=MIN_SIMILAR_WORDS)


async def fetch_similar_words(
    llm: LLMService,
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
) -> list[dict]:
    """Jedno zapytanie o 12 dystraktorów; gdy któryś wypadnie po deduplikacji,
    brakujące pozycje bierzemy z awaryjnej puli słów."""
    pos_val = pos or "unknown"

    similar = await llm.generate_similar_words(
        lemma=lemma,
        pos=pos_val,
        native=profile.app_lang,
        learning=profile.learning_lang,
        count=MIN_SIMILAR_WORDS,
    )
    collected = _collect([similar], lemma, pos_val, limit=MIN_SIMILAR_WORDS)
    if len(collected) >= MIN_SIMILAR_WORDS:
        return collected

    pool = await llm.generate_filler_words(
        pos=pos_val,
        native=profile.app_lang,
        learning=profile.learning_lang,
        exclude=[lemma, *(item["lemma"] for item in collected)],
        count=FILL_POOL_SIZE,
    )
    return _collect([collected, pool], lemma, pos_val, limit=MIN_SIMILAR_WORDS)


async def ensure_similar_words(
    content: dict,
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
) -> dict:
    """Gwarantuje 12 dystraktorów w content — przy dodawaniu / odświeżaniu karty."""
    updated = dict(content or {})
    pos_val = pos or "unknown"

    existing = _collect(
        [similar_words_from_content(updated)], lemma, pos_val, limit=MIN_SIMILAR_WORDS
    )
    if len(existing) >= MIN_SIMILAR_WORDS:
        updated["similar_words"] = existing
        return updated

    fetched = await fetch_similar_words(LLMService(), profile, lemma, pos)
    if len(fetched) < MIN_SIMILAR_FOR_QUIZ:
        raise ValueError(
            f"AI zwróciło za mało dystraktorów dla „{lemma}” "
            f"({len(fetched)}/{MIN_SIMILAR_FOR_QUIZ}). Spróbuj ponownie."
        )

    updated["similar_words"] = fetched
    return updated

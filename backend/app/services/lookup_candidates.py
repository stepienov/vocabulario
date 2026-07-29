"""Walidacja kandydatów z lookup — tylko pojedyncze lematy."""

from __future__ import annotations

_ARTICLES = frozenset({"el", "la", "los", "las"})


def _normalize_lemma(lemma: str) -> str:
    return " ".join(lemma.lower().split())


def sanitize_lookup_candidates(candidates: list[dict]) -> list[dict]:
    """Odrzuca zwroty, peryfrazy i duplikaty noun z/bez rodzajnika."""
    cleaned: list[dict] = []
    seen: set[tuple[str, str | None]] = set()
    nouns_with_article: set[str] = set()

    for item in candidates:
        if not isinstance(item, dict):
            continue
        lemma = (item.get("lemma") or "").strip()
        pos = item.get("pos")
        gloss = (item.get("gloss") or "").strip()
        if not lemma or not gloss:
            continue

        words = lemma.split()
        pos_lower = (pos or "").lower()

        if pos_lower == "verb" and len(words) != 1:
            continue

        if pos_lower == "noun":
            if len(words) == 1:
                continue
            if len(words) != 2 or words[0].lower() not in _ARTICLES:
                continue
            nouns_with_article.add(words[1].lower())

        if len(words) > 2:
            continue

        if pos_lower != "noun" and len(words) > 1:
            continue

        key = (_normalize_lemma(lemma), pos_lower or None)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    final: list[dict] = []
    for item in cleaned:
        lemma = item.get("lemma", "")
        pos_lower = (item.get("pos") or "").lower()
        words = lemma.split()
        if pos_lower == "noun" and len(words) == 1:
            continue
        if pos_lower != "noun" and len(words) == 1 and words[0].lower() in nouns_with_article:
            continue
        final.append(item)

    return final[:8]

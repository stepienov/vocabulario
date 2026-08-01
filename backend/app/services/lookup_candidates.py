"""Walidacja kandydatów z lookup — tylko pojedyncze lematy."""

from __future__ import annotations

_ARTICLES = frozenset({"el", "la", "los", "las"})


def _normalize_lemma(lemma: str) -> str:
    return " ".join(lemma.lower().split())


def sanitize_lookup_candidates(candidates: list[dict]) -> list[dict]:
    """Odrzuca zwroty, peryfrazy i gołe rzeczowniki bez rodzajnika."""
    cleaned: list[dict] = []
    seen: set[tuple[str, str | None]] = set()

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
            # Rzeczownik musi mieć rodzajnik: "el contar", nie samo "contar".
            if len(words) != 2 or words[0].lower() not in _ARTICLES:
                continue
        elif len(words) != 1:
            continue

        if len(words) > 2:
            continue

        key = (_normalize_lemma(lemma), pos_lower or None)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    return cleaned[:8]



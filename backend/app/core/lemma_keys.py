"""Jedyny klucz lookupu enrichmentu w PG: para języków + znormalizowane lematy.

Zapis i odczyt MUSZĄ używać tej samej funkcji. Inaczej „el resultado”
nie trafia w „resultado (efecto)” / „le résultat” i leci płatny OpenAI.
"""

from __future__ import annotations

import re
import unicodedata

# Artykuły wszystkich L2, które aplikacja obsługuje — zdejmujemy z CZOŁA, nie ze środka.
_ARTICLES = frozenset(
    {
        "el",
        "la",
        "los",
        "las",
        "le",
        "les",
        "un",
        "une",
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "the",
        "a",
        "an",
        "il",
        "lo",
        "i",
        "gli",
        "o",
        "os",
        "as",
        "l",
    }
)
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_APOS_PREFIX = re.compile(r"^l['’]\s*")
_SPACE = re.compile(r"\s+")


def canonical_lemma(raw: str | None) -> str:
    """Stabilny klucz: lower, bez nawiasów, bez interpunkcji, bez artykułu na początku."""
    text = (raw or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _PAREN.sub(" ", text)
    text = "".join(
        ch if unicodedata.category(ch)[0] in "LMN" or ch in " '\u2019" else " " for ch in text
    )
    text = _SPACE.sub(" ", text).strip()
    text = _APOS_PREFIX.sub("", text).strip()
    parts = text.split()
    while parts and parts[0] in _ARTICLES:
        parts = parts[1:]
        if parts:
            joined = " ".join(parts)
            stripped = _APOS_PREFIX.sub("", joined).strip()
            parts = stripped.split() if stripped else []
    return " ".join(parts)


def cache_lookup_keys(*texts: str | None) -> set[str]:
    return {canonical_lemma(t) for t in texts if canonical_lemma(t)}

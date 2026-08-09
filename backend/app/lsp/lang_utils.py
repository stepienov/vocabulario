"""Typologia językowa LSP (16 kodów) — artykuły, przyimki do importu/lookup."""

from __future__ import annotations

from app.lsp.constants import SUPPORTED_L2_LANGS, normalize_l2_code

_ARTICLES: dict[str, frozenset[str]] = {
    "en": frozenset({"a", "an", "the"}),
    "es": frozenset({"el", "la", "los", "las"}),
    "fr": frozenset({"le", "la", "les", "un", "une"}),
    "de": frozenset({"der", "die", "das", "ein", "eine"}),
    "it": frozenset({"il", "lo", "la", "i", "gli", "le", "l"}),
    "pt-br": frozenset({"o", "a", "os", "as"}),
    "pt-pt": frozenset({"o", "a", "os", "as"}),
    "ar": frozenset({"ال", "و", "ف"}),
    "ru": frozenset(),
    "hi": frozenset(),
    "tr": frozenset(),
    "pl": frozenset(),
    "zh": frozenset(),
    "ja": frozenset(),
    "ko": frozenset(),
    "vi": frozenset(),
}

_LEMMA_PREPS: dict[str, tuple[str, ...]] = {
    "es": ("con", "a", "de", "en", "por", "para", "sobre", "sin", "hacia"),
    "fr": ("à", "de", "en", "par", "pour", "avec", "sans", "sur"),
    "de": ("mit", "an", "auf", "für", "von", "zu", "über", "ohne"),
    "it": ("con", "a", "di", "da", "in", "per", "su", "senza"),
    "pt-br": ("com", "a", "de", "em", "por", "para", "sobre", "sem"),
    "pt-pt": ("com", "a", "de", "em", "por", "para", "sobre", "sem"),
    "en": ("to", "of", "in", "on", "for", "with", "at", "from"),
}


def _resolve_code(code: str | None) -> str:
    c = normalize_l2_code(code)
    if c == "pt":
        return "pt-br"
    return c


def articles_for(code: str | None) -> frozenset[str]:
    c = _resolve_code(code)
    if c not in SUPPORTED_L2_LANGS:
        return frozenset()
    return _ARTICLES.get(c, frozenset())


def lemma_preps_for(code: str | None) -> tuple[str, ...]:
    c = _resolve_code(code)
    return _LEMMA_PREPS.get(c, ())

"""Obsługiwane języki nauki (LSP) — 16 kodów."""

from __future__ import annotations

SUPPORTED_L2_LANGS: frozenset[str] = frozenset(
    {
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt-br",
        "pt-pt",
        "zh",
        "ja",
        "ko",
        "ar",
        "ru",
        "hi",
        "tr",
        "vi",
        "pl",
    }
)

CARD_SCHEMA_VERSION = "vocabulario.card.v1"


def is_supported_l2(code: str | None) -> bool:
    return (code or "").strip().lower() in SUPPORTED_L2_LANGS


def normalize_l2_code(code: str | None) -> str:
    return (code or "").strip().lower()

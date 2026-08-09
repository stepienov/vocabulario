"""Kanoniczne klucze czasów + aliasy ze starszych profili."""

from __future__ import annotations

TENSE_KEY_ALIASES = {
    "imperfecto": "preterito_imperfecto",
    "futuro": "futuro_simple",
    "condicional": "condicional_simple",
    # PL
    "present": "czas_terazniejszy",
    "present_tense": "czas_terazniejszy",
    "czas_teraźniejszy": "czas_terazniejszy",
    "past": "czas_przeszly",
    "past_tense": "czas_przeszly",
    "czas_przeszły": "czas_przeszly",
    "future": "czas_przyszly",
    "future_tense": "czas_przyszly",
    "czas_przyszły": "czas_przyszly",
    "imperative": "tryb_rozkazujacy",
    "tryb_rozkazujący": "tryb_rozkazujacy",
    "conditional": "tryb_przypuszczajacy",
    "tryb_przypuszczający": "tryb_przypuszczajacy",
}


def normalize_tense_key(key: str) -> str:
    return TENSE_KEY_ALIASES.get(key, key)


def normalize_tense_keys(keys: list[str] | None) -> list[str]:
    if not keys:
        return []
    seen: list[str] = []
    for raw in keys:
        key = normalize_tense_key(str(raw).strip())
        if key and key not in seen:
            seen.append(key)
    return seen

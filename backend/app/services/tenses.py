"""Kanoniczne klucze czasów + aliasy ze starszych profili, scoped per L2."""

from __future__ import annotations

DIACRITIC_TENSE_ALIASES = {
    "czas_teraźniejszy": "czas_terazniejszy",
    "czas_przeszły": "czas_przeszly",
    "czas_przyszły": "czas_przyszly",
    "tryb_rozkazujący": "tryb_rozkazujacy",
    "tryb_przypuszczający": "tryb_przypuszczajacy",
    "imiesłów": "imieslow",
}

ES_TENSE_ALIASES = {
    "imperfecto": "preterito_imperfecto",
    "futuro": "futuro_simple",
    "condicional": "condicional_simple",
}

PL_TENSE_ALIASES = {
    "present": "czas_terazniejszy",
    "present_tense": "czas_terazniejszy",
    "past": "czas_przeszly",
    "past_tense": "czas_przeszly",
    "future": "czas_przyszly",
    "future_tense": "czas_przyszly",
    "imperative": "tryb_rozkazujacy",
    "conditional": "tryb_przypuszczajacy",
    "infinitive": "bezokolicznik",
    "participle": "imieslow",
}

ALIASES_BY_LANG: dict[str, dict[str, str]] = {
    "es": ES_TENSE_ALIASES,
    "pl": PL_TENSE_ALIASES,
}


def tense_aliases_for(learning_lang: str | None) -> dict[str, str]:
    lang = (learning_lang or "").strip().lower()
    specific = ALIASES_BY_LANG.get(lang, {})
    return {**DIACRITIC_TENSE_ALIASES, **specific}


def normalize_tense_key(key: str, learning_lang: str | None = None) -> str:
    aliases = tense_aliases_for(learning_lang)
    return aliases.get(key, key)


def normalize_tense_keys(keys: list[str] | None, learning_lang: str | None = None) -> list[str]:
    if not keys:
        return []
    seen: list[str] = []
    for raw in keys:
        key = normalize_tense_key(str(raw).strip(), learning_lang)
        if key and key not in seen:
            seen.append(key)
    return seen

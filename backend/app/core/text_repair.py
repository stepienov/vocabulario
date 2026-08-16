"""Naprawa interpunkcji zapisanej jako UTF-8 odczytane w CP852 (ÔÇ×casaÔÇŁ)."""

from __future__ import annotations

_CP852_PUNCT = (
    ("ÔÇť", "\u201c"),
    ("ÔÇŁ", "\u201d"),
    ("ÔÇ×", "\u201e"),
    ("ÔÇś", "\u2018"),
    ("ÔÇÖ", "\u2019"),
    ("ÔÇô", "\u2013"),
    ("ÔÇö", "\u2014"),
    ("ÔÇŽ", "\u2026"),
    ("â€œ", "\u201c"),
    ("â€\x9d", "\u201d"),
    ("â€ž", "\u201e"),
    ("Â«", "\u00ab"),
    ("Â»", "\u00bb"),
)


def repair_display_text(raw: str) -> str:
    if not raw or not any(ch in raw for ch in "ÔâÂ"):
        return raw
    out = raw
    for bad, good in _CP852_PUNCT:
        if bad in out:
            out = out.replace(bad, good)
    return out


def repair_strings(value: object) -> object:
    if isinstance(value, str):
        return repair_display_text(value)
    if isinstance(value, list):
        return [repair_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_strings(item) for key, item in value.items()}
    return value

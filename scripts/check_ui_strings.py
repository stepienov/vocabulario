#!/usr/bin/env python3
"""Sprawdza kompletność strings.xml — 17 locale × te same klucze co values/strings.xml.

Wykrywa też skopiowany angielski (poza allowlistą cognate/marek).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.sax.saxutils import unescape

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "android" / "app" / "src" / "main" / "res"
BASE = RES / "values" / "strings.xml"

# 17 folderów res (values = fallback EN + 16 języków UI; pt-br/pt-pt osobno)
LOCALE_DIRS = [
    "values",
    "values-en",
    "values-es",
    "values-fr",
    "values-de",
    "values-it",
    "values-pt-rBR",
    "values-pt-rPT",
    "values-zh",
    "values-ja",
    "values-ko",
    "values-ar",
    "values-ru",
    "values-hi",
    "values-tr",
    "values-vi",
    "values-pl",
]

KEY_RE = re.compile(r'<string\s+name="([^"]+)"')
STRING_RE = re.compile(r'<string name="([^"]+)">(.*?)</string>', re.S)
FMT_RE = re.compile(r"%(?:\d+\$)?[sdif]")

ALLOW_EN_COPY = {
    "app_name",
    "action_ok",
    "sort_lemma_asc",
    "sort_lemma_desc",
    "card_history_diff_ipa",
    "voice_start",
    "voice_stop",
    "settings_mode_choice",
    "card_history_actor_system",
    "action_filter_active",
    "filter_title",
    "auth_email",
    "auth_password",
    "list_name_hint",
    "import_file_label",
    "status_error",
    "kind_construction",
    "section_fallback",
    "correction_section_lemma",
    "correction_note_label",
    "correction_field_notes",
    "correction_field_lemma",
    "settings_notifications",
    "card_history_diff_lemma",
    "pos_interj",
}


def extract_keys(path: Path) -> set[str]:
    return set(KEY_RE.findall(path.read_text(encoding="utf-8")))


def extract_values(path: Path) -> dict[str, str]:
    return {
        m.group(1): unescape(m.group(2).replace("\\'", "'").replace('\\"', '"'))
        for m in STRING_RE.finditer(path.read_text(encoding="utf-8"))
    }


def main() -> int:
    if not BASE.is_file():
        print(f"Brak pliku bazowego: {BASE}", file=sys.stderr)
        return 1

    base_keys = extract_keys(BASE)
    base_vals = extract_values(BASE)
    errors: list[str] = []

    for locale in LOCALE_DIRS:
        path = RES / locale / "strings.xml"
        if not path.is_file():
            errors.append(f"MISSING FILE: {path.relative_to(ROOT)}")
            continue
        keys = extract_keys(path)
        missing = sorted(base_keys - keys)
        extra = sorted(keys - base_keys)
        if missing:
            errors.append(f"{locale}: brakuje {len(missing)} kluczy (np. {missing[:5]})")
        if extra:
            errors.append(f"{locale}: {len(extra)} nadmiarowych kluczy (np. {extra[:5]})")
        vals = extract_values(path)
        empty = sorted(k for k in keys if not vals.get(k, "").strip())
        if empty:
            errors.append(f"{locale}: {len(empty)} pustych stringów (np. {empty[:5]})")
        if locale in ("values", "values-en"):
            continue
        copied = sorted(
            k
            for k in base_keys & keys
            if k not in ALLOW_EN_COPY and vals.get(k) == base_vals.get(k)
        )
        if copied:
            errors.append(f"{locale}: {len(copied)} skopiowanych EN (np. {copied[:5]})")
        for k in sorted(base_keys & keys):
            if set(FMT_RE.findall(base_vals.get(k, ""))) != set(FMT_RE.findall(vals.get(k, ""))):
                errors.append(f"{locale}: {k} — placeholdery ≠ EN")

    print(f"Bazowy plik: {len(base_keys)} kluczy")
    if errors:
        print("BŁĘDY:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK — {len(LOCALE_DIRS)} locale, po {len(base_keys)} kluczy, bez skopiowanego EN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

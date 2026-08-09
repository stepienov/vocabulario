#!/usr/bin/env python3
"""Sprawdza kompletność strings.xml — 16 locale × te same klucze co values/strings.xml."""

from __future__ import annotations

import re
import sys
from pathlib import Path

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


def extract_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(KEY_RE.findall(text))


def main() -> int:
    if not BASE.is_file():
        print(f"Brak pliku bazowego: {BASE}", file=sys.stderr)
        return 1

    base_keys = extract_keys(BASE)
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

    print(f"Bazowy plik: {len(base_keys)} kluczy")
    if errors:
        print("BŁĘDY:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK — {len(LOCALE_DIRS)} locale, po {len(base_keys)} kluczy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

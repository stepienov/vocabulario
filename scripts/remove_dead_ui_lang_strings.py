#!/usr/bin/env python3
"""Usuwa martwe klucze strings.xml po migracji app_lang."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "android" / "app" / "src" / "main" / "res"
REMOVE = frozenset(
    {
        "settings_ui_lang",
        "profile_ui_lang",
        "err_ui_lang",
        "msg_saved_ui_lang",
    }
)
PAT = re.compile(
    r'^\s*<string\s+name="(' + "|".join(sorted(REMOVE)) + r')"[^>]*>.*</string>\s*$'
)


def main() -> int:
    updated = 0
    for path in sorted(RES.glob("**/strings.xml")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        new_lines = [ln for ln in lines if not PAT.search(ln)]
        if len(new_lines) != len(lines):
            path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            updated += 1
            print(f"updated {path.relative_to(ROOT)}")
    print(f"OK — {updated} plików, usunięto {len(REMOVE)} kluczy na locale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

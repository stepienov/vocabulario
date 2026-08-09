#!/usr/bin/env python3
"""Weryfikuje spójność manifestów LSP z Android LanguagePacks (klucze czasów)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LSP_ROOT = ROOT / "backend" / "app" / "lsp"
ANDROID_PACKS = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "vocabulario" / "app" / "data" / "LanguagePacks.kt"

TENSE_ITEM_RE = re.compile(r'TenseItem\("([^"]+)"')


def extract_android_tense_keys(lang: str) -> set[str]:
    text = ANDROID_PACKS.read_text(encoding="utf-8")
    match = re.search(rf'code\s*=\s*"{re.escape(lang)}"', text)
    if not match:
        return set()
    idx = match.start()
    chunk = text[idx : idx + 8000]
    end_markers = [
        chunk.find("\n    private val ", 1),
        chunk.find("\n    private val packs", 1),
        chunk.find('\n        "', 1),
    ]
    ends = [e for e in end_markers if e > 0]
    if ends:
        chunk = chunk[: min(ends)]

    keys = set(TENSE_ITEM_RE.findall(chunk))
    if "ptBr.tenses" in chunk or "ptBr.nonFinite" in chunk:
        keys |= extract_android_tense_keys("pt-br")
    return keys


def main() -> int:
    from app.lsp.constants import SUPPORTED_L2_LANGS
    from app.lsp.registry import get_manifest, has_manifest

    errors: list[str] = []
    for code in sorted(SUPPORTED_L2_LANGS):
        if not has_manifest(code):
            errors.append(f"{code}: brak manifestu LSP")
            continue
        m = get_manifest(code)
        manifest_keys = set(m.tense_keys() + m.non_finite_keys())
        android_keys = extract_android_tense_keys(code)
        if not android_keys and manifest_keys:
            errors.append(f"{code}: brak packa w LanguagePacks.kt")
            continue
        only_manifest = sorted(manifest_keys - android_keys)
        only_android = sorted(android_keys - manifest_keys)
        if only_manifest:
            errors.append(f"{code}: tylko w LSP: {only_manifest[:8]}")
        if only_android:
            errors.append(f"{code}: tylko w Android: {only_android[:8]}")

    if errors:
        print("BŁĘDY synchronizacji LSP ↔ Android:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK — {len(SUPPORTED_L2_LANGS)} języków zsynchronizowanych")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "backend"))
    raise SystemExit(main())

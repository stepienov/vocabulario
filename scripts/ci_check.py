#!/usr/bin/env python3
"""Lokalne sprawdzenia CI — UI strings, synchronizacja LSP, testy backendu."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path | None = None) -> int:
    label = " ".join(cmd)
    print(f"\n▶ {label}")
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    if result.returncode != 0:
        print(f"✗ failed ({result.returncode}): {label}")
    else:
        print(f"✓ ok: {label}")
    return result.returncode


def main() -> int:
    steps = [
        (["python", str(ROOT / "scripts" / "check_ui_strings.py")], ROOT),
        (["python", str(ROOT / "scripts" / "lsp_sync.py")], ROOT),
        (["python", "-m", "pytest", "-q"], ROOT / "backend"),
    ]
    failed = 0
    for cmd, cwd in steps:
        failed += run(cmd, cwd=cwd) != 0
    if failed:
        print(f"\n{failed} check(s) failed")
        return 1
    print("\nAll CI checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

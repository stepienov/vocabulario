"""Sprawdza, czy biblioteki natywne 64-bitowe w AAB/APK są gotowe na strony 16 KB.

Użycie: python scripts/check_aab_16kb.py android/app/build/outputs/bundle/release/app-release.aab
Kod wyjścia 1, gdy któryś segment LOAD ma wyrównanie < 0x4000.
"""

from __future__ import annotations

import struct
import sys
import zipfile

REQUIRED_ALIGN = 0x4000
CHECKED_ABIS = ("arm64-v8a", "x86_64")


def load_alignments(data: bytes) -> list[int]:
    if data[:4] != b"\x7fELF" or data[4] != 2:  # tylko ELF64
        return []
    little = data[5] == 1
    endian = "<" if little else ">"
    phoff = struct.unpack_from(endian + "Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from(endian + "HH", data, 0x36)
    alignments = []
    for index in range(phnum):
        base = phoff + index * phentsize
        p_type = struct.unpack_from(endian + "I", data, base)[0]
        if p_type == 1:  # PT_LOAD
            alignments.append(struct.unpack_from(endian + "Q", data, base + 0x30)[0])
    return alignments


def main(path: str) -> int:
    failures: list[str] = []
    checked = 0
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith(".so"):
                continue
            if not any(f"/{abi}/" in name for abi in CHECKED_ABIS):
                continue
            checked += 1
            alignments = load_alignments(archive.read(name))
            if not alignments or min(alignments) < REQUIRED_ALIGN:
                failures.append(f"{name}: {[hex(a) for a in alignments]}")
    print(f"Sprawdzone biblioteki 64-bit: {checked}")
    for line in failures:
        print(f"NIE 16 KB: {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

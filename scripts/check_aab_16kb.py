"""Check ELF alignment in AAB/APK and uncompressed libraries in APK.

Usage: python scripts/check_aab_16kb.py android/app/build/outputs/bundle/release/app-release.aab
Checking an AAB does not replace checking the generated APK or testing on a 16 KB device.
"""

from __future__ import annotations

import struct
import sys
import zipfile
from pathlib import Path

REQUIRED_ALIGN = 0x4000
CHECKED_ABIS = ("arm64-v8a", "x86_64")


def load_alignments(data: bytes) -> list[int]:
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2 or data[5] not in (1, 2):
        return []
    little = data[5] == 1
    endian = "<" if little else ">"
    phoff = struct.unpack_from(endian + "Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from(endian + "HH", data, 0x36)
    if phentsize < 56 or not phnum or phoff + phentsize * phnum > len(data):
        return []
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
    apk = Path(path).suffix.lower() == ".apk"
    compressed = 0
    with open(path, "rb") as source, zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            name = info.filename
            if not name.endswith(".so"):
                continue
            if not any(f"/{abi}/" in name for abi in CHECKED_ABIS):
                continue
            checked += 1
            alignments = load_alignments(archive.read(info))
            if not alignments or any(
                alignment < REQUIRED_ALIGN or alignment & (alignment - 1)
                for alignment in alignments
            ):
                failures.append(f"{name}: {[hex(a) for a in alignments]}")
            if apk and info.compress_type == zipfile.ZIP_STORED:
                source.seek(info.header_offset)
                header = source.read(30)
                if len(header) != 30 or header[:4] != b"PK\x03\x04":
                    failures.append(f"{name}: invalid local ZIP header")
                    continue
                name_len, extra_len = struct.unpack_from("<HH", header, 26)
                offset = info.header_offset + 30 + name_len + extra_len
                if offset % REQUIRED_ALIGN:
                    failures.append(f"{name}: ZIP data is not 16 KB aligned (offset {offset})")
            elif apk:
                compressed += 1
    print(f"64-bit libraries checked: {checked}")
    if compressed:
        print(f"Compressed libraries in APK: {compressed}; extraction is required before use.")
    if not apk:
        print("An AAB does not verify ZIP alignment or runtime behavior of generated APKs.")
    for line in failures:
        print(f"NOT 16 KB: {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

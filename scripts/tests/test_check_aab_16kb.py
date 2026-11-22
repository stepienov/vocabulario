import os
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

from scripts.check_aab_16kb import load_alignments, main


def _elf(alignment=0x4000):
    data = bytearray(128)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", data, 0x20, 64)
    struct.pack_into("<HH", data, 0x36, 56, 1)
    struct.pack_into("<I", data, 64, 1)
    struct.pack_into("<Q", data, 64 + 0x30, alignment)
    return bytes(data)


def _archive(path, *, aligned=False, elf_alignment=0x4000):
    name = "lib/arm64-v8a/libexample.so"
    info = zipfile.ZipInfo(name)
    if aligned:
        padding = (-(30 + len(name) + 4)) % 0x4000
        info.extra = struct.pack("<HH", 0xCAFE, padding) + bytes(padding)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, _elf(elf_alignment))


def test_apk_requires_elf_and_zip_alignment(tmp_path):
    path = tmp_path / "test.apk"
    _archive(path)
    assert main(str(path)) == 1
    _archive(path, aligned=True)
    assert main(str(path)) == 0
    _archive(path, aligned=True, elf_alignment=0x1000)
    assert main(str(path)) == 1


def test_aab_checks_elf_without_treating_it_as_apk(tmp_path):
    path = tmp_path / "test.aab"
    _archive(path)
    assert main(str(path)) == 0


def test_invalid_elf_is_rejected():
    assert load_alignments(b"\x7fELF") == []
    data = bytearray(_elf())
    struct.pack_into("<Q", data, 0x20, len(data) + 1)
    assert load_alignments(data) == []


def test_cli_supports_non_utf8_stdout(tmp_path):
    path = tmp_path / "test.aab"
    _archive(path)
    script = Path(__file__).resolve().parents[1] / "check_aab_16kb.py"
    result = subprocess.run(
        [sys.executable, str(script), str(path)],
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

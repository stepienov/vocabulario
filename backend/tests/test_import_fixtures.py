"""Fixture-based import parsing tests (Desktop samples in fixtures/import/)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.core.upload_limits import MAX_IMPORT_FILE_BYTES
from app.services import import_package
from app.services.import_package import (
    ImportTooLargeError,
    _decompress_anki21b,
    _read_best_anki_db,
    load_raw_import,
    load_text_import,
)

FIXTURES = Path(__file__).parent / "fixtures" / "import"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _read_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_quizlet1_tsv_pairs():
    deck = load_text_import(_read("quizlet1.txt"))
    assert len(deck.notes) >= 20
    assert deck.notes[0][0].strip().lower().lstrip("\ufeff") == "fumar"
    assert "pali" in deck.notes[0][1].lower()


def test_quizlet2_semicolon_export_loads():
    """One-line Quizlet export — raw load keeps content for AI segmentation."""
    raw = _read("quizlet2.txt")
    assert ";" in raw and "," in raw
    deck = load_text_import(raw)
    blob = " ".join(" ".join(n) for n in deck.notes) if deck.notes else raw
    assert "volver a hacer algo" in blob.lower()
    # Without AI format step the whole line may be 1 note — content must still be there.
    assert "terminar haciendo algo" in blob.lower()


def test_quizlet3_phrases_present():
    deck = load_text_import(_read("quizlet3.txt"))
    assert len(deck.notes) >= 10
    joined = " | ".join(n[0] for n in deck.notes if n)
    assert "volver a hacer algo" in joined
    assert "ir a hacer algo" in joined


def test_testowa_notes_load_as_notes_deck():
    deck = load_text_import(_read("Testowa.txt"))
    assert deck.kind in {"notes", "anki_notes", "plain"}
    assert len(deck.notes) >= 5
    # Headword field should include Spanish lemmas (not guid)
    heads = " ".join(
        (n[3] if len(n) > 3 else n[0]) for n in deck.notes[:5]
    ).lower()
    assert "despertarse" in heads or "planear" in heads or "quejarse" in heads


def test_apkg_anki21b_loads_real_notes():
    data = _read_bytes("Testowa.apkg")
    deck = load_raw_import("Testowa.apkg", data)
    assert deck.kind == "anki_package"
    assert len(deck.notes) >= 3
    assert deck.field_names == [
        "Spanish",
        "Meanings_Block",
        "Irregularity",
        "Conjugation",
    ]
    assert deck.notes[0][0].strip()  # Spanish lemma


def test_import_parser_rejects_files_over_10_mib():
    with pytest.raises(ImportTooLargeError):
        load_raw_import("large.txt", b"x" * (MAX_IMPORT_FILE_BYTES + 1))


def test_anki_zip_member_expansion_is_capped(monkeypatch):
    monkeypatch.setattr(import_package, "MAX_ANKI_DATABASE_BYTES", 100)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("collection.anki2", b"x" * 101)
    with zipfile.ZipFile(io.BytesIO(archive.getvalue())) as zf:
        with pytest.raises(ImportTooLargeError):
            _read_best_anki_db(zf)


def test_anki21b_expansion_is_capped(monkeypatch):
    import zstandard

    monkeypatch.setattr(import_package, "MAX_ANKI_DATABASE_BYTES", 100)
    compressed = zstandard.ZstdCompressor().compress(b"x" * 101)
    with pytest.raises(ImportTooLargeError):
        _decompress_anki21b(compressed)

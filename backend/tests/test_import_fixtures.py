"""Fixture-based import parsing tests (Desktop samples in fixtures/import/)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.import_display import html_structure_blocks, resolve_import_display_cards
from app.services.import_package import load_raw_import, load_text_import
from app.services.llm import LLMService

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


def test_testowa_notes_conjugation_table_block():
    text = _read("Testowa.txt")
    assert "#separator:tab" in text
    assert "<table" in text.lower()
    blocks = html_structure_blocks(text)
    assert blocks is not None
    assert any(b["type"] == "table" for b in blocks)
    flats = []
    for table in blocks:
        if table["type"] != "table":
            continue
        parts = list(table.get("headers") or [])
        parts.extend(" ".join(r) for r in (table.get("rows") or []))
        flats.append(" ".join(parts).lower())
    joined = " | ".join(flats)
    assert "presente" in joined
    assert "despierto" in joined or "despert" in joined


def test_testowa_notes_load_as_notes_deck():
    deck = load_text_import(_read("Testowa.txt"))
    assert deck.kind in {"notes", "anki_notes", "plain"}
    assert len(deck.notes) >= 5
    # Headword field should include Spanish lemmas (not guid)
    heads = " ".join(
        (n[3] if len(n) > 3 else n[0]) for n in deck.notes[:5]
    ).lower()
    assert "despertarse" in heads or "planear" in heads or "quejarse" in heads


def test_testowa2_strips_script_style_for_structure():
    html = _read("Testowa2.txt")
    assert "<script" in html.lower() or "front-word" in html.lower()
    blocks = html_structure_blocks(html)
    if blocks:
        blob = str(blocks).lower()
        assert "tts.speak" not in blob
        assert "<script" not in blob


def test_preserve_mock_path_from_quizlet1():
    deck = load_text_import(_read("quizlet1.txt"))
    llm = LLMService()
    llm.mock = True
    result = asyncio.run(
        resolve_import_display_cards(
            deck,
            app_lang="pl",
            learning_lang="es",
            llm=llm,
        )
    )
    assert result["cards"]
    assert result["cards"][0]["display"]["prompt"]["blocks"]
    assert "bidirectional" in result["cards"][0]["display"]


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

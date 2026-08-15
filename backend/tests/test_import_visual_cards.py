"""Visual + layout quality tests on real Desktop import fixtures.

For each fixture file:
  1) load deck, take first CARDS_PER_FILE notes
  2) run preserve layout (real OpenAI unless LLM_MOCK / no key)
  3) assert structural quality of AI/heuristic output
  4) render 2–3 cards to HTML + PNG under tests/artifacts/import_visual/

Run:
  cd backend
  python -m pytest tests/test_import_visual_cards.py -q -s

Open gallery:
  backend/tests/artifacts/import_visual/index.html
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.import_display import resolve_import_display_cards
from app.services.import_package import RawImportDeck, load_raw_import, load_text_import
from app.services.llm import LLMService
from tests.visual.render_card import (
    sanitize_filename,
    screenshot_html,
    write_card_html,
    write_index,
)

FIXTURES = Path(__file__).parent / "fixtures" / "import"
ARTIFACTS = Path(__file__).parent / "artifacts" / "import_visual"
CARDS_PER_FILE = 3

# Fixture → how to load
CASES = [
    ("quizlet1.txt", "text"),
    ("quizlet2.txt", "text"),
    ("quizlet3.txt", "text"),
    ("Testowa.txt", "text"),
    ("Testowa2.txt", "text"),
    ("Testowa.apkg", "apkg"),
    ("Saludos_Basicos_EnglishSpanish.apkg", "apkg"),
    ("Autonomous_communities_of_Spain_with_locator_maps_in_Spanish.apkg", "apkg"),
    ("Spanish_Tenses_a_Lisardos_KOFI_Conjugation_Method_Primer.apkg", "apkg"),
    ("Assimil_El_nuevo_ingles_sin_esfuerzo_real_spoken_audio.apkg", "apkg"),
]


def _truncate(deck: RawImportDeck, n: int) -> RawImportDeck:
    return RawImportDeck(
        kind=deck.kind,
        notes=list(deck.notes[:n]),
        field_names=deck.field_names,
        meta=dict(deck.meta or {}),
        raw_text=deck.raw_text,
    )


def _load_case(name: str, mode: str) -> RawImportDeck:
    path = FIXTURES / name
    if mode == "apkg":
        return load_raw_import(name, path.read_bytes())
    return load_text_import(path.read_text(encoding="utf-8"))


def _assert_card_quality(card: dict, *, source: str) -> None:
    assert card.get("lemma_l2"), f"{source}: missing lemma_l2"
    display = card.get("display") or {}
    prompt = (display.get("prompt") or {}).get("blocks") or []
    answer = (display.get("answer") or {}).get("blocks") or []
    assert prompt, f"{source}: empty prompt blocks for {card.get('lemma_l2')}"
    # Never leak raw script/style into rendered text fields
    blob = str(display).lower()
    assert "<script" not in blob
    assert "javascript:" not in blob
    assert "bidirectional" in display
    assert isinstance(display["bidirectional"], bool)
    # At least one textual / structural signal on the card
    types = {b.get("type") for b in prompt + answer}
    assert types & {
        "headword",
        "title",
        "gloss",
        "text",
        "paragraph",
        "table",
        "list",
        "section",
        "bilingual",
        "chip",
        "meta",
    }, f"{source}: unexpected block types {types}"


def _assert_source_expectations(source: str, cards: list[dict]) -> None:
    if source.startswith("Testowa"):
        for c in cards:
            prompt = (c.get("display") or {}).get("prompt") or {}
            answer = (c.get("display") or {}).get("answer") or {}
            ptypes = {b.get("type") for b in (prompt.get("blocks") or [])}
            assert "headword" in ptypes or any(
                b.get("semantic") == "headword" for b in (prompt.get("blocks") or [])
            )
            # No irregularity chip on front
            for b in prompt.get("blocks") or []:
                assert not _looks_like_chip_irreg(b.get("text") or "")
            # Gloss should be short (not full meanings blob)
            gloss = c.get("gloss_primary") or ""
            assert "\n" not in gloss
            assert len(gloss) < 80
            # Conjugation tables present
            tables = 0
            for b in answer.get("blocks") or []:
                if b.get("type") == "table":
                    tables += 1
                for ch in b.get("children") or []:
                    if ch.get("type") == "table":
                        tables += 1
            assert tables >= 1, f"{source}: expected conjugation tables"
    if source.startswith("quizlet3") or source.startswith("quizlet2"):
        assert any(" " in (c.get("lemma_l2") or "") for c in cards)


def _looks_like_chip_irreg(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and ("→" in t or "obocz" in t.lower()) and len(t) <= 40


@pytest.fixture(scope="module")
def llm_service() -> LLMService:
    settings = get_settings()
    svc = LLMService()
    if not settings.openai_api_key:
        svc.mock = True
    return svc


@pytest.fixture(scope="module")
def artifact_dir() -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    # clean previous png/html from this suite (keep folder)
    for p in ARTIFACTS.glob("*"):
        if p.suffix.lower() in {".png", ".html", ".json"}:
            p.unlink(missing_ok=True)
    return ARTIFACTS


@pytest.fixture(scope="module")
def gallery_rows(artifact_dir: Path) -> list[dict]:
    rows: list[dict] = []
    yield rows
    if rows:
        write_index(artifact_dir, rows)
        print(f"\nGallery: {(artifact_dir / 'index.html').resolve()}")


@pytest.mark.parametrize("filename,mode", CASES, ids=[c[0] for c in CASES])
def test_visual_cards_per_fixture(
    filename: str,
    mode: str,
    llm_service: LLMService,
    artifact_dir: Path,
    gallery_rows: list[dict],
):
    deck = _load_case(filename, mode)
    assert deck.notes, f"{filename}: no notes after load"

    deck = _truncate(deck, CARDS_PER_FILE)
    # Keep extension so Testowa.txt vs Testowa.apkg don't collide
    stem = sanitize_filename(filename.replace(".", "_"))

    result = asyncio.run(
        resolve_import_display_cards(
            deck,
            app_lang="pl",
            learning_lang="es",
            llm=llm_service,
            max_cards=CARDS_PER_FILE,
        )
    )
    cards = result.get("cards") or []
    assert cards, f"{filename}: no cards from layout pipeline"
    cards = cards[:CARDS_PER_FILE]

    for i, card in enumerate(cards):
        _assert_card_quality(card, source=filename)
        lemma = sanitize_filename(card.get("lemma_l2") or f"card{i}")
        base = f"{stem}__{i+1:02d}_{lemma}"
        html_path = artifact_dir / f"{base}.html"
        png_path = artifact_dir / f"{base}.png"
        write_card_html(card, html_path, source=filename, index=i)
        try:
            screenshot_html(html_path, png_path)
        except Exception as exc:  # noqa: BLE001 — still keep HTML for inspection
            pytest.fail(f"PNG render failed for {base}: {exc}")
        assert png_path.exists() and png_path.stat().st_size > 1000
        gallery_rows.append(
            {
                "source": filename,
                "title": f"{filename} · {card.get('lemma_l2')}",
                "meta": (
                    f"bidirectional={card.get('display', {}).get('bidirectional')} · "
                    f"mock={llm_service.mock}"
                ),
                "png": png_path,
                "html": html_path,
            }
        )

    _assert_source_expectations(filename, cards)

    # When using real OpenAI, require non-mock and a rationale / field roles when present
    if not llm_service.mock:
        assert result.get("field_roles") is not None
        # AI path should not leave raw HTML tags in lemma
        for card in cards:
            assert "<" not in (card.get("lemma_l2") or "")

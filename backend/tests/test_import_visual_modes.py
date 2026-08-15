"""Compare visual: preserve vs vocabulario for each import fixture.

Per file (one gallery row):
  2× preserve cards + 2× vocabulario enriched cards (lemmas only).
If vocabulario can't produce lemmas (phrases/sentences/maps-only), placeholders.

Run:
  cd backend
  python -m pytest tests/test_import_visual_modes.py -q -s

Gallery:
  backend/tests/artifacts/import_visual_modes/index.html
"""

from __future__ import annotations

import asyncio
import random
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.services.enrichment import enrich_card_content
from app.services.import_classify import resolve_import_vocabulario_entries
from app.services.import_display import resolve_import_display_cards, strip_anki_sound
from app.services.import_package import RawImportDeck, load_raw_import, load_text_import
from app.services.llm import LLMService
from tests.visual.render_card import (
    sanitize_filename,
    screenshot_html,
    write_card_html,
    write_index,
)
from tests.visual.render_vocab_card import (
    card_dict_from_enrichment,
    placeholder_html,
    vocab_card_to_html,
)

FIXTURES = Path(__file__).parent / "fixtures" / "import"
ARTIFACTS = Path(__file__).parent / "artifacts" / "import_visual_modes"
SAMPLE_NOTES = 8
PICK = 2

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


def _load(name: str, mode: str) -> RawImportDeck:
    path = FIXTURES / name
    if mode == "apkg":
        return load_raw_import(name, path.read_bytes())
    return load_text_import(path.read_text(encoding="utf-8"))


def _rng(filename: str) -> random.Random:
    return random.Random(abs(hash(filename)) % (2**32))


def _is_lemma_entry(entry: dict) -> bool:
    kind = (entry.get("entry_kind") or "lemma").strip().lower()
    if kind != "lemma":
        return False
    lemma = strip_anki_sound(entry.get("lemma") or "").strip()
    if not lemma or len(lemma) > 40:
        return False
    # Vocabulario lemma path is for single words / short headwords
    if lemma.count(" ") >= 2:
        return False
    if re.search(r"[.!?]", lemma):
        return False
    return True


@pytest.fixture(scope="module")
def llm_service() -> LLMService:
    settings = get_settings()
    svc = LLMService()
    if not settings.openai_api_key:
        svc.mock = True
    return svc


def _learning_lang(filename: str) -> str:
    # Assimil deck is English L2; everything else in this fixture set is Spanish-oriented.
    if filename.startswith("Assimil_"):
        return "en"
    return "es"


@pytest.fixture(scope="module")
def artifact_dir() -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for p in ARTIFACTS.glob("*"):
        if p.suffix.lower() in {".png", ".html", ".json"}:
            p.unlink(missing_ok=True)
    return ARTIFACTS


@pytest.fixture(scope="module")
def gallery_rows(artifact_dir: Path) -> list[dict]:
    rows: list[dict] = []
    yield rows
    if rows:
        write_index(
            artifact_dir,
            rows,
            title="Import — preserve vs vocabulario",
            summary_extra="wiersz = plik · 2× preserve + 2× vocabulario (lub placeholder)",
        )
        print(f"\nGallery: {(artifact_dir / 'index.html').resolve()}")


def _shot_html(html: str, html_path: Path, png_path: Path) -> None:
    html_path.write_text(html, encoding="utf-8")
    screenshot_html(html_path, png_path)
    assert png_path.exists() and png_path.stat().st_size > 500


@pytest.mark.parametrize("filename,mode", CASES, ids=[c[0] for c in CASES])
def test_visual_preserve_and_vocabulario(
    filename: str,
    mode: str,
    llm_service: LLMService,
    artifact_dir: Path,
    gallery_rows: list[dict],
):
    path = FIXTURES / filename
    if not path.exists():
        pytest.skip(f"missing fixture: {filename}")

    learning_lang = _learning_lang(filename)
    profile = SimpleNamespace(app_lang="pl", learning_lang=learning_lang, cefr_level="B1")

    deck = _truncate(_load(filename, mode), SAMPLE_NOTES)
    assert deck.notes, f"{filename}: empty deck"
    stem = sanitize_filename(filename.replace(".", "_"))
    rng = _rng(filename)

    # --- preserve ---
    preserve_result = asyncio.run(
        resolve_import_display_cards(
            deck,
            app_lang=profile.app_lang,
            learning_lang=profile.learning_lang,
            llm=llm_service,
            max_cards=SAMPLE_NOTES,
        )
    )
    preserve_cards = list(preserve_result.get("cards") or [])
    assert preserve_cards, f"{filename}: no preserve cards"
    if len(preserve_cards) > PICK:
        preserve_pick = rng.sample(preserve_cards, PICK)
    else:
        preserve_pick = preserve_cards[:PICK]

    for i, card in enumerate(preserve_pick):
        lemma = sanitize_filename(card.get("lemma_l2") or f"p{i}")
        base = f"{stem}__P{i+1:02d}_{lemma}"
        html_path = artifact_dir / f"{base}.html"
        png_path = artifact_dir / f"{base}.png"
        card = {**card, "mode": "preserve"}
        write_card_html(card, html_path, source=f"{filename} [preserve]", index=i)
        screenshot_html(html_path, png_path)
        gallery_rows.append(
            {
                "source": filename,
                "title": f"{filename} · PRESERVE · {card.get('lemma_l2')}",
                "meta": "mode=preserve · bidirectional="
                f"{card.get('display', {}).get('bidirectional')}",
                "png": png_path,
                "html": html_path,
            }
        )

    # --- vocabulario (lemmas only) ---
    valid, _invalid = asyncio.run(
        resolve_import_vocabulario_entries(
            deck,
            app_lang=profile.app_lang,
            learning_lang=profile.learning_lang,
            llm=llm_service,
        )
    )
    lemmas = [e for e in valid if _is_lemma_entry(e)]
    # de-noise Assimil/Quizlet phrases left as lemma by classifier
    lemmas = [
        e
        for e in lemmas
        if strip_anki_sound(e.get("lemma") or "").count(" ") <= 1
    ]

    vocab_pick: list[dict] = []
    if lemmas:
        vocab_pick = rng.sample(lemmas, min(PICK, len(lemmas)))

    for i in range(PICK):
        base = f"{stem}__V{i+1:02d}"
        html_path = artifact_dir / f"{base}.html"
        png_path = artifact_dir / f"{base}.png"

        if i >= len(vocab_pick):
            reason = (
                "Brak haseł typu lemma (zwroty/zdania/mapa — Vocabulario potrzebuje słówka)."
                if not lemmas
                else "Za mało lematów w próbce."
            )
            _shot_html(
                placeholder_html(source=filename, reason=reason),
                html_path,
                png_path,
            )
            gallery_rows.append(
                {
                    "source": filename,
                    "title": f"{filename} · VOCABULARIO · (brak)",
                    "meta": "mode=vocabulario · skipped",
                    "png": png_path,
                    "html": html_path,
                }
            )
            continue

        entry = vocab_pick[i]
        lemma = strip_anki_sound(entry.get("lemma") or "").strip()
        try:
            content = asyncio.run(
                enrich_card_content(profile, lemma, entry.get("pos"))
            )
        except Exception as exc:  # noqa: BLE001
            _shot_html(
                placeholder_html(source=filename, reason=f"enrichment failed: {exc}"),
                html_path,
                png_path,
            )
            gallery_rows.append(
                {
                    "source": filename,
                    "title": f"{filename} · VOCABULARIO · {lemma} (error)",
                    "meta": "mode=vocabulario · enrichment_error",
                    "png": png_path,
                    "html": html_path,
                }
            )
            continue

        card = card_dict_from_enrichment(content, key=lemma)
        safe = sanitize_filename(lemma)
        html_path = artifact_dir / f"{stem}__V{i+1:02d}_{safe}.html"
        png_path = artifact_dir / f"{stem}__V{i+1:02d}_{safe}.png"
        _shot_html(
            vocab_card_to_html(content, source=filename, index=i, lemma=lemma),
            html_path,
            png_path,
        )
        gallery_rows.append(
            {
                "source": filename,
                "title": f"{filename} · VOCABULARIO · {lemma}",
                "meta": f"mode=vocabulario · gloss={card.get('gloss_primary')}",
                "png": png_path,
                "html": html_path,
            }
        )

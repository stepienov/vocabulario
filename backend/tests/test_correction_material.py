"""Tests for correction patch materiality and related gates."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.card_corrections import (
    STYLE_REJECT_REASON,
    _apply_patch_to_content,
    apply_correction_patch,
    gate_accepted_patch,
    obvious_headword_fix,
    patch_is_material,
)
from app.services.correction_evidence import both_glosses_attested, l1_terms_from_content
from app.services.dictionary_lookup import parse_wiktionary_title_exists


def _before(lemma="muebles", pos="noun", gloss="meble", content=None):
    content = content or {
        "lemma": lemma,
        "pos": pos,
        "meanings": [{"gloss_l1": gloss, "synonyms_l1": [], "examples": [], "usages": []}],
    }
    return {
        "lemma_l2": lemma,
        "pos": pos,
        "gloss_primary": gloss,
        "content": content,
    }


def test_rejects_stylistic_gloss_change():
    before = _before(gloss="meble")
    ok, reason = patch_is_material(before, {"gloss_primary": "obiekt meblowy"})
    assert ok is False
    assert reason


def test_rejects_identical_gloss_patch():
    before = _before(gloss="meble")
    ok, _ = patch_is_material(before, {"gloss_primary": "meble"})
    assert ok is False


def test_accepts_wrong_gloss_fix():
    before = _before(gloss="jedzenie")
    ok, reason = patch_is_material(before, {"gloss_primary": "meble"})
    assert ok is True
    assert reason is None


def test_accepts_pos_fix():
    before = _before(pos="noun")
    ok, _ = patch_is_material(before, {"pos": "verb"})
    assert ok is True


def test_accepts_placeholder_conjugation_fix():
    before = _before(
        content={
            "lemma": "comer",
            "pos": "verb",
            "meanings": [{"gloss_l1": "jeść", "synonyms_l1": [], "examples": [], "usages": []}],
            "conjugation": {"presente": {"yo": "—"}},
        }
    )
    ok, _ = patch_is_material(
        before,
        {"conjugation": {"presente": {"yo": "como", "tú": "comes"}}},
    )
    assert ok is True


def test_family_invented_word_is_material_and_persists():
    before = _before(
        lemma="el intermitente",
        gloss="kierunkowskaz",
        content={
            "lemma": "el intermitente",
            "pos": "noun",
            "meanings": [{"gloss_l1": "kierunkowskaz", "synonyms_l1": [], "examples": [], "usages": []}],
            "word_family_l2": [
                {"lemma": "la intermitencia", "pos": "noun", "gloss_l1": "przerywaność"},
            ],
        },
    )
    patch = {
        "word_family_l2": [
            {"lemma": "la intermitencia", "pos": "noun", "gloss_l1": "przerywalność"},
        ]
    }
    ok, reason = patch_is_material(before, patch)
    assert ok is True
    assert reason is None
    merged = _apply_patch_to_content(before["content"], patch)
    assert merged["word_family_l2"][0]["gloss_l1"] == "przerywalność"
    card = SimpleNamespace(
        lemma_l2="el intermitente",
        pos="noun",
        gloss_primary="kierunkowskaz",
        content=dict(before["content"]),
        lexical_entry_id="x",
    )
    apply_correction_patch(card, patch, "es")
    assert card.content["word_family_l2"][0]["gloss_l1"] == "przerywalność"
    assert card.content["lemma"] == card.lemma_l2
    assert card.lexical_entry_id is None


def test_synonym_pair_attested_in_dictionary_is_rejected():
    before = _before(lemma="despertarse", pos="verb", gloss="budzić się")
    patch = {"gloss_primary": "wstawać"}
    evidence = {
        "lemma_candidates": [
            {"lemma": "despertarse", "pos": "verb", "gloss": "budzić się"},
            {"lemma": "despertarse", "pos": "verb", "gloss": "wstawać"},
        ],
        "app_lang_page_exists": {},
    }
    assert both_glosses_attested("budzić się", "wstawać", evidence) is True
    ok, reason = gate_accepted_patch(before, patch, evidence)
    assert ok is False
    assert reason == STYLE_REJECT_REASON


def test_obvious_headword_fix_prefers_article_form():
    before = {
        "lemma_l2": "el intermitente",
        "pos": "noun",
        "gloss_primary": "kierunkowskaz",
        "content": {"lemma": "intermitente", "pos": "noun"},
    }
    patch = obvious_headword_fix(before, "es")
    assert patch == {"lemma": "el intermitente"}
    ok, _ = patch_is_material(before, patch)
    assert ok is True


def test_l1_terms_include_family_glosses():
    terms = l1_terms_from_content(
        {
            "meanings": [{"gloss_l1": "kierunkowskaz"}],
            "word_family_l2": [{"lemma": "la intermitencia", "gloss_l1": "przerywaność"}],
        }
    )
    assert "kierunkowskaz" in terms
    assert "przerywaność" in terms


def test_parse_wiktionary_title_exists():
    assert parse_wiktionary_title_exists({"query": {"pages": {"1": {"pageid": 99, "title": "dom"}}}}) is True
    assert parse_wiktionary_title_exists({"query": {"pages": {"-1": {"missing": "", "title": "przerywaność"}}}}) is False
    assert parse_wiktionary_title_exists(None) is None

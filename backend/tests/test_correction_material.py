"""Tests for correction patch materiality checks."""

from __future__ import annotations

from app.services.card_corrections import patch_is_material


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

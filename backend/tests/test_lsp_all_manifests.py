"""Testy ładowania wszystkich manifestów LSP (16 języków)."""

from __future__ import annotations

import pytest

from app.lsp.constants import SUPPORTED_L2_LANGS
from app.lsp.prompts import build_inflection_prompt
from app.lsp.registry import available_codes, get_manifest, has_manifest


@pytest.mark.parametrize("code", sorted(SUPPORTED_L2_LANGS))
def test_manifest_exists_and_loads(code: str):
    assert has_manifest(code), f"brak manifest.yaml dla {code}"
    m = get_manifest(code)
    assert m.code == code
    assert m.lsp_version
    assert m.name_en


@pytest.mark.parametrize("code", sorted(SUPPORTED_L2_LANGS))
def test_manifest_default_tenses_are_valid(code: str):
    m = get_manifest(code)
    keys = set(m.tense_keys() + m.non_finite_keys())
    for t in m.default_selected_tenses:
        assert t in keys, f"{code}: default tense {t!r} not in catalog"


@pytest.mark.parametrize("code", sorted(SUPPORTED_L2_LANGS))
def test_inflection_prompt_builds(code: str):
    m = get_manifest(code)
    if not m.verbs or not m.verbs.tenses:
        pytest.skip(f"{code}: no verb tenses")
    p = build_inflection_prompt(m, lemma="test", pos="verb", app_lang="pl")
    assert "test" in p
    assert m.code in p or m.name_en in p
    for key in m.default_selected_tenses[:1]:
        assert key in p


def test_available_codes_match_supported():
    assert set(available_codes()) == set(SUPPORTED_L2_LANGS)


def test_android_language_packs_sync():
    """Manifesty LSP ↔ Android LanguagePacks.kt (ten sam kontrakt co scripts/lsp_sync.py)."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "lsp_sync.py")],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


@pytest.mark.parametrize("code", sorted(SUPPORTED_L2_LANGS))
def test_ui_labels_cover_all_ui_langs(code: str):
    m = get_manifest(code)
    keys = set(m.tense_keys() + m.non_finite_keys())
    for ui in sorted(SUPPORTED_L2_LANGS):
        labels = m.ui_labels.get(ui, {})
        missing = sorted(keys - set(labels))
        assert not missing, f"{code} ui_labels[{ui}] brak: {missing}"
        empty = sorted(k for k in keys if not str(labels.get(k, "")).strip())
        assert not empty, f"{code} ui_labels[{ui}] puste: {empty}"

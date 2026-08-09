"""Etykiety czasów z manifestu LSP (app_lang lub learning_lang)."""

from __future__ import annotations

from app.lsp.registry import get_manifest, has_manifest


def tense_label_for(
    learning_lang: str,
    tense_key: str,
    *,
    label_lang: str,
    app_lang: str,
) -> str | None:
    """Zwraca etykietę czasu wg tense_label_lang profilu."""
    if not has_manifest(learning_lang):
        return None
    manifest = get_manifest(learning_lang)
    lang = app_lang if label_lang == "app_lang" else learning_lang
    return manifest.label_for_tense(tense_key, app_lang=lang)

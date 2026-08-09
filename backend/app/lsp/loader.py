"""Wczytywanie manifestów LSP z katalogów językowych."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.lsp.models import LanguageManifest

_LSP_ROOT = Path(__file__).resolve().parent


def lsp_root() -> Path:
    return _LSP_ROOT


def manifest_path(code: str) -> Path:
    return _LSP_ROOT / code.lower().strip() / "manifest.yaml"


def load_manifest(code: str) -> LanguageManifest:
    path = manifest_path(code)
    if not path.is_file():
        raise FileNotFoundError(f"Brak manifestu LSP dla '{code}': {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Niepoprawny manifest LSP: {path}")
    return LanguageManifest.model_validate(raw)

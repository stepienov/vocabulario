"""Rejestr załadowanych pakietów LSP."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.lsp.constants import normalize_l2_code
from app.lsp.loader import lsp_root, load_manifest
from app.lsp.models import LanguageManifest

logger = logging.getLogger(__name__)


class LSPNotImplementedError(Exception):
    """Język jest na liście 16, ale manifest LSP jeszcze nie istnieje."""


@lru_cache(maxsize=32)
def get_manifest(code: str) -> LanguageManifest:
    normalized = normalize_l2_code(code)
    return load_manifest(normalized)


def has_manifest(code: str) -> bool:
    normalized = normalize_l2_code(code)
    return (lsp_root() / normalized / "manifest.yaml").is_file()


def available_codes() -> list[str]:
    codes: list[str] = []
    for path in sorted(lsp_root().iterdir()):
        if path.is_dir() and (path / "manifest.yaml").is_file():
            codes.append(path.name)
    return codes


def require_manifest(code: str) -> LanguageManifest:
    if not has_manifest(code):
        raise LSPNotImplementedError(
            f"LSP dla języka '{code}' nie jest jeszcze zaimplementowany. "
            f"Dostępne: {', '.join(available_codes()) or '(brak)'}"
        )
    return get_manifest(code)

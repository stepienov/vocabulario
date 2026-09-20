"""Independent dictionary evidence for card-correction verdicts (Wiktionary, not the model)."""

from __future__ import annotations

import re
from typing import Any

from app.services.dictionary_lookup import lookup_dictionary_candidates, wiktionary_title_exists

_MAX_L1_CHECKS = 12
_SPLIT_GLOSS = re.compile(r"\s*[;/|]\s*")


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def l1_terms_from_content(content: dict) -> list[str]:
    """Collect UI-language gloss strings from the card (meanings + related lists)."""
    seen: set[str] = set()
    out: list[str] = []

    def add(raw: str | None) -> None:
        text = str(raw or "").strip()
        if not text:
            return
        for part in _SPLIT_GLOSS.split(text):
            piece = part.strip()
            if not piece:
                continue
            key = _norm(piece)
            if key in seen:
                continue
            seen.add(key)
            out.append(piece)

    for meaning in content.get("meanings") or []:
        if isinstance(meaning, dict):
            add(meaning.get("gloss_l1"))
            for syn in meaning.get("synonyms_l1") or []:
                if isinstance(syn, str):
                    add(syn)
    for key in ("synonyms_l2", "antonyms_l2", "word_family_l2", "associations_l2", "similar_words"):
        for item in content.get(key) or []:
            if isinstance(item, dict):
                add(item.get("gloss_l1") or item.get("gloss"))
            elif isinstance(item, str):
                add(item)
    return out


def summarize_candidates(candidates: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in candidates[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "lemma": item.get("lemma"),
                "pos": item.get("pos"),
                "gloss": item.get("gloss"),
            }
        )
    return rows


def both_glosses_attested(old: str | None, new: str | None, evidence: dict) -> bool:
    """True when Wiktionary lists both strings as valid glosses for this lemma."""
    old_n, new_n = _norm(old), _norm(new)
    if not old_n or not new_n or old_n == new_n:
        return False
    glosses = {
        _norm(c.get("gloss"))
        for c in (evidence.get("lemma_candidates") or [])
        if isinstance(c, dict) and c.get("gloss")
    }
    if old_n in glosses and new_n in glosses:
        return True
    # Also: both UI-language pages exist → two real words, not an invented-word fix.
    pages = evidence.get("app_lang_page_exists") or {}
    old_exists = pages.get(old) if old in pages else pages.get(old_n)
    new_exists = pages.get(new) if new in pages else pages.get(new_n)
    if old_exists is not True or new_exists is not True:
        # Try case-insensitive key match
        mapped = {_norm(k): v for k, v in pages.items()}
        old_exists = mapped.get(old_n)
        new_exists = mapped.get(new_n)
    return old_exists is True and new_exists is True


async def gather_correction_evidence(
    content: dict[str, Any],
    *,
    app_lang: str,
    learning_lang: str,
) -> dict[str, Any]:
    lemma = str(content.get("lemma") or "").strip()
    candidates: list[dict] = []
    lookup_error = False
    if lemma:
        try:
            candidates = await lookup_dictionary_candidates(
                lemma, app_lang=app_lang, learning_lang=learning_lang
            )
        except Exception:
            lookup_error = True
            candidates = []

    page_exists: dict[str, bool | None] = {}
    for term in l1_terms_from_content(content)[:_MAX_L1_CHECKS]:
        try:
            page_exists[term] = await wiktionary_title_exists(term, app_lang)
        except Exception:
            page_exists[term] = None

    return {
        "lemma": lemma,
        "lemma_candidates": summarize_candidates(candidates),
        "lookup_empty": not candidates,
        "lookup_error": lookup_error,
        "app_lang_page_exists": page_exists,
    }

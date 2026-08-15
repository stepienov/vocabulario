"""Klasyfikacja zaimportowanych notatek → entry_kind / headword pod karty Vocabulario."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.lsp.lang_utils import articles_for, lemma_preps_for
from app.services.import_format import ensure_deck_segmented
from app.services.import_package import ImportPackageError, RawImportDeck
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

_BATCH = 50


async def resolve_import_vocabulario_entries(
    deck: RawImportDeck,
    *,
    app_lang: str,
    learning_lang: str,
    llm: LLMService | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Segmentacja + klasyfikacja → (valid entries, invalid inputs)."""
    service = llm or LLMService()
    deck = await ensure_deck_segmented(
        deck,
        app_lang=app_lang,
        learning_lang=learning_lang,
        llm=service,
    )
    if not deck.notes:
        raise ImportPackageError("Brak notatek do zaimportowania.")

    notes = deck.notes
    classified: list[dict[str, Any]] = []

    for start in range(0, len(notes), _BATCH):
        chunk = notes[start : start + _BATCH]
        if service.mock:
            batch = _mock_classify(chunk, offset=start, learning_lang=learning_lang)
        else:
            raw = await service.analyze_import_classify(
                native=app_lang,
                learning=learning_lang,
                notes=chunk,
            )
            batch = _normalize_batch(raw, chunk, offset=start, learning_lang=learning_lang)
        classified.extend(batch)

    valid: list[dict[str, Any]] = []
    invalid: list[str] = []
    seen: set[str] = set()

    for item in classified:
        if not item.get("valid"):
            label = (item.get("headword_l2") or item.get("input") or "").strip()
            if label:
                invalid.append(label)
            continue
        head = (item.get("headword_l2") or "").strip()
        if not head:
            continue

        # Vocabulario import = te same karty co lookup/+ : zawsze lemma + pełny enrichment.
        # Zwroty/zdania bez lematu bazowego → invalid (tryb „zachowaj fiszkę” jest do oryginału).
        lemma_out = _vocabulario_lemma(item, learning_lang=learning_lang)
        if not lemma_out:
            invalid.append(head)
            continue

        key = lemma_out.casefold()
        if key in seen:
            continue
        seen.add(key)

        kind = (item.get("entry_kind") or "lemma").strip().lower()
        pos = item.get("pos")
        # Po remapie na base_lemma nie ufamy POS z klasyfikacji zwrotu.
        if kind != "lemma" and lemma_out.casefold() != head.casefold():
            pos = None

        valid.append(
            {
                "input": item.get("input") or head,
                "lemma": lemma_out,
                "pos": pos,
                "gloss": (item.get("gloss_l1") or "").strip(),
                "lexical_entry_id": None,
                "entry_kind": "lemma",
                "base_lemma": None,
                "pattern": None,
            }
        )

    logger.info(
        "import classify → %s valid lemmas, %s invalid (from %s notes)",
        len(valid),
        len(invalid),
        len(notes),
    )
    return valid, invalid


def _vocabulario_lemma(item: dict[str, Any], *, learning_lang: str) -> str | None:
    """Wybierz lemat słownikowy pod pełną kartę Vocabulario (jak lookup)."""
    head = (item.get("headword_l2") or "").strip()
    if not head:
        return None
    kind = (item.get("entry_kind") or "lemma").strip().lower()
    base = (item.get("base_lemma") or "").strip() or None

    if kind == "lemma":
        return head
    if base:
        return base
    # Krótki headword wyglądający jak lemma (np. „el banco”) — dopuszczamy.
    if _guess_kind(head, learning_lang=learning_lang) == "lemma":
        return head
    return None


def _note_input(note: list[str]) -> str:
    return " | ".join(c for c in note if (c or "").strip())[:200]


def _normalize_batch(
    raw: dict,
    chunk: list[list[str]],
    *,
    offset: int,
    learning_lang: str = "es",
) -> list[dict[str, Any]]:
    by_idx: dict[int, dict] = {}
    for e in raw.get("entries") or []:
        if not isinstance(e, dict):
            continue
        try:
            idx = int(e["index"])
        except (KeyError, TypeError, ValueError):
            continue
        by_idx[idx] = e

    out: list[dict[str, Any]] = []
    for i, note in enumerate(chunk):
        global_i = offset + i
        e = by_idx.get(i) or by_idx.get(global_i) or {}
        front = (note[0] if note else "").strip()
        back = (note[1] if len(note) > 1 else "").strip()
        head = (e.get("headword_l2") or front or "").strip()
        gloss = e.get("gloss_l1")
        if gloss is None or gloss == "":
            gloss = back or None
        valid = bool(e.get("valid", True)) if e else bool(head)
        if not head:
            valid = False
        kind = e.get("entry_kind") or _guess_kind(head, learning_lang=learning_lang)
        out.append(
            {
                "index": global_i,
                "input": _note_input(note),
                "valid": valid,
                "entry_kind": kind,
                "headword_l2": head,
                "gloss_l1": gloss,
                "pos": e.get("pos"),
                "base_lemma": e.get("base_lemma"),
                "pattern": e.get("pattern"),
                "invalid_reason": e.get("invalid_reason"),
            }
        )
    return out


def _mock_classify(
    chunk: list[list[str]],
    *,
    offset: int,
    learning_lang: str = "es",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, note in enumerate(chunk):
        front = (note[0] if note else "").strip()
        back = (note[1] if len(note) > 1 else "").strip()
        kind = _guess_kind(front, learning_lang=learning_lang)
        tokens = front.split()
        base = tokens[0].lower() if tokens and kind == "construction" else None
        out.append(
            {
                "index": offset + i,
                "input": _note_input(note),
                "valid": bool(front),
                "entry_kind": kind,
                "headword_l2": front,
                "gloss_l1": back or None,
                "pos": "construction" if kind == "construction" else (
                    "verb" if kind == "lemma" and front.replace("-", "").isalpha() else kind
                ),
                "base_lemma": base,
                "pattern": None,
                "invalid_reason": None if front else "puste",
            }
        )
    return out


def _guess_kind(head: str, *, learning_lang: str = "es") -> str:
    h = (head or "").strip()
    if not h:
        return "other"
    words = h.split()
    articles = {a.lower() for a in articles_for(learning_lang)}
    # Single token, or article + noun (L2-aware).
    if len(words) == 1 or (len(words) == 2 and words[0].lower().rstrip("'") in articles):
        return "lemma"
    if h.endswith((".", "?", "!", "。", "？", "！")) or len(words) >= 6:
        return "sentence"
    preps = {p.lower() for p in lemma_preps_for(learning_lang)}
    particles = preps | {
        # light verbs / particles that form constructions (L2-aware extras)
        *{
            "es": {"que", "se", "lo", "la", "le"},
            "fr": {"y", "en", "ne", "se"},
            "en": {"to", "for", "up", "out", "off", "on"},
            "de": {"zu", "sich", "ein"},
            "it": {"si", "ci", "ne"},
            "pt": {"se", "lhe"},
            "ja": set(),
        }.get((learning_lang or "").lower(), set())
    }
    # Construction: explicit markers or L2 preposition/particle between content words.
    if "+" in h or "·" in h or "〜" in h or "~" in h:
        return "construction"
    if any(w.lower() in particles for w in words[1:]):
        return "construction"
    if len(words) >= 2:
        return "phrase"
    return "other"

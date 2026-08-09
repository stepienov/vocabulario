"""LLM: analiza formatu surowego pliku → instrukcja segmentacji → notatki."""

from __future__ import annotations

import logging

from app.services.import_package import (
    ImportPackageError,
    RawImportDeck,
    apply_import_format,
)
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

_RAW_SAMPLE_CHARS = 9000


async def ensure_deck_segmented(
    deck: RawImportDeck,
    *,
    app_lang: str,
    learning_lang: str,
    llm: LLMService | None = None,
) -> RawImportDeck:
    """Jeśli trzeba — odpytaj LLM o format i przebuduj notes z raw_text."""
    if not deck.needs_format_analysis:
        return deck
    if not deck.raw_text:
        return deck

    service = llm or LLMService()
    sample = deck.raw_text[:_RAW_SAMPLE_CHARS]
    if service.mock:
        fmt = _mock_format_analysis(sample)
    else:
        fmt = await service.analyze_import_format(
            native=app_lang,
            learning=learning_lang,
            kind_hint=deck.kind,
            field_names=deck.field_names,
            raw_sample=sample,
        )

    logger.info(
        "import format: already_segmented=%s card_sep=%s field_delim=%s "
        "field_split=%s row=%s rationale=%s",
        fmt.get("already_segmented"),
        fmt.get("card_separator") or fmt.get("block_separator"),
        fmt.get("field_delimiter"),
        fmt.get("field_split"),
        fmt.get("row_mode"),
        (fmt.get("rationale") or "")[:240],
    )

    if fmt.get("already_segmented"):
        if not deck.notes:
            raise ImportPackageError(
                "AI uznało plik za już posegmentowany, ale nie ma notatek. "
                f"{(fmt.get('rationale') or '')[:200]}"
            )
        return deck

    notes, field_names = apply_import_format(deck.raw_text, fmt)
    if not notes:
        raise ImportPackageError(
            "Po instrukcji formatu AI nie powstały żadne fiszki. "
            f"{(fmt.get('rationale') or '')[:200]}"
        )

    preview = fmt.get("preview_notes") or []
    logger.info(
        "import format applied → %s notes (LLM preview had %s); field_names=%s",
        len(notes),
        len(preview) if isinstance(preview, list) else 0,
        field_names,
    )

    return RawImportDeck(
        kind="notes",
        notes=notes,
        field_names=field_names or deck.field_names,
        meta={**deck.meta, "format_rationale": (fmt.get("rationale") or "")[:500]},
        raw_text=deck.raw_text,
    )


def _mock_format_analysis(sample: str) -> dict:
    """Prosty fallback bez OpenAI — tylko development/mock."""
    has_tab = "\t" in sample
    has_eq = any(ln.strip() == "===" for ln in sample.split("\n"))
    # Quizlet: term,def;term,def w jednej / wielu liniach
    semi_count = sample.count(";")
    comma_count = sample.count(",")
    if semi_count >= 2 and comma_count >= 2 and not has_tab:
        return {
            "already_segmented": False,
            "card_separator": "semicolon",
            "card_separator_value": None,
            "row_mode": "delimited",
            "field_delimiter": "comma",
            "field_split": "first_only",
            "append_continuation_lines_to_answer": False,
            "inferred_field_names": ["Front", "Back"],
            "preview_notes": [],
            "rationale": "mock: Quizlet term,def;term,def",
        }
    if has_eq and has_tab:
        return {
            "already_segmented": False,
            "card_separator": "custom_string",
            "card_separator_value": "===",
            "row_mode": "delimited",
            "field_delimiter": "tab",
            "field_split": "all",
            "append_continuation_lines_to_answer": True,
            "inferred_field_names": ["Front", "Back"],
            "preview_notes": [],
            "rationale": "mock: TSV + bloki ===",
        }
    if has_eq:
        return {
            "already_segmented": False,
            "card_separator": "custom_string",
            "card_separator_value": "===",
            "row_mode": "multiline_first_rest",
            "field_delimiter": "none",
            "field_split": "all",
            "append_continuation_lines_to_answer": False,
            "inferred_field_names": ["Front", "Back"],
            "preview_notes": [],
            "rationale": "mock: bloki ===",
        }
    if has_tab:
        return {
            "already_segmented": False,
            "card_separator": "newline",
            "card_separator_value": None,
            "row_mode": "delimited",
            "field_delimiter": "tab",
            "field_split": "all",
            "append_continuation_lines_to_answer": True,
            "inferred_field_names": ["Front", "Back"],
            "preview_notes": [],
            "rationale": "mock: TSV",
        }
    return {
        "already_segmented": False,
        "card_separator": "blank_lines",
        "card_separator_value": None,
        "row_mode": "multiline_first_rest",
        "field_delimiter": "none",
        "field_split": "all",
        "append_continuation_lines_to_answer": False,
        "inferred_field_names": None,
        "preview_notes": [],
        "rationale": "mock: puste linie",
    }

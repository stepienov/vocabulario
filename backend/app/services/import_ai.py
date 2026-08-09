"""Mapowanie dowolnej talii Anki/CSV/Quizlet na listę haseł — zawsze przez LLM."""

from __future__ import annotations

import json
import logging

from app.ai.prompts.v1 import IMPORT_STRUCTURE_PROMPT_V1
from app.ai.language_typology import lang_name_en
from app.services.import_format import ensure_deck_segmented
from app.services.import_package import (
    ImportPackageError,
    RawImportDeck,
    apply_field_index,
    apply_html_class,
    sample_notes_for_llm,
    words_from_raw_deck_naive,
)
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


async def resolve_import_words(
    deck: RawImportDeck,
    *,
    app_lang: str,
    learning_lang: str,
    llm: LLMService | None = None,
) -> list[str]:
    """Zawsze pyta OpenAI o strategię, potem stosuje ją deterministycznie na całej talii."""
    service = llm or LLMService()
    deck = await ensure_deck_segmented(
        deck,
        app_lang=app_lang,
        learning_lang=learning_lang,
        llm=service,
    )
    if not deck.notes:
        raise ImportPackageError("Brak notatek do zaimportowania.")

    if service.mock:
        words = words_from_raw_deck_naive(deck)
        logger.info("import: LLM mock → naive %s words", len(words))
        return words

    analysis = await service.analyze_import_structure(
        native=app_lang,
        learning=learning_lang,
        kind=deck.kind,
        field_names=deck.field_names,
        sample_notes=sample_notes_for_llm(deck, limit=12),
        total_notes=len(deck.notes),
    )
    words = _apply_analysis(deck, analysis)
    logger.info(
        "import: LLM strategy=%s label=%s → %s words (estimate=%s) rationale=%s",
        analysis.get("strategy"),
        analysis.get("l2_field_label"),
        len(words),
        analysis.get("unique_estimate"),
        (analysis.get("rationale") or "")[:300],
    )
    if not words:
        raise ImportPackageError(
            "Po analizie AI nie powstały żadne hasła. "
            f"Strategia: {analysis.get('strategy')}; "
            f"{(analysis.get('rationale') or '')[:200]}"
        )
    return words


def _apply_analysis(deck: RawImportDeck, analysis: dict) -> list[str]:
    strategy = (analysis.get("strategy") or "").strip()
    if strategy == "plain_list":
        return words_from_raw_deck_naive(deck)

    if strategy == "html_class":
        css = (analysis.get("html_class") or "").strip()
        if not css:
            raise ImportPackageError(
                "AI nie podał klasy HTML z hasłem. "
                f"{(analysis.get('rationale') or '')[:200]}"
            )
        return apply_html_class(deck, css)

    if strategy == "field_index":
        idx = analysis.get("field_index")
        if idx is None:
            raise ImportPackageError(
                "AI nie podał indeksu pola z hasłem. "
                f"{(analysis.get('rationale') or '')[:200]}"
            )
        return apply_field_index(deck, int(idx))

    raise ImportPackageError(
        f"Nieznana strategia AI: {strategy!r}. "
        f"{(analysis.get('rationale') or '')[:200]}"
    )


async def resolve_words_from_upload(
    filename: str | None,
    data: bytes,
    *,
    app_lang: str,
    learning_lang: str,
) -> list[str]:
    from app.services.import_package import load_raw_import

    deck = load_raw_import(filename, data)
    return await resolve_import_words(
        deck,
        app_lang=app_lang,
        learning_lang=learning_lang,
    )


def build_import_structure_prompt(
    *,
    native: str,
    learning: str,
    kind: str,
    field_names: list[str] | None,
    sample_notes: list[list[str]],
    total_notes: int,
) -> str:
    compact = []
    for note in sample_notes:
        row = []
        for cell in note:
            if "<" in cell:
                row.append(cell[:280])
            else:
                row.append(cell)
        compact.append(row)
    return IMPORT_STRUCTURE_PROMPT_V1.format(
        native_name=lang_name_en(native),
        learning_name=lang_name_en(learning),
        kind=kind,
        total_notes=total_notes,
        field_names=json.dumps(field_names, ensure_ascii=False)
        if field_names
        else "nieznane",
        sample_json=json.dumps(compact, ensure_ascii=False, indent=2),
    )

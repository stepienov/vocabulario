"""Orkiestracja enrichmentu przez LSP (vocabulario.card.v1)."""

from __future__ import annotations

import asyncio

from app.ai.prompt_cache import pair_cache_key
from app.core.text_repair import repair_strings
from app.lsp.constants import CARD_SCHEMA_VERSION
from app.lsp.prompts import build_inflection_prompt_parts
from app.lsp.registry import get_manifest
from app.lsp.validate import apply_manifest_ui_labels, inflection_to_legacy_conjugation, validate_inflection
from app.models import LanguageProfile
from app.services.enrichment import (
    MAX_MEANINGS,
    _merge_examples_into_meanings,
    _normalize_related_words,
    _normalize_usages,
    _resolve_pos,
    examples_unique_across_meanings,
    strip_prepositional_construction_meanings,
)
from app.services.llm import LLMService
from app.services.similar_words import fetch_similar_words
from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ, MIN_SIMILAR_WORDS


def _core_examples_valid(meanings: list[dict]) -> bool:
    glosses = [m.get("gloss_l1") for m in meanings if isinstance(m, dict) and m.get("gloss_l1")]
    if not glosses:
        return False
    return examples_unique_across_meanings({"meanings": meanings}, expected=len(glosses))


async def _fetch_core_with_examples(
    llm: LLMService,
    profile: LanguageProfile,
    lemma: str,
    pos: str,
    *,
    gloss_hint: str | None,
) -> dict:
    """Rdzeń + przykłady w jednym callu; fallback na osobny generate_examples (Luna)."""
    core = await llm.enrich_core(
        lemma=lemma,
        pos=pos,
        native=profile.app_lang,
        learning=profile.learning_lang,
        cefr=profile.cefr_level,
        gloss_hint=gloss_hint,
    )
    meanings = [m for m in (core.get("meanings") or []) if isinstance(m, dict)]
    if _core_examples_valid(meanings):
        return core

    core = await llm.enrich_core(
        lemma=lemma,
        pos=pos,
        native=profile.app_lang,
        learning=profile.learning_lang,
        cefr=profile.cefr_level,
        gloss_hint=gloss_hint,
        retry=True,
    )
    meanings = [m for m in (core.get("meanings") or []) if isinstance(m, dict)]
    if _core_examples_valid(meanings):
        return core

    glosses = [m["gloss_l1"] for m in meanings if m.get("gloss_l1")]
    if glosses:
        pos_final = _resolve_pos(core.get("pos")) or _resolve_pos(pos) or "unknown"
        examples_data = await llm.generate_examples(
            lemma=core.get("lemma") or lemma,
            pos=pos_final,
            glosses=glosses,
            native=profile.app_lang,
            learning=profile.learning_lang,
            retry=True,
        )
        _merge_examples_into_meanings(core, examples_data)
    return core


async def enrich_card_content_lsp(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    gloss_hint: str | None = None,
) -> dict:
    """Pełna karta w formacie vocabulario.card.v1 dla języka z manifestem LSP."""
    manifest = get_manifest(profile.learning_lang)
    llm = LLMService()
    app_lang = profile.app_lang
    pos_val = pos or "unknown"

    core = await _fetch_core_with_examples(
        llm, profile, lemma, pos_val, gloss_hint=gloss_hint
    )
    lemma_final = core.get("lemma") or lemma
    pos_final = _resolve_pos(core.get("pos")) or _resolve_pos(pos) or "unknown"

    meanings = [m for m in (core.get("meanings") or []) if isinstance(m, dict)]
    _normalize_usages(meanings)
    meanings = strip_prepositional_construction_meanings(
        lemma_final, meanings, profile.learning_lang
    )
    core["meanings"] = meanings[:MAX_MEANINGS]
    pos_for_related = pos_final if pos_final != "unknown" else None
    core["synonyms_l2"] = _normalize_related_words(
        core.get("synonyms_l2"), fallback_pos=pos_for_related
    )
    core["antonyms_l2"] = _normalize_related_words(
        core.get("antonyms_l2"), fallback_pos=pos_for_related
    )
    family = _normalize_related_words(core.get("word_family_l2"), fallback_pos=None)
    lemma_key = lemma_final.casefold().strip()
    core["word_family_l2"] = [
        w for w in family if (w.get("lemma") or "").casefold().strip() != lemma_key
    ][:10]

    async def fetch_similar() -> list[dict]:
        return await fetch_similar_words(llm, profile, lemma_final, pos_final)

    async def fetch_inflection() -> dict:
        if pos_final not in {"verb", "noun", "adj"}:
            return {}
        static, dynamic = build_inflection_prompt_parts(
            manifest, lemma=lemma_final, pos=pos_final, app_lang=app_lang
        )
        prompt = static + "\n" + dynamic if dynamic else static
        cache_key = pair_cache_key("inflect", app_lang, manifest.code)
        raw = await llm.generate_lsp_inflection(
            prompt,
            cache_key=cache_key if dynamic else None,
            prompt_static=static if dynamic else None,
            prompt_dynamic=dynamic or None,
        )
        return validate_inflection(raw, manifest, pos=pos_final)

    similar, inflection = await asyncio.gather(fetch_similar(), fetch_inflection())

    apply_manifest_ui_labels(inflection, manifest, app_lang=app_lang)

    if len(similar) < MIN_SIMILAR_FOR_QUIZ:
        raise ValueError(
            f"AI zwróciło za mało dystraktorów dla „{lemma_final}” "
            f"({len(similar)}/{MIN_SIMILAR_FOR_QUIZ})."
        )

    ui_hints = core.get("ui_hints") if isinstance(core.get("ui_hints"), dict) else {}
    ui_hints = dict(ui_hints)
    ui_hints.setdefault("script", manifest.script)
    ui_hints["rtl"] = manifest.rtl
    ui_hints["inflection_kind"] = manifest.inflection_kind
    if inflection.get("verbs"):
        ui_hints["show_conjugation"] = True

    conjugation = inflection_to_legacy_conjugation(inflection)

    return repair_strings({
        "schema_version": CARD_SCHEMA_VERSION,
        "lsp_version": manifest.lsp_version,
        "lemma": lemma_final,
        "language": profile.learning_lang,
        "pos": pos_final,
        "ipa": core.get("ipa"),
        "headword_note": core.get("headword_note"),
        "ui_hints": ui_hints,
        "meanings": core["meanings"],
        "synonyms_l2": core.get("synonyms_l2") or [],
        "antonyms_l2": core.get("antonyms_l2") or [],
        "word_family_l2": core.get("word_family_l2") or [],
        "similar_words": similar,
        "inflection": inflection,
        "conjugation": conjugation,
        "language_specific": core.get("language_specific") or {},
        "notes": core.get("notes"),
        "confidence": core.get("confidence"),
    })

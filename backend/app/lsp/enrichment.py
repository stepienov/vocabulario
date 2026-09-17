"""Orkiestracja enrichmentu przez LSP (vocabulario.card.v1)."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.prompt_cache import pair_cache_key
from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ, MIN_SIMILAR_WORDS
from app.core.lemma_keys import canonical_lemma
from app.core.text_repair import repair_strings
from app.lsp.constants import CARD_SCHEMA_VERSION
from app.lsp.lang_utils import articles_for
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
from app.services.word_family_quality import filter_word_family
from app.services.llm import LLMService
from app.services.pos_normalize import normalize_pos_bucket
from app.services.similar_words import fetch_similar_words

logger = logging.getLogger(__name__)

OnCore = Callable[[dict], Awaitable[None]]

_STEM_CHANGE_NOTE = re.compile(
    r"([a-záéíóúüñ])\s*[>:]\s*([a-záéíóúüñ]{1,3})",
    re.IGNORECASE,
)


def normalize_headword_note(raw: object) -> str | None:
    """Keep only a real stem-change mark like (e>ie). Drop regular/empty/invented notes."""
    text = str(raw or "").strip()
    if not text:
        return None
    match = _STEM_CHANGE_NOTE.search(text)
    if not match:
        return None
    src, dst = match.group(1).lower(), match.group(2).lower()
    if src == dst:
        return None
    return f"({src}>{dst})"


def _core_examples_valid(meanings: list[dict]) -> bool:
    glosses = [m.get("gloss_l1") for m in meanings if isinstance(m, dict) and m.get("gloss_l1")]
    if not glosses:
        return False
    return examples_unique_across_meanings({"meanings": meanings}, expected=len(glosses))


def _same_headword(left: str | None, right: str | None) -> bool:
    a = canonical_lemma(left)
    b = canonical_lemma(right)
    return bool(a and b and a == b)


def inflect_pos_key(pos: str | None, lemma: str = "", learning_lang: str = "") -> str | None:
    bucket = _resolve_pos(pos) or "unknown"
    if bucket in {"noun", "adj"}:
        return bucket
    if bucket == "verb":
        return "verb"
    if bucket == "construction":
        return "verb"
    if bucket == "phrase":
        words = (lemma or "").split()
        articles = articles_for(learning_lang)
        if words and words[0].lower().rstrip("'") in articles:
            return None
        return "verb"
    return None


def side_jobs_need_retry(
    lookup_lemma: str,
    lookup_pos: str | None,
    final_lemma: str,
    final_pos: str | None,
) -> tuple[bool, bool]:
    """Czy similar / odmiana odpalone na POS/lemat z lookupu są nieaktualne.

    Lookup często ma już formę hasłową i POS. Retry tylko gdy core je zmieni
    (albo dopiero ustali POS, gdy lookup był unknown).
    """
    lemma_changed = bool(
        lookup_lemma and final_lemma and not _same_headword(lookup_lemma, final_lemma)
    )
    look_p = normalize_pos_bucket(lookup_pos)
    final_p = normalize_pos_bucket(final_pos)
    pos_changed = look_p != final_p and not (
        look_p != "unknown" and final_p == "unknown"
    )
    retry_similar = lemma_changed or pos_changed
    retry_inflection = lemma_changed or (
        inflect_pos_key(lookup_pos, lemma=lookup_lemma)
        != inflect_pos_key(final_pos, lemma=final_lemma)
    )
    return retry_similar, retry_inflection


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


async def fetch_lsp_inflection(
    llm: LLMService,
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
) -> dict:
    pos_final = inflect_pos_key(pos, lemma=lemma, learning_lang=profile.learning_lang)
    if pos_final is None:
        return {}
    manifest = get_manifest(profile.learning_lang)
    app_lang = profile.app_lang
    static, dynamic = build_inflection_prompt_parts(
        manifest, lemma=lemma, pos=pos_final, app_lang=app_lang
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


def assemble_core_card(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    core: dict,
) -> dict:
    """vocabulario.card.v1 z rdzenia — bez similar_words i odmiany."""
    manifest = get_manifest(profile.learning_lang)
    core_lemma = core.get("lemma") or lemma
    # Headword z lookupu zostaje; LLM nie może „naprawić” karty tłumaczeniem na inny język.
    if lemma and core_lemma and not _same_headword(lemma, core_lemma):
        lemma_final = lemma
    else:
        lemma_final = core_lemma or lemma
    pos_lookup = _resolve_pos(pos) or pos or "unknown"
    if pos_lookup in {"phrase", "construction"}:
        pos_final = pos_lookup
    else:
        pos_final = _resolve_pos(core.get("pos")) or pos_lookup or "unknown"

    meanings = [m for m in (core.get("meanings") or []) if isinstance(m, dict)]
    _normalize_usages(meanings)
    meanings = strip_prepositional_construction_meanings(
        lemma_final, meanings, profile.learning_lang
    )
    meanings = meanings[:MAX_MEANINGS]
    pos_for_related = pos_final if pos_final != "unknown" else None
    lang = profile.learning_lang
    synonyms = _normalize_related_words(
        core.get("synonyms_l2"), fallback_pos=pos_for_related, learning_lang=lang
    )
    antonyms = _normalize_related_words(
        core.get("antonyms_l2"), fallback_pos=pos_for_related, learning_lang=lang
    )
    family = _normalize_related_words(
        core.get("word_family_l2"), fallback_pos=None, learning_lang=lang
    )
    family, antonyms = filter_word_family(
        lemma_final, pos_final, family, antonyms, lang
    )

    ui_hints = core.get("ui_hints") if isinstance(core.get("ui_hints"), dict) else {}
    ui_hints = dict(ui_hints)
    ui_hints.setdefault("script", manifest.script)
    ui_hints["rtl"] = manifest.rtl
    ui_hints["inflection_kind"] = manifest.inflection_kind
    if inflect_pos_key(pos_final, lemma=lemma_final, learning_lang=profile.learning_lang) == "verb":
        ui_hints.setdefault("show_conjugation", True)

    return repair_strings({
        "schema_version": CARD_SCHEMA_VERSION,
        "entry_kind": "lemma",
        "lsp_version": manifest.lsp_version,
        "lemma": lemma_final,
        "language": profile.learning_lang,
        "pos": pos_final,
        "ipa": core.get("ipa"),
        "headword_note": normalize_headword_note(core.get("headword_note")),
        "ui_hints": ui_hints,
        "meanings": meanings,
        "synonyms_l2": synonyms,
        "antonyms_l2": antonyms,
        "word_family_l2": family,
        "similar_words": [],
        "inflection": None,
        "conjugation": None,
        "language_specific": core.get("language_specific") or {},
        "notes": core.get("notes"),
        "confidence": core.get("confidence"),
    })


def merge_side_jobs(
    card: dict,
    similar: list[dict] | None,
    inflection: dict | None,
    profile: LanguageProfile,
) -> dict:
    """Dokleja dystraktory i odmianę do karty z rdzenia."""
    merged = dict(card)
    if similar:
        merged["similar_words"] = similar
    inflection = inflection or {}
    if inflection:
        manifest = get_manifest(profile.learning_lang)
        apply_manifest_ui_labels(inflection, manifest, app_lang=profile.app_lang)
        merged["inflection"] = inflection
        merged["conjugation"] = inflection_to_legacy_conjugation(inflection)
        ui_hints = dict(merged.get("ui_hints") or {})
        if inflection.get("verbs"):
            ui_hints["show_conjugation"] = True
        merged["ui_hints"] = ui_hints
    return repair_strings(merged)


async def _await_task(task: asyncio.Task, default: Any) -> Any:
    try:
        return await task
    except asyncio.CancelledError:
        return default
    except Exception:
        logger.exception("Side-job enrichment failed")
        return default


def _cancel_if_pending(task: asyncio.Task | None) -> None:
    if task is not None and not task.done():
        task.cancel()


async def finish_side_jobs(
    profile: LanguageProfile,
    content: dict,
    *,
    llm: LLMService | None = None,
) -> dict:
    """Dociąga brakujące similar_words / odmianę do karty, która ma już rdzeń."""
    llm = llm or LLMService()
    lemma = content.get("lemma") or ""
    pos = content.get("pos")
    need_similar = len(content.get("similar_words") or []) < MIN_SIMILAR_WORDS
    has_infl = bool(content.get("inflection") or content.get("conjugation"))
    need_inflection = inflect_pos_key(
        pos, lemma=lemma, learning_lang=profile.learning_lang
    ) is not None and not has_infl

    similar_task = (
        asyncio.create_task(fetch_similar_words(llm, profile, lemma, pos))
        if need_similar
        else None
    )
    inflection_task = (
        asyncio.create_task(fetch_lsp_inflection(llm, profile, lemma, pos))
        if need_inflection
        else None
    )
    similar = (
        await _await_task(similar_task, content.get("similar_words") or [])
        if similar_task
        else (content.get("similar_words") or [])
    )
    inflection = (
        await _await_task(inflection_task, content.get("inflection") or {})
        if inflection_task
        else (content.get("inflection") or {})
    )
    return merge_side_jobs(content, similar, inflection, profile)


async def run_lemma_enrichment(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    gloss_hint: str | None = None,
    on_core: OnCore | None = None,
    require_similar: bool = True,
    llm: LLMService | None = None,
) -> dict:
    """Pełna karta: core ∥ similar ∥ inflection; retry side-jobs gdy core zmieni POS/lemat.

    ``on_core`` dostaje kartę zaraz po rdzeniu (learnable), zanim skończą się side-jobs.
    """
    llm = llm or LLMService()
    pos_lookup = _resolve_pos(pos) or pos or "unknown"

    core_task = asyncio.create_task(
        _fetch_core_with_examples(llm, profile, lemma, pos_lookup, gloss_hint=gloss_hint)
    )
    similar_task: asyncio.Task | None = asyncio.create_task(
        fetch_similar_words(llm, profile, lemma, pos_lookup)
    )
    inflection_task: asyncio.Task = asyncio.create_task(
        fetch_lsp_inflection(llm, profile, lemma, pos_lookup)
    )

    try:
        core = await core_task
    except Exception:
        _cancel_if_pending(similar_task)
        _cancel_if_pending(inflection_task)
        raise

    from app.services.related_articles import fill_related_articles_on_core

    await fill_related_articles_on_core(llm, core, profile.learning_lang)
    card = assemble_core_card(profile, lemma, pos_lookup, core)
    lemma_final = card.get("lemma") or lemma
    pos_final = card.get("pos") or pos_lookup

    if on_core is not None:
        try:
            await on_core(dict(card))
        except Exception:
            logger.exception("on_core callback failed for %r", lemma_final)

    retry_similar, retry_inflection = side_jobs_need_retry(
        lemma, pos_lookup, lemma_final, pos_final
    )
    if retry_similar:
        _cancel_if_pending(similar_task)
        if similar_task is not None:
            await _await_task(similar_task, [])
        similar_task = asyncio.create_task(
            fetch_similar_words(llm, profile, lemma_final, pos_final)
        )
    if retry_inflection:
        _cancel_if_pending(inflection_task)
        await _await_task(inflection_task, {})
        inflection_task = asyncio.create_task(
            fetch_lsp_inflection(llm, profile, lemma_final, pos_final)
        )

    similar = (
        await _await_task(similar_task, [])
        if similar_task is not None
        else []
    )
    inflection = await _await_task(inflection_task, {})
    card = merge_side_jobs(card, similar, inflection, profile)

    if require_similar and len(card.get("similar_words") or []) < MIN_SIMILAR_FOR_QUIZ:
        raise ValueError(
            f"AI zwróciło za mało dystraktorów dla „{lemma_final}” "
            f"({len(card.get('similar_words') or [])}/{MIN_SIMILAR_FOR_QUIZ})."
        )
    return card


async def enrich_card_content_lsp(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    gloss_hint: str | None = None,
) -> dict:
    """Pełna karta w formacie vocabulario.card.v1 dla języka z manifestem LSP."""
    return await run_lemma_enrichment(
        profile, lemma, pos, gloss_hint=gloss_hint, require_similar=True
    )

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
    filter_associations,
    strip_prepositional_construction_meanings,
)
from app.services.word_family_quality import filter_word_family
from app.services.llm import LLMService
from app.services.pos_normalize import normalize_pos_bucket
from app.services.similar_words import fetch_similar_words

logger = logging.getLogger(__name__)

OnMeanings = Callable[[dict], Awaitable[None]]
OnStudy = Callable[[dict], Awaitable[None]]
OnRelated = Callable[[dict], Awaitable[None]]
# Alias dla starych testów / wywołań.
OnCore = OnStudy

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


def has_required_inflection(
    content: dict, *, pos: str, lemma: str, learning_lang: str
) -> bool:
    """Odmiana, której LSP chce dla tego POS. Puste klucze to brak, nie sukces."""
    if content.get("inflection_status") == "not_applicable":
        return True
    key = inflect_pos_key(pos, lemma=lemma, learning_lang=learning_lang)
    if key is None:
        return True
    inf = content.get("inflection") if isinstance(content.get("inflection"), dict) else {}
    if key == "noun":
        nouns = inf.get("nouns") if isinstance(inf.get("nouns"), dict) else None
        return bool(nouns)
    if key == "adj":
        adjs = inf.get("adjectives") if isinstance(inf.get("adjectives"), dict) else None
        return bool(adjs)
    verbs = inf.get("verbs") if isinstance(inf, dict) else None
    has_forms = isinstance(verbs, dict) and (verbs.get("tenses") or verbs.get("non_finite"))
    return bool(has_forms or content.get("conjugation"))


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


def _locked_glosses(meanings: list) -> list[str]:
    out: list[str] = []
    for m in meanings:
        if isinstance(m, dict):
            g = str(m.get("gloss_l1") or "").strip()
            if g:
                out.append(g)
    return out


def _glosses_match_locked(locked: list[str], finished: dict) -> bool:
    got = _locked_glosses(finished.get("meanings") or [])
    return got == locked


def _force_locked_glosses(locked: list[str], finished: dict) -> dict:
    data = dict(finished)
    meanings = [m for m in (data.get("meanings") or []) if isinstance(m, dict)]
    forced: list[dict] = []
    for i, gloss in enumerate(locked):
        base = dict(meanings[i]) if i < len(meanings) else {}
        base["gloss_l1"] = gloss
        forced.append(base)
    data["meanings"] = forced
    return data


async def _fetch_meanings(
    llm: LLMService,
    profile: LanguageProfile,
    lemma: str,
    pos: str,
    *,
    gloss_hint: str | None,
) -> dict:
    return await llm.enrich_meanings(profile, lemma, pos, gloss_hint)


async def _fetch_study_finish(
    llm: LLMService,
    profile: LanguageProfile,
    lemma: str,
    pos: str,
    locked_meanings: list[dict],
) -> dict:
    locked = _locked_glosses(locked_meanings)
    study = await llm.enrich_study_finish(profile, lemma, pos, locked_meanings)
    if not _glosses_match_locked(locked, study):
        study = await llm.enrich_study_finish(profile, lemma, pos, locked_meanings)
    if not _glosses_match_locked(locked, study):
        study = _force_locked_glosses(locked, study)

    meanings = [m for m in (study.get("meanings") or []) if isinstance(m, dict)]
    if _core_examples_valid(meanings):
        return study

    glosses = _locked_glosses(meanings) or locked
    if glosses:
        pos_final = _resolve_pos(study.get("pos")) or _resolve_pos(pos) or "unknown"
        examples_data = await llm.generate_examples(
            lemma=study.get("lemma") or lemma,
            pos=pos_final,
            glosses=glosses,
            native=profile.app_lang,
            learning=profile.learning_lang,
            retry=True,
        )
        _merge_examples_into_meanings(study, examples_data)
        study = _force_locked_glosses(locked or glosses, study)
    return study


# Kompatybilność starych testów: patchowali `_fetch_core_with_examples`.
async def _fetch_core_with_examples(
    llm: LLMService,
    profile: LanguageProfile,
    lemma: str,
    pos: str,
    *,
    gloss_hint: str | None,
) -> dict:
    meanings = await _fetch_meanings(
        llm, profile, lemma, pos, gloss_hint=gloss_hint
    )
    locked = [
        {"gloss_l1": g}
        for g in _locked_glosses(meanings.get("meanings") or [])
    ]
    if not locked:
        locked = [{"gloss_l1": gloss_hint or "bedeutung"}]
    return await _fetch_study_finish(
        llm, profile, meanings.get("lemma") or lemma, pos, locked
    )


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


def _resolve_lemma_pos(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    payload: dict,
) -> tuple[str, str]:
    payload_lemma = payload.get("lemma") or lemma
    pos_lookup = _resolve_pos(pos) or pos or "unknown"
    if lemma and payload_lemma and not _same_headword(lemma, payload_lemma):
        lemma_final = lemma
    else:
        from app.services.pos_normalize import prefer_citation_headword

        lemma_final = prefer_citation_headword(
            lemma,
            payload_lemma,
            pos=pos_lookup,
            learning_lang=profile.learning_lang,
        ) or payload_lemma or lemma
    if pos_lookup in {"phrase", "construction"}:
        pos_final = pos_lookup
    else:
        pos_final = _resolve_pos(payload.get("pos")) or pos_lookup or "unknown"
    return str(lemma_final), str(pos_final)


def assemble_meanings_card(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    meanings_payload: dict,
) -> dict:
    """Sama lista glos — bez zdań; examples_pending + related_pending."""
    manifest = get_manifest(profile.learning_lang)
    lemma_final, pos_final = _resolve_lemma_pos(profile, lemma, pos, meanings_payload)
    raw = [m for m in (meanings_payload.get("meanings") or []) if isinstance(m, dict)]
    meanings: list[dict] = []
    for m in raw[:MAX_MEANINGS]:
        gloss = str(m.get("gloss_l1") or "").strip()
        if not gloss:
            continue
        meanings.append(
            {
                "gloss_l1": gloss,
                "synonyms_l1": [],
                "examples": [],
                "usages": [],
            }
        )
    meanings = strip_prepositional_construction_meanings(
        lemma_final, meanings, profile.learning_lang
    )
    ui_hints = {
        "script": manifest.script,
        "rtl": manifest.rtl,
        "inflection_kind": manifest.inflection_kind,
    }
    if inflect_pos_key(pos_final, lemma=lemma_final, learning_lang=profile.learning_lang) == "verb":
        ui_hints["show_conjugation"] = True
    return repair_strings({
        "schema_version": CARD_SCHEMA_VERSION,
        "entry_kind": "lemma",
        "lsp_version": manifest.lsp_version,
        "lemma": lemma_final,
        "language": profile.learning_lang,
        "pos": pos_final,
        "ipa": None,
        "headword_note": None,
        "ui_hints": ui_hints,
        "meanings": meanings,
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
        "associations_l2": [],
        "similar_words": [],
        "inflection": None,
        "conjugation": None,
        "language_specific": {},
        "notes": None,
        "confidence": None,
        "examples_pending": True,
        "related_pending": True,
    })


def assemble_study_card(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    study: dict,
) -> dict:
    """vocabulario.card.v1 — pełna nauka (bez powiązanych, similar, odmiany)."""
    manifest = get_manifest(profile.learning_lang)
    lemma_final, pos_final = _resolve_lemma_pos(profile, lemma, pos, study)

    meanings = [m for m in (study.get("meanings") or []) if isinstance(m, dict)]
    _normalize_usages(meanings)
    meanings = strip_prepositional_construction_meanings(
        lemma_final, meanings, profile.learning_lang
    )
    meanings = meanings[:MAX_MEANINGS]

    ui_hints = study.get("ui_hints") if isinstance(study.get("ui_hints"), dict) else {}
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
        "ipa": study.get("ipa"),
        "headword_note": normalize_headword_note(study.get("headword_note")),
        "ui_hints": ui_hints,
        "meanings": meanings,
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
        "associations_l2": [],
        "similar_words": [],
        "inflection": None,
        "conjugation": None,
        "language_specific": {},
        "notes": None,
        "confidence": None,
        "related_pending": True,
    })


def merge_study_finish_into_card(card: dict, finished: dict) -> dict:
    """Dokleja IPA/note/examples/usages z finish; zdejmuje examples_pending."""
    out = dict(card)
    if finished.get("ipa") is not None:
        out["ipa"] = finished.get("ipa")
    if "headword_note" in finished:
        out["headword_note"] = normalize_headword_note(finished.get("headword_note"))
    fin_meanings = [m for m in (finished.get("meanings") or []) if isinstance(m, dict)]
    base_meanings = [m for m in (out.get("meanings") or []) if isinstance(m, dict)]
    merged: list[dict] = []
    for i, base in enumerate(base_meanings):
        row = dict(base)
        src = fin_meanings[i] if i < len(fin_meanings) else {}
        if src.get("examples"):
            row["examples"] = src["examples"]
        if src.get("usages") is not None:
            row["usages"] = src["usages"]
        merged.append(row)
    if merged:
        _normalize_usages(merged)
        out["meanings"] = merged
    out.pop("examples_pending", None)
    return repair_strings(out)


def assemble_related_part(
    profile: LanguageProfile,
    lemma_final: str,
    pos_final: str | None,
    related: dict,
) -> dict:
    """Cztery listy powiązanych po normalizacji i filtrach."""
    pos_for_related = (
        (_resolve_pos(pos_final) or pos_final)
        if pos_final and pos_final != "unknown"
        else None
    )
    lang = profile.learning_lang
    synonyms = _normalize_related_words(
        related.get("synonyms_l2"), fallback_pos=pos_for_related, learning_lang=lang
    )
    antonyms = _normalize_related_words(
        related.get("antonyms_l2"), fallback_pos=pos_for_related, learning_lang=lang
    )
    family = _normalize_related_words(
        related.get("word_family_l2"), fallback_pos=None, learning_lang=lang
    )
    family, antonyms = filter_word_family(
        lemma_final, pos_final or "unknown", family, antonyms, lang
    )
    associations = _normalize_related_words(
        related.get("associations_l2"), fallback_pos=None, learning_lang=lang
    )
    associations = filter_associations(
        lemma_final,
        associations,
        synonyms=synonyms,
        antonyms=antonyms,
        family=family,
    )
    return {
        "synonyms_l2": synonyms,
        "antonyms_l2": antonyms,
        "word_family_l2": family,
        "associations_l2": associations,
    }


def assemble_core_card(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    core: dict,
) -> dict:
    """Składa naukę + powiązane (bez related_pending) — kompatybilność testów."""
    card = assemble_study_card(profile, lemma, pos, core)
    part = assemble_related_part(profile, card["lemma"], card.get("pos"), core)
    card.update(part)
    card.pop("related_pending", None)
    if "language_specific" in core:
        card["language_specific"] = core.get("language_specific") or {}
    if "notes" in core:
        card["notes"] = core.get("notes")
    if "confidence" in core:
        card["confidence"] = core.get("confidence")
    return repair_strings(card)


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


async def _await_inflection(task: asyncio.Task) -> dict | None:
    """None = błąd albo anulowanie. Słownik, także pusty, = odpowiedź modelu."""
    try:
        result = await task
    except asyncio.CancelledError:
        return None
    except Exception:
        logger.exception("Side-job enrichment failed")
        return None
    return result if isinstance(result, dict) else {}


def inflection_not_applicable(
    content: dict,
    inflection: dict | None,
    *,
    pos: str,
    lemma: str,
    learning_lang: str,
) -> bool:
    """Pusta, poprawna odpowiedź dla zwrotu: odmiana tego hasła nie dotyczy."""
    if inflection is None:
        return False
    bucket = _resolve_pos(pos)
    if bucket not in {"phrase", "construction"}:
        return False
    if inflect_pos_key(pos, lemma=lemma, learning_lang=learning_lang) != "verb":
        return False
    probe = dict(content)
    probe["inflection"] = inflection
    probe["conjugation"] = None
    probe.pop("inflection_status", None)
    return not has_required_inflection(
        probe, pos=pos, lemma=lemma, learning_lang=learning_lang
    )


def _with_inflection_outcome(
    content: dict,
    similar: list[dict] | None,
    inflection: dict | None,
    profile: LanguageProfile,
    *,
    pos: str,
    lemma: str,
) -> dict:
    if inflection is not None and inflection_not_applicable(
        content,
        inflection,
        pos=pos,
        lemma=lemma,
        learning_lang=profile.learning_lang,
    ):
        merged = merge_side_jobs(content, similar, {}, profile)
        merged["inflection"] = None
        merged["conjugation"] = None
        merged["inflection_status"] = "not_applicable"
        return merged
    return merge_side_jobs(content, similar, inflection or {}, profile)


def _cancel_if_pending(task: asyncio.Task | None) -> None:
    if task is not None and not task.done():
        task.cancel()


async def _fetch_related_part(
    llm: LLMService,
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    gloss_hint: str | None,
) -> dict:
    from app.services.related_articles import fill_related_articles_on_core

    related = await llm.enrich_related(profile, lemma, pos, gloss_hint)
    await fill_related_articles_on_core(llm, related, profile.learning_lang)
    return assemble_related_part(profile, lemma, pos, related)


async def finish_side_jobs(
    profile: LanguageProfile,
    content: dict,
    *,
    llm: LLMService | None = None,
) -> dict:
    """Dociąga brakujące powiązane / similar_words / odmianę do karty z nauką."""
    llm = llm or LLMService()
    lemma = str(content.get("lemma") or "")
    pos = str(content.get("pos") or "")
    gloss = None
    meanings = content.get("meanings") or []
    if meanings and isinstance(meanings[0], dict):
        gloss = meanings[0].get("gloss_l1")
    need_related = bool(content.get("related_pending"))
    need_similar = len(content.get("similar_words") or []) < MIN_SIMILAR_WORDS
    need_inflection = not has_required_inflection(
        content, pos=pos, lemma=lemma, learning_lang=profile.learning_lang
    )

    related_task = (
        asyncio.create_task(
            _fetch_related_part(llm, profile, lemma, pos, gloss_hint=gloss)
        )
        if need_related
        else None
    )
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

    out = dict(content)
    if related_task is not None:
        try:
            part = await related_task
        except Exception:
            logger.exception("finish_side_jobs related failed for %r", lemma)
            part = None
        if isinstance(part, dict):
            out.update(part)
            out.pop("related_pending", None)

    similar = (
        await _await_task(similar_task, out.get("similar_words") or [])
        if similar_task
        else (out.get("similar_words") or [])
    )
    if inflection_task is None:
        existing = out.get("inflection")
        return merge_side_jobs(
            out,
            similar,
            existing if isinstance(existing, dict) else {},
            profile,
        )
    inflection = await _await_inflection(inflection_task)
    return _with_inflection_outcome(
        out, similar, inflection, profile, pos=pos, lemma=lemma
    )


async def run_lemma_enrichment(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    gloss_hint: str | None = None,
    on_meanings: OnMeanings | None = None,
    on_study: OnStudy | None = None,
    on_related: OnRelated | None = None,
    on_core: OnCore | None = None,
    require_similar: bool = True,
    llm: LLMService | None = None,
) -> dict:
    """meanings ∥ related ∥ similar ∥ odmiana; study_finish po meanings.

    ``on_meanings`` — glosy (`examples_pending`), status bez ``learnable``.
    ``on_study`` (alias ``on_core``) — po finish, treść learnable.
    ``on_related`` — dokleja powiązane po pierwszym zapisie (meanings lub study).
    """
    llm = llm or LLMService()
    on_study = on_study or on_core
    pos_lookup = _resolve_pos(pos) or pos or "unknown"

    meanings_task: asyncio.Task = asyncio.create_task(
        _fetch_meanings(llm, profile, lemma, pos_lookup, gloss_hint=gloss_hint)
    )
    related_task: asyncio.Task | None = asyncio.create_task(
        _fetch_related_part(
            llm, profile, lemma, pos_lookup, gloss_hint=gloss_hint
        )
    )
    similar_task: asyncio.Task | None = asyncio.create_task(
        fetch_similar_words(llm, profile, lemma, pos_lookup)
    )
    inflection_task: asyncio.Task | None = asyncio.create_task(
        fetch_lsp_inflection(llm, profile, lemma, pos_lookup)
    )
    finish_task: asyncio.Task | None = None

    card: dict | None = None
    related_part: dict | None = None
    related_done = False
    related_failed = False
    meanings_delivered = False
    study_delivered = False
    lemma_final = lemma
    pos_final = pos_lookup
    similar: list | None = None
    inflection: dict | None = None

    pending: set[asyncio.Task] = {
        t
        for t in (meanings_task, related_task, similar_task, inflection_task)
        if t is not None
    }

    def _discard(task: asyncio.Task | None) -> None:
        if task is not None:
            pending.discard(task)

    async def _emit_related() -> None:
        nonlocal card
        if related_part is None or card is None:
            return
        if on_related is not None and meanings_delivered:
            try:
                await on_related(dict(related_part))
            except Exception:
                logger.exception("on_related callback failed for %r", lemma_final)
            card.update(related_part)
            card.pop("related_pending", None)
        elif not meanings_delivered:
            return
        else:
            card.update(related_part)
            card.pop("related_pending", None)

    while pending:
        done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            pending.discard(task)

            if task is meanings_task:
                try:
                    meanings_payload = task.result()
                except Exception:
                    _cancel_if_pending(related_task)
                    _cancel_if_pending(similar_task)
                    _cancel_if_pending(inflection_task)
                    raise
                card = assemble_meanings_card(
                    profile, lemma, pos_lookup, meanings_payload
                )
                lemma_final = card.get("lemma") or lemma
                pos_final = card.get("pos") or pos_lookup
                if related_part is not None:
                    card.update(related_part)
                    card.pop("related_pending", None)
                if on_meanings is not None:
                    try:
                        await on_meanings(dict(card))
                    except Exception:
                        logger.exception(
                            "on_meanings callback failed for %r", lemma_final
                        )
                meanings_delivered = True

                retry_similar, retry_inflection = side_jobs_need_retry(
                    lemma, pos_lookup, lemma_final, pos_final
                )
                retry_related = retry_similar
                if retry_related and not related_done:
                    _cancel_if_pending(related_task)
                    if related_task is not None:
                        await _await_task(related_task, {})
                        _discard(related_task)
                    related_part = None
                    related_failed = False
                    related_task = asyncio.create_task(
                        _fetch_related_part(
                            llm,
                            profile,
                            lemma_final,
                            pos_final,
                            gloss_hint=gloss_hint,
                        )
                    )
                    pending.add(related_task)
                if retry_similar:
                    _cancel_if_pending(similar_task)
                    if similar_task is not None:
                        await _await_task(similar_task, [])
                        _discard(similar_task)
                    similar = None
                    similar_task = asyncio.create_task(
                        fetch_similar_words(llm, profile, lemma_final, pos_final)
                    )
                    pending.add(similar_task)
                if retry_inflection:
                    _cancel_if_pending(inflection_task)
                    if inflection_task is not None:
                        await _await_task(inflection_task, {})
                        _discard(inflection_task)
                    inflection = None
                    inflection_task = asyncio.create_task(
                        fetch_lsp_inflection(llm, profile, lemma_final, pos_final)
                    )
                    pending.add(inflection_task)

                locked = [
                    {"gloss_l1": str(m.get("gloss_l1") or "").strip()}
                    for m in (card.get("meanings") or [])
                    if isinstance(m, dict) and str(m.get("gloss_l1") or "").strip()
                ]
                if not locked:
                    locked = [{"gloss_l1": (gloss_hint or "bedeutung").strip()}]
                finish_task = asyncio.create_task(
                    _fetch_study_finish(
                        llm, profile, lemma_final, pos_final, locked
                    )
                )
                pending.add(finish_task)
                continue

            if finish_task is not None and task is finish_task:
                try:
                    finished = task.result()
                except Exception:
                    _cancel_if_pending(related_task)
                    _cancel_if_pending(similar_task)
                    _cancel_if_pending(inflection_task)
                    raise
                card = assemble_study_card(profile, lemma, pos_lookup, finished)
                lemma_final = card.get("lemma") or lemma_final
                pos_final = card.get("pos") or pos_final
                if related_part is not None:
                    card.update(related_part)
                    card.pop("related_pending", None)
                elif related_failed:
                    card.setdefault("related_pending", True)
                if on_study is not None:
                    try:
                        await on_study(dict(card))
                    except Exception:
                        logger.exception("on_study callback failed for %r", lemma_final)
                study_delivered = True
                continue

            if task is related_task:
                related_done = True
                try:
                    related_part = task.result()
                except Exception:
                    logger.exception("enrich_related failed for %r", lemma)
                    related_part = None
                    related_failed = True
                    continue
                if meanings_delivered and related_part is not None:
                    await _emit_related()
                continue

            if task is similar_task:
                similar = await _await_task(task, [])
                continue

            if task is inflection_task:
                inflection = await _await_inflection(task)
                continue

    if card is None or not study_delivered:
        raise RuntimeError("enrich_study_finish did not return a card")

    if related_part is not None and card.get("related_pending"):
        card.update(related_part)
        card.pop("related_pending", None)
    elif related_failed:
        card.setdefault("related_pending", True)

    card = _with_inflection_outcome(
        card,
        similar if similar is not None else [],
        inflection,
        profile,
        pos=str(pos_final or ""),
        lemma=str(lemma_final or ""),
    )

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

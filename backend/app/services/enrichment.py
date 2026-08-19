"""Orkiestracja enrichmentu — równoległe, mniejsze wywołania LLM."""

from __future__ import annotations

import re

from app.lsp.lang_utils import articles_for, lemma_preps_for
from app.services.pos_normalize import normalize_pos_bucket
from app.models import LanguageProfile
from app.services.llm import LLMService

# Jedno zdanie na pasmo poziomów: A2 widzi A1–A2, B2 widzi B1–B2, C2 widzi C1–C2.
EXAMPLE_CEFR_LEVELS = ["A2", "B2", "C2"]

# Jedno znaczenie główne i do dwóch pobocznych — sensy bliskoznaczne grupuje prompt.
MAX_MEANINGS = 3


def _count_examples_by_cefr(examples: list[dict]) -> dict[str, int]:
    counts = {level: 0 for level in EXAMPLE_CEFR_LEVELS}
    for item in examples:
        if not isinstance(item, dict):
            continue
        level = (item.get("cefr") or "").upper()
        if level in counts:
            counts[level] += 1
    return counts


def examples_complete(examples: list[dict]) -> bool:
    counts = _count_examples_by_cefr(examples)
    return all(counts[level] >= 1 for level in EXAMPLE_CEFR_LEVELS)


def _norm_example_l2(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().split())


def examples_unique_across_meanings(examples_payload: dict, *, expected: int) -> bool:
    """True gdy każde znaczenie ma komplet CEFR i żadne l2 nie powtarza się między sensami."""
    meanings = examples_payload.get("meanings") or []
    if not isinstance(meanings, list) or len(meanings) < expected:
        return False
    seen: set[str] = set()
    for meaning in meanings[:expected]:
        if not isinstance(meaning, dict):
            return False
        examples = meaning.get("examples")
        if not isinstance(examples, list) or not examples_complete(examples):
            return False
        for item in examples:
            if not isinstance(item, dict):
                return False
            key = _norm_example_l2(item.get("l2"))
            if not key or key in seen:
                return False
            seen.add(key)
    return True


def _merge_examples_into_meanings(core: dict, examples_payload: dict) -> None:
    """Przypina examples do meanings.

    Najpierw po indeksie (ta sama kolejność co w prompcie) — krytyczne gdy dwa
    sensy mają identyczny/podobny gloss_l1 (wcześniej oba brały pierwszy match).
    Dopiero potem unikalny match po gloss_l1.
    """
    core_meanings = core.get("meanings") or []
    ex_meanings = examples_payload.get("meanings") or []
    if not isinstance(core_meanings, list) or not isinstance(ex_meanings, list):
        return

    used_ex: set[int] = set()
    for idx, meaning in enumerate(core_meanings):
        if not isinstance(meaning, dict):
            continue
        source = None
        if idx < len(ex_meanings) and isinstance(ex_meanings[idx], dict):
            source = ex_meanings[idx]
            used_ex.add(idx)
        else:
            gloss = meaning.get("gloss_l1")
            if gloss:
                matches = [
                    (j, m)
                    for j, m in enumerate(ex_meanings)
                    if j not in used_ex
                    and isinstance(m, dict)
                    and m.get("gloss_l1") == gloss
                ]
                if len(matches) == 1:
                    j, source = matches[0]
                    used_ex.add(j)
        if source and isinstance(source.get("examples"), list):
            meaning["examples"] = source["examples"]


def _resolve_pos(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    bucket = normalize_pos_bucket(value)
    return None if bucket == "unknown" else bucket


def _normalize_related_words(
    raw: object,
    *,
    fallback_pos: str | None,
) -> list[dict]:
    """synonyms_l2 / antonyms_l2 zawsze jako {lemma, pos, gloss_l1}."""
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, dict) and item.get("lemma"):
            lemma = str(item["lemma"]).strip()
            gloss = str(item.get("gloss_l1") or item.get("gloss") or "").strip()
            pos = _resolve_pos(item.get("pos")) or _resolve_pos(fallback_pos)
        elif isinstance(item, str) and item.strip():
            lemma = item.strip()
            gloss = ""
            pos = _resolve_pos(fallback_pos)
        else:
            continue
        key = lemma.lower()
        if not lemma or key in seen:
            continue
        seen.add(key)
        entry = {"lemma": lemma, "gloss_l1": gloss or "?"}
        if pos:
            entry["pos"] = pos
        result.append(entry)
    return result


def _normalize_usages(meanings: list[dict]) -> None:
    """Usages zawsze jako {l2, l1} — model czasem zwraca same stringi L2."""
    for meaning in meanings:
        raw = meaning.get("usages") or []
        if not isinstance(raw, list):
            meaning["usages"] = []
            continue
        normalized: list[dict] = []
        for item in raw:
            if isinstance(item, dict) and item.get("l2"):
                normalized.append(
                    {
                        "l2": str(item["l2"]).strip(),
                        "l1": str(item.get("l1") or "").strip(),
                    }
                )
            elif isinstance(item, str) and item.strip():
                normalized.append({"l2": item.strip(), "l1": ""})
        meaning["usages"] = normalized


def _bare_lemma(lemma: str, learning_lang: str = "es") -> str:
    words = lemma.strip().lower().split()
    articles = articles_for(learning_lang)
    if len(words) == 2 and words[0].rstrip("'") in articles:
        return words[1]
    return " ".join(words)


def _usage_is_fixed_prep_construction(
    lemma: str, usage_l2: str, learning_lang: str = "es"
) -> bool:
    """True gdy usage to stałe „lemat (+odmiana) + przyimek …”, np. contar con."""
    bare = _bare_lemma(lemma, learning_lang)
    preps = lemma_preps_for(learning_lang)
    if not bare or not usage_l2 or not preps:
        return False
    text = usage_l2.strip().lower()
    for prep in preps:
        if re.match(rf"^{re.escape(bare)}\s+{re.escape(prep)}(?:\s|$)", text):
            return True
    first, *rest = text.split()
    if not first:
        return False
    if learning_lang == "es" and (
        first.endswith("migo") or first.endswith("tigo") or first.endswith("sigo")
    ):
        stem = bare.rstrip("ar") if bare.endswith("ar") else bare[:4]
        if stem and stem in first:
            return True
    if rest:
        prep = rest[0]
        if prep in preps:
            stem = bare[: max(3, len(bare) - 2)]
            if stem and stem in first:
                return True
    return False


def _meaning_is_prep_construction(
    lemma: str, meaning: dict, learning_lang: str = "es"
) -> bool:
    """Sens peryfrazy: większość usages to stałe lemat+przyimek."""
    usages = meaning.get("usages") or []
    if not isinstance(usages, list) or not usages:
        return False
    l2_list = [
        str(u.get("l2") or "").strip()
        for u in usages
        if isinstance(u, dict) and u.get("l2")
    ]
    if len(l2_list) < 2:
        return False
    hits = sum(
        1
        for l2 in l2_list
        if _usage_is_fixed_prep_construction(lemma, l2, learning_lang)
    )
    return hits >= 2 and hits >= (len(l2_list) + 1) // 2


def strip_prepositional_construction_meanings(
    lemma: str, meanings: list[dict], learning_lang: str = "es"
) -> list[dict]:
    """Usuwa znaczenia, które w praktyce opisują peryfrazę (np. contar con)."""
    kept = [
        m
        for m in meanings
        if not _meaning_is_prep_construction(lemma, m, learning_lang)
    ]
    return kept if kept else meanings[:1]


async def enrich_card_content(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    gloss_hint: str | None = None,
) -> dict:
    """Buduje pełną kartę w formacie vocabulario.card.v1 (LSP)."""
    from app.lsp.enrichment import enrich_card_content_lsp
    from app.lsp.registry import require_manifest

    require_manifest(profile.learning_lang)
    return await enrich_card_content_lsp(profile, lemma, pos, gloss_hint=gloss_hint)


# Legacy pipeline removed — all 16 L2 langs have LSP manifests.
ADAPTIVE_KINDS = frozenset({"phrase", "construction", "sentence", "other"})


async def enrich_adaptive_card_content(
    profile: LanguageProfile,
    *,
    headword: str,
    entry_kind: str,
    gloss: str | None = None,
    pos: str | None = None,
    base_lemma: str | None = None,
    pattern: str | None = None,
) -> dict:
    """Bogata karta dla zwrotu/konstrukcji/zdania — bez full conjugation / similar_words."""
    llm = LLMService()
    kind = (entry_kind or "other").strip().lower()
    if kind == "lemma":
        return await enrich_card_content(profile, headword, pos)

    if llm.mock:
        g = (gloss or "").strip() or "?"
        data = {
            "lemma": headword,
            "pos": pos or kind,
            "pattern": pattern,
            "related_lemma": base_lemma,
            "ipa": None,
            "meanings": [
                {
                    "gloss_l1": g,
                    "synonyms_l1": [],
                    "usages": ["Użycie z kontekstu importu (mock)."],
                    "examples": [
                        {
                            "l2": f"Ejemplo con {headword}.",
                            "l1": f"Przykład z „{headword}”.",
                            "cefr": "A2",
                        },
                        {
                            "l2": f"Usamos {headword} en este contexto.",
                            "l1": f"Używamy „{headword}” w tym kontekście.",
                            "cefr": "B2",
                        },
                        {
                            "l2": f"Resulta evidente que {headword} cambia el sentido.",
                            "l1": f"Widać, że „{headword}” zmienia sens.",
                            "cefr": "C2",
                        },
                    ],
                }
            ],
            "notes": "mock adaptive",
        }
    else:
        data = await llm.enrich_adaptive_entry(
            native=profile.app_lang,
            learning=profile.learning_lang,
            cefr=profile.cefr_level,
            entry_kind=kind,
            headword=headword,
            gloss=gloss,
            base_lemma=base_lemma,
            pattern=pattern,
        )

    meanings = [m for m in (data.get("meanings") or []) if isinstance(m, dict)]
    _normalize_usages(meanings)
    for m in meanings:
        if not isinstance(m.get("examples"), list):
            m["examples"] = []
        if not isinstance(m.get("synonyms_l1"), list):
            m["synonyms_l1"] = []
        if not isinstance(m.get("usages"), list):
            m["usages"] = []

    return {
        "schema_version": "vocabulario.adaptive.v1",
        "entry_kind": kind,
        "lemma": data.get("lemma") or headword,
        "language": profile.learning_lang,
        "pos": _resolve_pos(data.get("pos")) or _resolve_pos(pos) or kind,
        "ipa": data.get("ipa"),
        "pattern": data.get("pattern") or pattern,
        "related_lemma": data.get("related_lemma") or base_lemma,
        "meanings": meanings[:MAX_MEANINGS],
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
        "similar_words": [],
        "conjugation": None,
        "notes": data.get("notes"),
        "source_import": {
            "gloss_hint": gloss,
            "base_lemma": base_lemma,
            "pattern": pattern,
        },
    }

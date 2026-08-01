"""Orkiestracja enrichmentu — równoległe, mniejsze wywołania LLM."""

from __future__ import annotations

import asyncio
import re

from app.models import LanguageProfile
from app.services.llm import LLMService
from app.ai.schemas.similar_words import MIN_SIMILAR_WORDS
from app.services.similar_words import fetch_similar_words

# Jedno zdanie na pasmo poziomów: A2 widzi A1–A2, B2 widzi B1–B2, C2 widzi C1–C2.
EXAMPLE_CEFR_LEVELS = ["A2", "B2", "C2"]

# Jedno znaczenie główne i do dwóch pobocznych — sensy bliskoznaczne grupuje prompt.
MAX_MEANINGS = 3

# Stałe przyimki po lemacie → sens należy do peryfrazy, nie do gołego lematu.
_LEMMA_PREPS = ("con", "a", "de", "en", "por", "para", "sobre", "sin", "hacia")


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


def _merge_examples_into_meanings(core: dict, examples_payload: dict) -> None:
    core_meanings = core.get("meanings") or []
    ex_meanings = examples_payload.get("meanings") or []
    if not isinstance(core_meanings, list):
        return

    for idx, meaning in enumerate(core_meanings):
        if not isinstance(meaning, dict):
            continue
        source = None
        gloss = meaning.get("gloss_l1")
        if gloss and isinstance(ex_meanings, list):
            source = next(
                (
                    m
                    for m in ex_meanings
                    if isinstance(m, dict) and m.get("gloss_l1") == gloss
                ),
                None,
            )
        if source is None and isinstance(ex_meanings, list) and idx < len(ex_meanings):
            source = ex_meanings[idx] if isinstance(ex_meanings[idx], dict) else None
        if source and isinstance(source.get("examples"), list):
            meaning["examples"] = source["examples"]


def _resolve_pos(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None if cleaned.lower() != "unknown" else None


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


def _bare_lemma(lemma: str) -> str:
    words = lemma.strip().lower().split()
    if len(words) == 2 and words[0] in {"el", "la", "los", "las"}:
        return words[1]
    return " ".join(words)


def _usage_is_fixed_prep_construction(lemma: str, usage_l2: str) -> bool:
    """True gdy usage to stałe „lemat (+odmiana) + przyimek …”, np. contar con."""
    bare = _bare_lemma(lemma)
    if not bare or not usage_l2:
        return False
    text = usage_l2.strip().lower()
    # Bezokolicznik: "contar con ayuda"
    for prep in _LEMMA_PREPS:
        if re.match(rf"^{re.escape(bare)}\s+{prep}(?:\s|$)", text):
            return True
    # Odmiana hiszpańska kończąca się na rdzeniu + " con/a/…" — tylko gdy
    # usage zaczyna się od formy zawierającej rdzeń lematu i zaraz jest przyimek.
    # Np. "cuento contigo" / "contábamos con llegar" — wykrywamy przyimek
    # bezpośrednio po pierwszym tokenie albo scalone "contigo".
    first, *rest = text.split()
    if not first:
        return False
    # contigo / consigo traktuj jak "con"
    if first.endswith("migo") or first.endswith("tigo") or first.endswith("sigo"):
        # "cuento contigo" — drugi token to fused prep; first is conjugated verb
        stem = bare.rstrip("ar") if bare.endswith("ar") else bare[:4]
        if stem and stem in first:
            return True
    if rest:
        prep = rest[0]
        if prep in _LEMMA_PREPS:
            stem = bare[: max(3, len(bare) - 2)]
            if stem and stem in first:
                return True
    return False


def _meaning_is_prep_construction(lemma: str, meaning: dict) -> bool:
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
    hits = sum(1 for l2 in l2_list if _usage_is_fixed_prep_construction(lemma, l2))
    return hits >= 2 and hits >= (len(l2_list) + 1) // 2


def strip_prepositional_construction_meanings(lemma: str, meanings: list[dict]) -> list[dict]:
    """Usuwa znaczenia, które w praktyce opisują peryfrazę (np. contar con)."""
    kept = [m for m in meanings if not _meaning_is_prep_construction(lemma, m)]
    return kept if kept else meanings[:1]


async def enrich_card_content(
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
) -> dict:
    """Buduje pełną kartę: core → równolegle examples + similar_words + conjugation."""
    llm = LLMService()
    pos_val = pos or "unknown"

    core = await llm.enrich_core(
        lemma=lemma,
        pos=pos_val,
        native=profile.native_lang,
        learning=profile.learning_lang,
        cefr=profile.cefr_level,
    )
    lemma_final = core.get("lemma") or lemma
    # POS z core ma pierwszeństwo — gdy wywołanie nie podało części mowy,
    # dopiero tutaj jest znana i musi trafić do dystraktorów oraz koniugacji.
    pos_final = _resolve_pos(core.get("pos")) or _resolve_pos(pos) or "unknown"

    # Przycięcie przed krokiem z przykładami, żeby indeksy znaczeń się zgadzały
    # i żeby nie płacić za zdania do sensów, które i tak nie wejdą na kartę.
    meanings = [m for m in (core.get("meanings") or []) if isinstance(m, dict)]
    _normalize_usages(meanings)
    meanings = strip_prepositional_construction_meanings(lemma_final, meanings)
    core["meanings"] = meanings[:MAX_MEANINGS]
    pos_for_related = pos_final if pos_final != "unknown" else None
    core["synonyms_l2"] = _normalize_related_words(
        core.get("synonyms_l2"), fallback_pos=pos_for_related
    )
    core["antonyms_l2"] = _normalize_related_words(
        core.get("antonyms_l2"), fallback_pos=pos_for_related
    )
    glosses = [m["gloss_l1"] for m in core["meanings"] if m.get("gloss_l1")]

    async def fetch_examples() -> dict:
        if not glosses:
            return {"meanings": []}
        data = await llm.generate_examples(
            lemma=lemma_final,
            pos=pos_final,
            glosses=glosses,
            native=profile.native_lang,
            learning=profile.learning_lang,
        )
        first = (data.get("meanings") or [{}])[0] if data.get("meanings") else {}
        first_examples = first.get("examples") if isinstance(first, dict) else []
        if isinstance(first_examples, list) and not examples_complete(first_examples):
            data = await llm.generate_examples(
                lemma=lemma_final,
                pos=pos_final,
                glosses=glosses,
                native=profile.native_lang,
                learning=profile.learning_lang,
                retry=True,
            )
        return data

    async def fetch_similar() -> list[dict]:
        return await fetch_similar_words(llm, profile, lemma_final, pos_final)

    async def fetch_conjugation() -> dict | None:
        if pos_final != "verb":
            return None
        return await llm.generate_conjugation(lemma=lemma_final)

    examples_data, similar, conjugation = await asyncio.gather(
        fetch_examples(),
        fetch_similar(),
        fetch_conjugation(),
    )

    _merge_examples_into_meanings(core, examples_data)

    if len(similar) < MIN_SIMILAR_WORDS:
        raise ValueError(
            f"AI zwróciło za mało dystraktorów dla „{lemma_final}” "
            f"({len(similar)}/{MIN_SIMILAR_WORDS})."
        )
    core["similar_words"] = similar
    core["conjugation"] = conjugation
    return core

"""Schemat odmiany czasownika — językowa-agnostyczny (LLM dobiera paradigmę L2)."""

from __future__ import annotations

from app.ai.language_typology import lang_name_en, language_pair_guidance, morphology_hint
from app.lsp.registry import get_manifest, has_manifest

# Zachowane dla kompatybilności ze starymi kartami ES + filtrami UI.
ALL_CONJUGATION_TENSES: list[str] = [
    "presente",
    "preterito_perfecto",
    "preterito_indefinido",
    "preterito_imperfecto",
    "futuro_simple",
    "condicional_simple",
    "presente_subjuntivo",
    "imperfecto_subjuntivo",
    "futuro_subjuntivo",
    "preterito_pluscuamperfecto",
    "condicional_compuesto",
    "futuro_perfecto",
    "imperativo_afirmativo",
    "imperativo_negativo",
]

NON_FINITE_FORMS: list[str] = ["gerundio", "participio"]

DEFAULT_DISPLAY_TENSES: list[str] = ["presente", *NON_FINITE_FORMS]

# Legacy Spanish person keys — UI falls back when card has no person_order.
PERSON_KEYS = ["yo", "tú", "él", "nosotros", "vosotros", "ellos"]


CONJUGATION_PROMPT_BLOCK = """
CONJUGATION / INFLECTION for lemma "{lemma}" in L2={learning_name} [{learning}].

{pair_guidance}

Decide whether a learner-facing paradigm is useful for this POS and language.
- If NOT useful (many analytic languages, particles-only aspect, etc.):
  conjugation = null and ui_hints.show_conjugation = false.
- If useful: fill conjugation with a COMPLETE, VERIFIED paradigm for THIS L2
  (not a copy of Spanish yo/tú tables unless L2 is Spanish).
- For non-verbs: conjugation = null.

ACCURACY (mandatory — read before filling any tense):
1. Mentally conjugate "{lemma}" in each tense you include. Every value MUST be a
   real, attested inflected form for THIS lemma in standard {learning_name}.
2. NEVER use placeholders: no "—", "-", "n/a", empty strings, or invented forms.
3. If a tense does not exist for this lemma (e.g. Polish perfective present),
   OMIT that tense key entirely from "tenses". Do NOT emit a tense object full of
   placeholders.
4. person_order and person keys MUST match the grammatical paradigm of that tense
   in L2 — do not reuse person grids from a different tense or language.
5. Before returning JSON, re-check each tense: if any form would be a placeholder,
   remove the whole tense instead of returning it.

{paradigm_rules}

Required shape when conjugation is not null:
{{
  "ui_meta": {{
    "conjugation_kind": "person_tense|agglutinative|aspect_particles|minimal",
    "person_order": ["ordered keys used in tenses objects"],
    "person_labels": {{"key": "short label"}},
    "tense_labels": {{"tense_key": "short label"}},
    "non_finite_labels": {{"key": "short label"}}
  }},
  "non_finite": {{ "key": "form in L2", "...": "..." }},
  "tenses": {{
    "tense_key": {{ "person_key": "form in L2", "...": "..." }}
  }},
  "periphrases": [
    {{
      "id": "snake_case_id",
      "formula_l2": "pattern in L2",
      "gloss_l1": "meaning in L1",
      "examples": [{{"l2": "...", "l1": "..."}}]
    }}
  ]
}}

CRITICAL — tense / non_finite object keys MUST be EXACTLY from this list
(do not invent English synonyms like present/past):
- finite tense keys: {tense_keys}
- non_finite keys: {non_finite_keys}

Rules:
- Prefer the keys above + human labels in *_labels (labels may be localized).
- person_order MUST list every person key you use, in display order.
- Include learner-relevant tenses from the key list only when you can fill them
  with real forms. Omit inapplicable tenses — never pad with placeholders.
- periphrases: ONLY idioms where meaning comes from THIS lemma (not generic auxiliaries).
  If none → [].
- Gloss fields in L1 ({native_name}). Forms in L2 script.

L2 morphology reminder: {morphology}
""".strip()


_POLISH_PARADIGM_RULES = """
POLISH (pl) — MANDATORY when L2=pl:
1. Determine aspect of "{lemma}" (perfective vs imperfective). Pairs: pisać/napisać,
   jechać/pojechać, robić/zrobić. Prefixes po-, na-, prze-, wy-, za- often mark perfective.
2. czas_terazniejszy — ONLY for IMPERFECTIVE verbs.
   - person_order: ["ja", "ty", "on", "ona", "ono", "my", "wy", "oni", "one"]
   - Present tense has NO masculine/feminine verb distinction.
     NEVER use ja_m, ja_f, ja_ż, ty_m, ty_f, nested ja→{{m,ż}}, or past-tense grids here.
   - "on", "ona", "ono" share the same 3sg form; "oni" and "one" share the same 3pl form.
   - Example (robić): ja=robię, ty=robisz, on/ona/ono=robi, my=robimy, wy=robicie, oni/one=robią.
   - For PERFECTIVE verbs: do NOT include czas_terazniejszy at all.
3. czas_przeszly — both aspects; gender required where Polish distinguishes it.
   - person_order: ["ja_m", "ja_f", "ty_m", "ty_f", "on", "ona", "ono", "my_mv", "my_fv",
     "wy_mv", "wy_fv", "oni", "one"]
   - Fill every key with the correct l-participle form (e.g. robiłem/robiłam, …).
4. czas_przyszly:
   - Imperfective: compound future (będę + l-participle with gender where applicable).
   - Perfective: simple future (pójdę, pójdziesz, …) — no gender in 1sg/2sg.
5. tryb_rozkazujacy: typically ty, my, wy (2sg, 1pl, 2pl imperative forms).
6. tryb_przypuszczajacy: gendered like past (robiłbym/robiłabym, …).
7. non_finite: bezokolicznik = infinitive of lemma; imiesłów = active participle if common.
""".strip()

_CZECH_PARADIGM_RULES = """
CZECH (cs) — MANDATORY when L2=cs:
1. Determine aspect (dokonavý vs nedokonavý). Perfective verbs have no true present —
   OMIT pritomny for perfective; do not use placeholders.
2. pritomny: 6 persons (já, ty, on/ona/ono, my, vy, oni/ony) — no speaker-gender split.
3. minuly / budouci / rozkazovaci: follow standard Czech paradigms for this lemma.
4. Every form must be a real inflected word; omit a tense rather than padding with dashes.
""".strip()

_RUSSIAN_PARADIGM_RULES = """
RUSSIAN (ru) — MANDATORY when L2=ru:
1. Determine aspect (совершенный / несовершенный). Perfective verbs have no present tense —
   OMIT nastoyashchee for perfective; do not use placeholders.
2. nastoyashchee: 6 persons, no gender split in present.
3. proshedshee / budushchee / povelitelnoe: standard Russian paradigms for this lemma.
4. Every form must be real Cyrillic inflection; omit a tense rather than placeholders.
""".strip()

_PARADIGM_RULES_BY_LANG: dict[str, str] = {
    "pl": _POLISH_PARADIGM_RULES,
    "cs": _CZECH_PARADIGM_RULES,
    "ru": _RUSSIAN_PARADIGM_RULES,
    "uk": _RUSSIAN_PARADIGM_RULES.replace("Russian", "Ukrainian").replace("(ru)", "(uk)"),
}


def conjugation_paradigm_rules(learning: str, lemma: str) -> str:
    """Language-specific conjugation paradigm — injected into LLM prompts."""
    template = _PARADIGM_RULES_BY_LANG.get((learning or "").strip().lower())
    if not template:
        return (
            "Use the standard learner paradigm for this language and lemma. "
            "Omit tenses that do not exist; never pad with placeholder dashes."
        )
    return template.format(lemma=lemma)


def _allowed_inflection_keys(learning: str) -> tuple[set[str], set[str]]:
    key = (learning or "").strip().lower()
    if has_manifest(key):
        manifest = get_manifest(key)
        return set(manifest.tense_keys()), set(manifest.non_finite_keys())
    return set(), set()


def conjugation_rules_for_prompt(
    lemma: str,
    *,
    native: str = "pl",
    learning: str = "es",
) -> str:
    allowed_tenses, allowed_nf = _allowed_inflection_keys(learning)
    tense_keys = ", ".join(sorted(allowed_tenses)) or "(language-default)"
    non_finite_keys = ", ".join(sorted(allowed_nf)) or "(none)"
    return CONJUGATION_PROMPT_BLOCK.format(
        lemma=lemma,
        learning=learning,
        learning_name=lang_name_en(learning),
        native_name=lang_name_en(native),
        pair_guidance=language_pair_guidance(native=native, learning=learning),
        paradigm_rules=conjugation_paradigm_rules(learning, lemma),
        morphology=morphology_hint(learning),
        tense_keys=tense_keys,
        non_finite_keys=non_finite_keys,
    )


# Free-form LLM keys → pack keys (per L2). Also strip diacritics loosely via aliases.
_TENSE_ALIASES_BY_LANG: dict[str, dict[str, str]] = {
    "pl": {
        "present": "czas_terazniejszy",
        "present_tense": "czas_terazniejszy",
        "czas_terazniejszy": "czas_terazniejszy",
        "czas_teraźniejszy": "czas_terazniejszy",
        "terazniejszy": "czas_terazniejszy",
        "past": "czas_przeszly",
        "past_tense": "czas_przeszly",
        "czas_przeszly": "czas_przeszly",
        "czas_przeszły": "czas_przeszly",
        "przeszly": "czas_przeszly",
        "future": "czas_przyszly",
        "future_tense": "czas_przyszly",
        "czas_przyszly": "czas_przyszly",
        "czas_przyszły": "czas_przyszly",
        "imperative": "tryb_rozkazujacy",
        "tryb_rozkazujacy": "tryb_rozkazujacy",
        "tryb_rozkazujący": "tryb_rozkazujacy",
        "conditional": "tryb_przypuszczajacy",
        "tryb_przypuszczajacy": "tryb_przypuszczajacy",
        "tryb_przypuszczający": "tryb_przypuszczajacy",
        "infinitive": "bezokolicznik",
        "bezokolicznik": "bezokolicznik",
        "participle": "imieslow_przeszly",
        "imieslow": "imieslow_przeszly",
        "imiesłów": "imieslow_przeszly",
        "imieslow_przeszly": "imieslow_przeszly",
        "imieslow_przyszly": "imieslow_przyszly",
    },
    "es": {
        "present": "presente",
        "past": "preterito_indefinido",
        "imperfect": "preterito_imperfecto",
        "future": "futuro_simple",
        "conditional": "condicional_simple",
        "imperative": "imperativo_afirmativo",
    },
    "en": {
        "present_simple": "present",
        "past_simple": "past",
        "present_continuous": "present_continuous",
        "present_perfect": "present_perfect",
    },
    "fr": {
        "present": "present",
        "passé_composé": "passe_compose",
        "passe_compose": "passe_compose",
        "imparfait": "imparfait",
        "futur": "futur_simple",
        "conditionnel": "conditionnel_present",
    },
    "de": {
        "present": "praesens",
        "präsens": "praesens",
        "praesens": "praesens",
        "past": "preteritum",
        "präteritum": "preteritum",
        "perfect": "perfekt",
        "future": "futur_i",
    },
}


_PLACEHOLDER_FORMS = frozenset({"", "—", "-", "–", "n/a", "na"})


def _score_forms(forms: object) -> int:
    if not isinstance(forms, dict):
        if isinstance(forms, str) and forms.strip() and forms.strip().lower() not in _PLACEHOLDER_FORMS:
            return 1
        return 0
    score = 0
    for value in forms.values():
        if isinstance(value, dict):
            score += _score_forms(value)
        elif isinstance(value, str) and value.strip() and value.strip().lower() not in _PLACEHOLDER_FORMS:
            score += 1
    return score


def _is_placeholder_form(value: object) -> bool:
    if not isinstance(value, str):
        return True
    return value.strip().lower() in _PLACEHOLDER_FORMS


def _tense_is_all_placeholders(forms: object) -> bool:
    if not isinstance(forms, dict) or not forms:
        return True
    for value in forms.values():
        if isinstance(value, dict):
            if not _tense_is_all_placeholders(value):
                return False
        elif not _is_placeholder_form(value):
            return False
    return True


_PL_PRESENT_GENDER_KEYS = frozenset(
    {
        "ja_m",
        "ja_f",
        "ja_ż",
        "ja_z",
        "ty_m",
        "ty_f",
        "ty_ż",
        "ty_z",
        "my_m",
        "my_f",
        "my_ż",
        "my_z",
        "wy_m",
        "wy_f",
        "wy_ż",
        "wy_z",
    }
)


def _pl_present_has_invalid_gender_grid(forms: dict) -> bool:
    """Polish present tense must not use past-style speaker-gender keys."""
    keys = {str(k).strip().lower().replace(".", "") for k in forms}
    if keys & _PL_PRESENT_GENDER_KEYS:
        return True
    for key, value in forms.items():
        if isinstance(value, dict) and str(key).strip().lower() in {"ja", "ty", "my", "wy"}:
            sub = {str(s).strip().lower() for s in value}
            if sub & {"m", "ż", "z", "f"}:
                return True
    return False


def validate_conjugation(conjugation: dict, learning: str) -> dict:
    """Drop structurally invalid tense blocks (placeholder grids, wrong paradigms)."""
    lang = (learning or "").strip().lower()
    tenses_in = conjugation.get("tenses")
    if not isinstance(tenses_in, dict):
        return conjugation

    cleaned: dict = {}
    for tense_key, forms in tenses_in.items():
        if not isinstance(forms, dict):
            continue
        flat = _flatten_person_forms(forms)
        if _tense_is_all_placeholders(flat):
            continue
        if lang == "pl" and tense_key == "czas_terazniejszy" and _pl_present_has_invalid_gender_grid(flat):
            continue
        cleaned[tense_key] = flat

    conjugation["tenses"] = cleaned

    nf_in = conjugation.get("non_finite")
    if isinstance(nf_in, dict):
        conjugation["non_finite"] = {
            k: v
            for k, v in nf_in.items()
            if not _is_placeholder_form(v)
        }

    if not conjugation["tenses"] and not conjugation.get("non_finite"):
        return {}

    return conjugation


def _flatten_person_forms(forms: dict) -> dict:
    """LLM sometimes nests PL persons: ja -> {m, ż} while ui_meta uses ja_m."""
    out = dict(forms)
    for key, value in list(forms.items()):
        if not isinstance(value, dict):
            continue
        for sub_key, sub_val in value.items():
            if not isinstance(sub_val, str):
                continue
            flat = f"{key}_{sub_key}".replace(".", "")
            if flat not in out:
                out[flat] = sub_val
    return out


def _merge_tense_forms(existing: object, incoming: object) -> object:
    if not isinstance(existing, dict):
        return incoming
    if not isinstance(incoming, dict):
        return existing
    flat_existing = _flatten_person_forms(existing)
    flat_incoming = _flatten_person_forms(incoming)
    if _score_forms(flat_incoming) > _score_forms(flat_existing):
        return flat_incoming
    return flat_existing


def canonicalize_conjugation_keys(conjugation: dict, learning: str) -> dict:
    """Remap free-form LLM tense keys onto LanguagePack keys when possible."""
    allowed_tenses, allowed_nf = _allowed_inflection_keys(learning)
    aliases = dict(_TENSE_ALIASES_BY_LANG.get(learning, {}))
    for key in list(allowed_tenses) + list(allowed_nf):
        aliases.setdefault(key, key)

    def map_key(raw: str, allowed: set[str]) -> str:
        k = (raw or "").strip()
        if k in allowed:
            return k
        mapped = aliases.get(k) or aliases.get(k.casefold())
        if mapped and mapped in allowed:
            return mapped
        return k

    tenses_in = conjugation.get("tenses")
    if isinstance(tenses_in, dict):
        out: dict = {}
        for raw_key, forms in tenses_in.items():
            key = map_key(str(raw_key), allowed_tenses)
            if key not in out:
                out[key] = _flatten_person_forms(forms) if isinstance(forms, dict) else forms
            else:
                out[key] = _merge_tense_forms(out[key], forms)
        conjugation["tenses"] = out

    nf_in = conjugation.get("non_finite")
    if isinstance(nf_in, dict):
        out_nf: dict = {}
        for raw_key, form in nf_in.items():
            key = map_key(str(raw_key), allowed_nf) if allowed_nf else str(raw_key)
            if key not in out_nf:
                out_nf[key] = form
        conjugation["non_finite"] = out_nf

    ui_meta = conjugation.get("ui_meta")
    if isinstance(ui_meta, dict):
        for label_field in ("tense_labels", "non_finite_labels"):
            labels = ui_meta.get(label_field)
            if not isinstance(labels, dict):
                continue
            allowed = allowed_tenses if label_field == "tense_labels" else allowed_nf
            remapped: dict = {}
            for raw_key, label in labels.items():
                key = map_key(str(raw_key), allowed) if allowed else str(raw_key)
                remapped.setdefault(key, label)
            ui_meta[label_field] = remapped

    return conjugation

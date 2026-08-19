"""Prompty LSP — budowane z manifestu."""

from __future__ import annotations

from app.ai.language_typology import lang_name_en, language_pair_guidance, morphology_hint
from app.lsp.models import LanguageManifest


def build_inflection_prompt_parts(
    manifest: LanguageManifest,
    *,
    lemma: str,
    pos: str,
    app_lang: str,
) -> tuple[str, str]:
    """Static manifest prefix (cacheable) + dynamic lemma block."""
    verbs = manifest.verbs
    if not verbs:
        body = (
            f"Lemma '{lemma}' ({manifest.code}): no verbal inflection catalog. "
            'Return {"verbs": null, "nouns": null, "adjectives": null, "periphrases": []}.'
        )
        return body, ""

    tense_keys = ", ".join(manifest.tense_keys()) or "(none)"
    nf_keys = ", ".join(manifest.non_finite_keys()) or "(none)"
    grids_desc = []
    for name, grid in verbs.person_grids.items():
        grids_desc.append(f"  - {name}: {', '.join(grid.keys)}")

    static = f"""
Generate COMPLETE inflection for an L2 lemma. JSON shape:
{{
  "verbs": {{
    "ui_meta": {{
      "inflection_kind": "{manifest.inflection_kind}",
      "person_order": ["..."],
      "person_labels": {{}},
      "tense_labels": {{}},
      "non_finite_labels": {{}}
    }},
    "tenses": {{ "tense_key": {{ "person_key": "form" }} }},
    "non_finite": {{ "key": "form" }}
  }},
  "nouns": null,
  "adjectives": null,
  "periphrases": []
}}

L2 language: {manifest.name_en} [{manifest.code}]

{language_pair_guidance(native=app_lang, learning=manifest.code)}

ACCURACY:
1. Every form must be real and attested — no placeholders (—, -, n/a).
2. Omit entire tense if grammatically impossible for this lemma.
3. Use ONLY these finite tense keys: {tense_keys}
4. Use ONLY these non_finite keys: {nf_keys}
5. person_order must list keys used, in display order.
6. Glosses in periphrases in L1 ({lang_name_en(app_lang)}). Forms in L2.

Person grids (reference):
{chr(10).join(grids_desc) if grids_desc else "  (language-specific)"}

Morphology: {morphology_hint(manifest.code)}
""".strip()

    paradigm = verbs.paradigm_rules.format(lemma=lemma) if verbs.paradigm_rules else ""
    dynamic = f"""
INFLECTION for lemma "{lemma}" (POS={pos}) in L2={manifest.name_en} [{manifest.code}].

{paradigm}
""".strip()
    return static, dynamic


def build_inflection_prompt(
    manifest: LanguageManifest,
    *,
    lemma: str,
    pos: str,
    app_lang: str,
) -> str:
    static, dynamic = build_inflection_prompt_parts(
        manifest, lemma=lemma, pos=pos, app_lang=app_lang
    )
    if not dynamic:
        return static
    return static + "\n\n" + dynamic

"""Walidacja bloków inflection wg manifestu LSP."""

from __future__ import annotations

from app.ai.conjugation import canonicalize_conjugation_keys, validate_conjugation
from app.lsp.models import LanguageManifest


def validate_verbs_block(raw: dict | None, manifest: LanguageManifest) -> dict | None:
    if not raw or not isinstance(raw, dict):
        return None
    code = manifest.code
    cleaned = validate_conjugation(dict(raw), code)
    if not cleaned:
        return None
    cleaned = canonicalize_conjugation_keys(cleaned, code)
    if not cleaned.get("tenses") and not cleaned.get("non_finite"):
        return None
    return cleaned


def validate_inflection(
    raw: dict | None,
    manifest: LanguageManifest,
    *,
    pos: str,
) -> dict:
    """Zwraca znormalizowany blok inflection do zapisu na karcie."""
    result: dict = {
        "verbs": None,
        "nouns": None,
        "adjectives": None,
        "periphrases": [],
    }
    if not raw or not isinstance(raw, dict):
        return result

    per = raw.get("periphrases")
    if isinstance(per, list):
        result["periphrases"] = [p for p in per if isinstance(p, dict)]

    if pos == "verb" and manifest.verbs:
        verbs = validate_verbs_block(raw.get("verbs") if isinstance(raw.get("verbs"), dict) else raw, manifest)
        if verbs:
            result["verbs"] = verbs

    # TODO: nouns / adjectives validators per manifest (następny krok)
    if pos == "noun" and isinstance(raw.get("nouns"), dict):
        result["nouns"] = raw["nouns"]
    if pos in {"adjective", "adj"} and isinstance(raw.get("adjectives"), dict):
        result["adjectives"] = raw["adjectives"]

    return result


def apply_manifest_ui_labels(
    inflection: dict,
    manifest: LanguageManifest,
    *,
    app_lang: str,
) -> None:
    """Uzupełnia ui_meta etykietami czasów z manifestu (app_lang + L2)."""
    verbs = inflection.get("verbs")
    if not isinstance(verbs, dict):
        return
    ui_meta = verbs.get("ui_meta")
    if not isinstance(ui_meta, dict):
        ui_meta = {}
        verbs["ui_meta"] = ui_meta

    tense_app: dict[str, str] = {}
    tense_l2: dict[str, str] = {}
    nf_app: dict[str, str] = {}
    nf_l2: dict[str, str] = {}
    for key in manifest.tense_keys():
        tense_app[key] = manifest.label_for_tense(key, app_lang=app_lang)
        tense_l2[key] = manifest.label_for_tense(key, app_lang=manifest.code)
    for key in manifest.non_finite_keys():
        nf_app[key] = manifest.label_for_tense(key, app_lang=app_lang)
        nf_l2[key] = manifest.label_for_tense(key, app_lang=manifest.code)

    ui_meta["tense_labels_app"] = tense_app
    ui_meta["tense_labels_l2"] = tense_l2
    ui_meta["non_finite_labels_app"] = nf_app
    ui_meta["non_finite_labels_l2"] = nf_l2
    ui_meta.setdefault("tense_labels", tense_l2)
    ui_meta.setdefault("non_finite_labels", nf_l2)


def inflection_to_legacy_conjugation(inflection: dict | None) -> dict | None:
    """Mapuje inflection.verbs → stary kształt conjugation (Android do czasu migracji UI)."""
    if not inflection or not isinstance(inflection, dict):
        return None
    verbs = inflection.get("verbs")
    if not isinstance(verbs, dict):
        return None
    out = {
        "tenses": verbs.get("tenses") or {},
        "non_finite": verbs.get("non_finite") or {},
        "ui_meta": verbs.get("ui_meta") or {},
        "periphrases": inflection.get("periphrases") or [],
    }
    if not out["tenses"] and not out["non_finite"] and not out["periphrases"]:
        return None
    return out

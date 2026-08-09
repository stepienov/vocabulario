"""Testy LSP — manifest polski i walidacja."""

from app.lsp.loader import load_manifest
from app.lsp.prompts import build_inflection_prompt
from app.lsp.registry import available_codes, get_manifest, has_manifest
from app.lsp.validate import apply_manifest_ui_labels, inflection_to_legacy_conjugation, validate_inflection


def test_pl_manifest_loads():
    m = load_manifest("pl")
    assert m.code == "pl"
    assert m.lsp_version == "pl-1.0.0"
    assert "czas_terazniejszy" in m.tense_keys()
    assert m.default_selected_tenses == ["czas_terazniejszy", "czas_przeszly"]


def test_registry_has_pl():
    assert has_manifest("pl")
    assert "pl" in available_codes()
    assert get_manifest("pl").name_en == "Polish"


def test_inflection_prompt_contains_paradigm_rules():
    m = get_manifest("pl")
    p = build_inflection_prompt(m, lemma="robić", pos="verb", app_lang="pl")
    assert "robić" in p
    assert "czas_terazniejszy" in p
    assert "PERFECTIVE" in p.upper() or "perfective" in p.lower()


def test_validate_drops_placeholder_present():
    m = get_manifest("pl")
    raw = {
        "verbs": {
            "tenses": {
                "czas_terazniejszy": {"ja_m": "—", "ja_f": "—"},
                "czas_przeszly": {"ja_m": "robiłem", "ja_f": "robiłam"},
            },
            "non_finite": {"bezokolicznik": "robić"},
        }
    }
    out = validate_inflection(raw, m, pos="verb")
    assert "czas_terazniejszy" not in (out["verbs"] or {}).get("tenses", {})
    assert out["verbs"]["tenses"]["czas_przeszly"]["ja_m"] == "robiłem"


def test_manifest_ui_labels_applied():
    m = get_manifest("pl")
    inf = {
        "verbs": {
            "tenses": {"czas_przeszly": {"ja_m": "robiłem"}},
            "non_finite": {"bezokolicznik": "robić"},
            "ui_meta": {},
        },
        "periphrases": [],
    }
    apply_manifest_ui_labels(inf, m, app_lang="pl")
    labels = inf["verbs"]["ui_meta"]["tense_labels_app"]
    assert labels["czas_przeszly"] == "Czas przeszły"


def test_legacy_conjugation_mapping():
    inf = {
        "verbs": {
            "tenses": {"czas_przeszly": {"ja_m": "robiłem"}},
            "non_finite": {"bezokolicznik": "robić"},
            "ui_meta": {"inflection_kind": "person_tense"},
        },
        "periphrases": [],
    }
    conj = inflection_to_legacy_conjugation(inf)
    assert conj is not None
    assert conj["tenses"]["czas_przeszly"]["ja_m"] == "robiłem"

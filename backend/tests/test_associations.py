"""Skojarzenia: filtr dedupu i składanie karty."""

from types import SimpleNamespace

from app.lsp.enrichment import assemble_core_card
from app.services.enrichment import filter_associations


def _profile():
    return SimpleNamespace(app_lang="pl", learning_lang="es", cefr_level="A2")


def _core(**extra):
    payload = {
        "lemma": "conducir",
        "pos": "verb",
        "ipa": "a",
        "meanings": [
            {
                "gloss_l1": "prowadzić",
                "synonyms_l1": [],
                "usages": [],
                "examples": [
                    {"l2": "a", "l1": "a", "cefr": "A2"},
                    {"l2": "b", "l1": "b", "cefr": "B2"},
                    {"l2": "c", "l1": "c", "cefr": "C2"},
                ],
            }
        ],
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
        "associations_l2": [],
    }
    payload.update(extra)
    return payload


def test_filter_drops_headword_synonym_antonym_and_family():
    kept = filter_associations(
        "conducir",
        [
            {"lemma": "conducir", "pos": "verb", "gloss_l1": "x"},
            {"lemma": "manejar", "pos": "verb", "gloss_l1": "x"},
            {"lemma": "el volante", "pos": "noun", "article": "el", "gloss_l1": "kierownica"},
            {"lemma": "conductor", "pos": "noun", "article": "el", "gloss_l1": "kierowca"},
            {"lemma": "parar", "pos": "verb", "gloss_l1": "zatrzymywać się"},
        ],
        synonyms=[{"lemma": "manejar", "pos": "verb", "gloss_l1": "x"}],
        antonyms=[{"lemma": "parar", "pos": "verb", "gloss_l1": "x"}],
        family=[{"lemma": "conductor", "pos": "noun", "article": "el", "gloss_l1": "x"}],
    )
    assert [w["lemma"] for w in kept] == ["el volante"]


def test_filter_caps_at_twenty():
    items = [{"lemma": f"w{i}", "pos": "noun", "article": "el", "gloss_l1": "x"} for i in range(25)]
    assert len(filter_associations("head", items)) == 20


def test_assemble_keeps_associations_and_dedups():
    card = assemble_core_card(
        _profile(),
        "conducir",
        "verb",
        _core(
            synonyms_l2=[{"lemma": "manejar", "pos": "verb", "gloss_l1": "kierować", "article": None}],
            associations_l2=[
                {"lemma": "manejar", "pos": "verb", "gloss_l1": "kierować", "article": None},
                {"lemma": "volante", "pos": "noun", "article": "el", "gloss_l1": "kierownica"},
                {"lemma": "conducir", "pos": "verb", "gloss_l1": "x", "article": None},
            ],
        ),
    )
    lemmas = [w["lemma"] for w in card["associations_l2"]]
    assert lemmas == ["volante"]
    assert card["associations_l2"][0]["article"] == "el"


def test_assemble_missing_associations_is_empty_list():
    core = _core()
    del core["associations_l2"]
    card = assemble_core_card(_profile(), "conducir", "verb", core)
    assert card["associations_l2"] == []

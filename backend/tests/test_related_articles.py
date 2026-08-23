"""Related-word citation articles: copy/lift from the LLM, never invent."""

from types import SimpleNamespace

from app.lsp.enrichment import assemble_core_card
from app.services.enrichment import _normalize_related_words
from app.services.related_articles import (
    apply_article_repairs,
    article_is_required,
    attach_article,
    drop_related_missing_articles,
    lift_article_from_lemma,
    related_items_missing_article,
)


def test_spanish_copies_el():
    entry = attach_article(
        {"lemma": "alcance", "pos": "noun", "gloss_l1": "zasięg"},
        "el",
        "es",
    )
    assert entry["article"] == "el"
    assert entry["lemma"] == "alcance"


def test_italian_keeps_lo_not_il():
    entry = attach_article({"lemma": "studente", "pos": "noun"}, "lo", "it")
    assert entry["article"] == "lo"
    assert entry["lemma"] == "studente"


def test_french_elision_lifts_from_lemma():
    art, stem = lift_article_from_lemma("l'homme", "fr")
    assert art == "l'"
    assert stem == "homme"
    entry = attach_article({"lemma": "l'homme", "pos": "noun"}, None, "fr")
    assert entry["article"] == "l'"
    assert entry["lemma"] == "homme"


def test_arabic_al_lifts_without_space():
    art, stem = lift_article_from_lemma("الكتاب", "ar")
    assert art == "ال"
    assert stem == "كتاب"
    entry = attach_article({"lemma": "الكتاب", "pos": "noun"}, None, "ar")
    assert entry["article"] == "ال"
    assert entry["lemma"] == "كتاب"


def test_english_and_polish_nouns_do_not_require_article():
    assert article_is_required("noun", "en") is False
    assert article_is_required("noun", "pl") is False
    en = attach_article({"lemma": "book", "pos": "noun"}, None, "en")
    pl = attach_article({"lemma": "książka", "pos": "noun"}, None, "pl")
    assert en["article"] is None
    assert pl["article"] is None
    assert related_items_missing_article(
        {"word_family_l2": [{"lemma": "book", "pos": "noun"}]}, "en"
    ) == []


def test_verb_article_always_null():
    entry = attach_article({"lemma": "alcanzar", "pos": "verb"}, "el", "es")
    assert entry["article"] is None
    assert entry["lemma"] == "alcanzar"


def test_missing_article_is_dropped_not_invented():
    raw = [
        {"lemma": "alcance", "pos": "noun", "gloss_l1": "zasięg"},
        {"lemma": "alcanzar", "pos": "verb", "gloss_l1": "osiągać"},
    ]
    out = _normalize_related_words(raw, fallback_pos=None, learning_lang="es")
    lemmas = [e["lemma"] for e in out]
    assert "alcance" not in lemmas
    assert "alcanzar" in lemmas


def test_repair_fills_then_drop_still_empty():
    filled = apply_article_repairs(
        [{"lemma": "alcance", "pos": "noun", "article": None}],
        {"alcance": "el"},
    )
    assert filled[0]["article"] == "el"
    still_empty = drop_related_missing_articles(
        [{"lemma": "nada", "pos": "noun", "article": None}], "es"
    )
    assert still_empty == []


def test_assemble_family_keeps_lo_and_drops_bare_spanish_noun():
    profile = SimpleNamespace(app_lang="pl", learning_lang="es", cefr_level="A2")
    core = {
        "lemma": "limitar",
        "pos": "verb",
        "ipa": "a",
        "meanings": [
            {
                "gloss_l1": "ograniczać",
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
        "word_family_l2": [
            {"lemma": "alcance", "pos": "noun", "article": "el", "gloss_l1": "zasięg"},
            {"lemma": "studente", "pos": "noun", "article": "lo", "gloss_l1": "student"},
            {"lemma": "hueco", "pos": "noun", "gloss_l1": "luka"},
            {"lemma": "limitación", "pos": "noun", "article": "la", "gloss_l1": "ograniczenie"},
        ],
    }
    card = assemble_core_card(profile, "limitar", "verb", core)
    family = {w["lemma"]: w for w in card["word_family_l2"]}
    assert family["alcance"]["article"] == "el"
    assert family["studente"]["article"] == "lo"
    assert "hueco" not in family
    assert family["limitación"]["article"] == "la"

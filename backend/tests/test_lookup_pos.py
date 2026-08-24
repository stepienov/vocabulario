# -*- coding: utf-8 -*-
"""Lookup POS: locutions vs periphrases across supported L2s."""

from app.services.lookup_candidates import sanitize_lookup_candidates
from app.services.lookup_pos import is_construction_headword, refine_lookup_pos


def test_spanish_collocation_is_phrase_not_verb():
    assert refine_lookup_pos("pagar a plazos", "verb", learning_lang="es") == "phrase"
    assert refine_lookup_pos("comprar a plazos", "verb", learning_lang="es") == "phrase"
    assert refine_lookup_pos("pedir perdón", "verb", learning_lang="es") == "phrase"
    assert refine_lookup_pos("hacer la cama", "verb", learning_lang="es") == "phrase"


def test_spanish_periphrasis_is_construction():
    assert refine_lookup_pos("tener que", "verb", learning_lang="es") == "construction"
    assert refine_lookup_pos("hay que", "verb", learning_lang="es") == "construction"
    assert refine_lookup_pos("ir a", "verb", learning_lang="es") == "construction"
    assert refine_lookup_pos("volver a hacer algo", "verb", learning_lang="es") == "construction"
    assert refine_lookup_pos("ir a comprar", "verb", learning_lang="es") == "construction"
    assert refine_lookup_pos("acabar de", "verb", learning_lang="es") == "construction"


def test_spanish_ir_a_place_is_phrase():
    assert refine_lookup_pos("ir a casa", "verb", learning_lang="es") == "phrase"
    assert refine_lookup_pos("volver a casa", "verb", learning_lang="es") == "phrase"


def test_single_verb_stays_verb():
    assert refine_lookup_pos("comprar", "verb", learning_lang="es") == "verb"
    assert refine_lookup_pos("financiar", "verb", learning_lang="es") == "verb"
    assert refine_lookup_pos("se laver", "verb", learning_lang="fr") == "verb"
    assert refine_lookup_pos("sich erinnern", "verb", learning_lang="de") == "verb"


def test_article_noun_stays_noun():
    assert refine_lookup_pos("el libro", "noun", learning_lang="es") == "noun"


def test_english_phrasal_vs_periphrasis():
    assert refine_lookup_pos("look up", "verb", learning_lang="en") == "phrase"
    assert refine_lookup_pos("give up", "verb", learning_lang="en") == "phrase"
    assert refine_lookup_pos("take care of", "verb", learning_lang="en") == "phrase"
    assert refine_lookup_pos("have to", "verb", learning_lang="en") == "construction"
    assert refine_lookup_pos("be going to", "verb", learning_lang="en") == "construction"
    assert refine_lookup_pos("used to", "verb", learning_lang="en") == "construction"
    assert refine_lookup_pos("going to the store", "verb", learning_lang="en") == "phrase"


def test_other_l2_periphrases():
    assert refine_lookup_pos("venir de", "verb", learning_lang="fr") == "construction"
    assert refine_lookup_pos("être en train de", "verb", learning_lang="fr") == "construction"
    assert refine_lookup_pos("aller manger", "verb", learning_lang="fr") == "construction"
    assert refine_lookup_pos("avoir peur", "verb", learning_lang="fr") == "phrase"
    assert refine_lookup_pos("anfangen zu", "verb", learning_lang="de") == "construction"
    assert refine_lookup_pos("stare per", "verb", learning_lang="it") == "construction"
    assert refine_lookup_pos("ter que", "verb", learning_lang="pt-br") == "construction"
    assert refine_lookup_pos("acabar de", "verb", learning_lang="pt-pt") == "construction"
    assert refine_lookup_pos("być w stanie", "verb", learning_lang="pl") == "construction"
    assert refine_lookup_pos("mieć na myśli", "verb", learning_lang="pl") == "phrase"
    assert refine_lookup_pos("быть в состоянии", "verb", learning_lang="ru") == "construction"
    assert refine_lookup_pos("يجب أن", "verb", learning_lang="ar") == "construction"
    assert refine_lookup_pos("zorunda olmak", "verb", learning_lang="tr") == "construction"
    assert refine_lookup_pos("có thể", "verb", learning_lang="vi") == "construction"


def test_cjk_unspaced_constructions():
    assert is_construction_headword("なければならない", learning_lang="ja")
    assert refine_lookup_pos("ている", "verb", learning_lang="ja") == "construction"
    assert is_construction_headword("고 있다", learning_lang="ko")
    assert is_construction_headword("不得不", learning_lang="zh")


def test_sanitize_reclassifies_and_keeps_four_word_construction():
    out = sanitize_lookup_candidates(
        [
            {"lemma": "pagar a plazos", "pos": "verb", "gloss": "płacić na raty"},
            {"lemma": "estar a punto de", "pos": "verb", "gloss": "zaraz coś zrobić"},
            {"lemma": "comprar", "pos": "verb", "gloss": "kupić"},
        ],
        learning_lang="es",
    )
    by_lemma = {c["lemma"]: c["pos"] for c in out}
    assert by_lemma["pagar a plazos"] == "phrase"
    assert by_lemma["estar a punto de"] == "construction"
    assert by_lemma["comprar"] == "verb"


def test_slot_marker_is_construction():
    assert refine_lookup_pos("volver a + inf", "verb", learning_lang="es") == "construction"

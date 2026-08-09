# -*- coding: utf-8 -*-
"""POS normalization — all LSP languages must return canonical English buckets."""

import pytest

from app.services.pos_normalize import (
    canonicalize_lookup_candidate,
    ensure_noun_article,
    infer_gender_from_lemma,
    infer_gender_from_pos,
    lookup_dedup_key,
    merge_lookup_variants,
    normalize_pos_bucket,
)
from app.services.lookup_candidates import dedupe_lookup_candidates, sanitize_lookup_candidates


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("noun", "noun"),
        ("n", "noun"),
        ("sustantivo masculino", "noun"),
        ("sustantivo femenino", "noun"),
        ("rzeczownik", "noun"),
        ("substantivo masculino", "noun"),
        ("Nom", "noun"),
        ("verb", "verb"),
        ("verbo", "verb"),
        ("czasownik", "verb"),
        ("v", "verb"),
        ("adj", "adj"),
        ("adjetivo", "adj"),
        ("przymiotnik", "adj"),
        ("adjective", "adj"),
        ("adv", "adv"),
        ("adverbio", "adv"),
        ("przysłówek", "adv"),
        ("prep", "prep"),
        ("przyimek", "prep"),
        ("conj", "conj"),
        ("pron", "pron"),
        ("det", "det"),
        ("interj", "interj"),
        ("wykrzyknik", "interj"),
        ("phrase", "phrase"),
        ("construction", "construction"),
        ("garbage xyz", "unknown"),
        (None, "unknown"),
        ("", "unknown"),
        # Italian
        ("sostantivo maschile", "noun"),
        ("verbo", "verb"),
        ("aggettivo", "adj"),
        ("avverbio", "adv"),
        ("preposizione", "prep"),
        # Portuguese
        ("substantivo masculino", "noun"),
        ("advérbio", "adv"),
        ("preposição", "prep"),
        ("conjunção", "conj"),
        # German
        ("Substantiv maskulinum", "noun"),
        ("Adjektiv", "adj"),
        ("Interjektion", "interj"),
        # Russian
        ("существительное", "noun"),
        ("прилагательное", "adj"),
        ("наречие", "adv"),
        ("предлог", "prep"),
        ("местоимение", "pron"),
        # Chinese
        ("名词", "noun"),
        ("动词", "verb"),
        ("形容词", "adj"),
        ("副词", "adv"),
        ("介词", "prep"),
        # Japanese
        ("名詞", "noun"),
        ("動詞", "verb"),
        ("形容詞", "adj"),
        ("副詞", "adv"),
        # Korean
        ("명사", "noun"),
        ("동사", "verb"),
        ("형용사", "adj"),
        ("부사", "adv"),
        # Turkish
        ("isim", "noun"),
        ("fiil", "verb"),
        ("sıfat", "adj"),
        ("zarf", "adv"),
        ("edat", "prep"),
        # Vietnamese
        ("danh từ", "noun"),
        ("động từ", "verb"),
        ("tính từ", "adj"),
        ("trạng từ", "adv"),
        ("giới từ", "prep"),
        # Hindi
        ("संज्ञा", "noun"),
        ("क्रिया", "verb"),
        ("विशेषण", "adj"),
        # Arabic (common LLM labels)
        ("اسم", "noun"),
        ("فعل", "verb"),
        ("صفة", "adj"),
    ],
)
def test_normalize_pos_bucket(raw, expected):
    assert normalize_pos_bucket(raw) == expected


@pytest.mark.parametrize(
    "pos,gender",
    [
        ("sustantivo masculino", "m"),
        ("sustantivo femenino", "f"),
        ("substantivo masculino", "m"),
        ("rzeczownik żeński", "f"),
        ("noun masculine", "m"),
        ("noun", None),
    ],
)
def test_infer_gender_from_pos(pos, gender):
    assert infer_gender_from_pos(pos) == gender


@pytest.mark.parametrize(
    "lemma,lang,expected",
    [
        ("el libro", "es", "m"),
        ("la casa", "es", "f"),
        ("le livre", "fr", "m"),
        ("la maison", "fr", "f"),
        ("der Mann", "de", "m"),
        ("die Frau", "de", "f"),
        ("das Haus", "de", "n"),
        ("il libro", "it", "m"),
        ("o livro", "pt-br", "m"),
        ("a casa", "pt-br", "f"),
        ("libro", "es", None),
    ],
)
def test_infer_gender_from_lemma(lemma, lang, expected):
    assert infer_gender_from_lemma(lemma, lang) == expected


def test_ensure_noun_article_spanish():
    assert ensure_noun_article("libro", learning_lang="es", gender="m") == "el libro"
    assert ensure_noun_article("tripa", learning_lang="es", gender="f") == "la tripa"
    assert ensure_noun_article("el libro", learning_lang="es", gender="m") == "el libro"


def test_canonicalize_strips_verbose_pos_and_adds_article():
    raw = {"lemma": "libro", "pos": "sustantivo masculino", "gloss": "książka"}
    out = canonicalize_lookup_candidate(raw, learning_lang="es")
    assert out["pos"] == "noun"
    assert out["lemma"] == "el libro"


def test_dedup_libro_sustantivo_and_noun():
    cands = [
        {"lemma": "libro", "pos": "sustantivo masculino", "gloss": "książka"},
        {"lemma": "libro", "pos": "noun", "gloss": "książka"},
        {"lemma": "tripa", "pos": "sustantivo femenino", "gloss": "kiszka"},
        {"lemma": "tripa", "pos": "noun", "gloss": "kiszka"},
        {"lemma": "morcilla", "pos": "noun", "gloss": "kiszka"},
    ]
    out = sanitize_lookup_candidates(cands, learning_lang="es")
    lemmas = [c["lemma"] for c in out]
    assert lemmas.count("el libro") == 1
    assert lemmas.count("la tripa") == 1
    assert "libro" not in lemmas
    assert "tripa" not in lemmas
    assert all(c["pos"] == "noun" for c in out)
    assert len(out) == 3


def test_dedup_key_ignores_pos_language():
    k1 = lookup_dedup_key("el libro", "sustantivo masculino", learning_lang="es")
    k2 = lookup_dedup_key("libro", "noun", learning_lang="es")
    assert k1 == k2


def test_merge_prefers_article_and_canonical_pos():
    a = {"lemma": "libro", "pos": "sustantivo masculino", "gloss": "książka"}
    b = {"lemma": "el libro", "pos": "noun", "gloss": "książka"}
    merged = merge_lookup_variants(a, b, learning_lang="es")
    assert merged["lemma"] == "el libro"
    assert merged["pos"] == "noun"


def test_german_noun_article():
    out = canonicalize_lookup_candidate(
        {"lemma": "Haus", "pos": "Substantiv neutrum", "gloss": "dom"},
        learning_lang="de",
    )
    assert out["pos"] == "noun"
    assert out["lemma"] == "das Haus"


def test_french_noun_article():
    out = canonicalize_lookup_candidate(
        {"lemma": "maison", "pos": "nom féminin", "gloss": "dom"},
        learning_lang="fr",
    )
    assert out["pos"] == "noun"
    assert out["lemma"] == "la maison"

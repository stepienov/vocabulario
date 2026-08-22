# -*- coding: utf-8 -*-
"""Query-keyed lookup cache: normalize + append-never-overwrite."""

from app.services.lookup_candidates import (
    append_lookup_candidates,
    normalize_lookup_query,
    rank_lookup_candidates,
)


def test_normalize_lookup_query_folds_diacritics_and_punct():
    assert normalize_lookup_query("Książka") == normalize_lookup_query("ksiazka")
    assert normalize_lookup_query("ksiazka.") == normalize_lookup_query("książka")
    assert normalize_lookup_query("  niño ") == normalize_lookup_query("nino")
    assert normalize_lookup_query("Łódź") == normalize_lookup_query("lodz")


def test_append_never_overwrites_existing_gloss():
    existing = [{"lemma": "el libro", "pos": "noun", "gloss": "książka"}]
    incoming = [{"lemma": "el libro", "pos": "noun", "gloss": "pozycja (inna glosa)"}]
    merged, added = append_lookup_candidates(existing, incoming, learning_lang="es")
    assert added == 0
    assert len(merged) == 1
    assert merged[0]["gloss"] == "książka"
    assert merged[0]["lemma"] == "el libro"


def test_append_adds_new_lemma_pos_and_keeps_old():
    existing = [{"lemma": "play", "pos": "verb", "gloss": "grać"}]
    incoming = [
        {"lemma": "play", "pos": "verb", "gloss": "występować"},
        {"lemma": "play", "pos": "noun", "gloss": "sztuka"},
        {"lemma": "player", "pos": "noun", "gloss": "gracz"},
    ]
    merged, added = append_lookup_candidates(existing, incoming, learning_lang="en")
    assert added == 2
    assert merged[0]["lemma"] == "play"
    assert merged[0]["pos"] == "verb"
    assert merged[0]["gloss"] == "grać"
    pos = {(c["lemma"], c["pos"]) for c in merged}
    assert ("play", "noun") in pos
    assert ("player", "noun") in pos


def test_append_dedupes_article_variant_without_replacing():
    existing = [{"lemma": "libro", "pos": "noun", "gloss": "książka"}]
    incoming = [{"lemma": "el libro", "pos": "noun", "gloss": "książka"}]
    merged, added = append_lookup_candidates(existing, incoming, learning_lang="es")
    assert added == 0
    assert merged[0]["lemma"] == "libro"


def test_append_empty_incoming_is_zero_added():
    existing = [{"lemma": "casa", "pos": "noun", "gloss": "dom"}]
    merged, added = append_lookup_candidates(existing, [], learning_lang="es")
    assert added == 0
    assert merged == existing


def test_rank_union_puts_closest_first():
    union, added = append_lookup_candidates(
        [{"lemma": "la tripa", "pos": "noun", "gloss": "kiszka"}],
        [{"lemma": "el libro", "pos": "noun", "gloss": "książka"}],
        learning_lang="es",
    )
    assert added == 1
    ranked = rank_lookup_candidates(union, "ksiazka", learning_lang="es")
    assert ranked[0]["lemma"] == "el libro"
    assert {c["lemma"] for c in ranked} == {"el libro", "la tripa"}


def test_expand_prompt_lists_existing_candidates():
    from app.ai.prompts.v1 import LOOKUP_EXPAND_PROMPT_V1, lookup_output_form_rules_text
    from app.services.llm import LLMService

    already = LLMService._already_block(
        [{"lemma": "el libro", "pos": "noun", "gloss": "książka"}]
    )
    prompt = LOOKUP_EXPAND_PROMPT_V1.format(
        native_name="Polish",
        learning_name="Spanish",
        text="ksiazka",
        cefr="A2",
        pair_guidance="pair",
        lookup_output_form_rules=lookup_output_form_rules_text("pl", "es"),
        already_block=already,
    )
    assert "User query string: \"ksiazka\"" in prompt
    assert "el libro" in prompt
    assert "do NOT repeat" in prompt
    assert LLMService._already_block([]) == (
        "None yet — this is a cold start. Return the full high-recall "
        "union of all plausible readings (up to 16)."
    )

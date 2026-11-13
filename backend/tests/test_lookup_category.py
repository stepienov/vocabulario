"""Category lookup prompts and ranking."""

from app.ai.prompts.v1 import (
    LOOKUP_CATEGORY_DRAFT_PROMPT_V1,
    LOOKUP_CATEGORY_EXPAND_PROMPT_V1,
    lookup_output_form_rules_text,
)
from app.services.lexical import CATEGORY_QUERY_PREFIX, LexicalService
from app.services.lookup_candidates import (
    LOOKUP_CATEGORY_DRAFT_LIMIT,
    LOOKUP_CATEGORY_LIMIT,
    append_lookup_candidates,
    candidate_is_confident,
    rank_category_candidates,
)
from app.services.llm import LLMService


def test_assoc_rounds_are_separate_tasks():
    from uuid import UUID

    from app.services.lookup_category_jobs import _key

    user = UUID("00000000-0000-0000-0000-000000000001")
    profile = UUID("00000000-0000-0000-0000-000000000002")
    other = UUID("00000000-0000-0000-0000-000000000003")
    assert _key(user, profile, "wysyłać", 1) != _key(user, profile, "wysyłać", 2)
    assert _key(user, profile, "wysyłać", 2) != _key(other, profile, "wysyłać", 2)
    assert _key(user, profile, "wysyłać", 2) == _key(user, profile, "wysyłać", 2)


def test_assoc_key_fits_the_column():
    svc = LexicalService(db=None)  # type: ignore[arg-type]
    text = "ą" * 200
    word = svc._assoc_key(text)
    third = svc._assoc_key(text, 3)
    assert word.startswith("assoc:")
    assert not word.startswith(CATEGORY_QUERY_PREFIX)
    assert len(word) <= 200
    assert len(third) <= 200
    assert third == word + ":3"


def test_category_draft_prompt_includes_query():
    prompt = LOOKUP_CATEGORY_DRAFT_PROMPT_V1.format(
        native_name="Polish",
        learning_name="Spanish",
        text="czerwony",
        pair_guidance="pair",
    )
    assert "czerwony" in prompt
    assert "8 total" in prompt


def test_category_expand_prompt_lists_already():
    already = LLMService._already_block(
        [{"lemma": "rojo", "pos": "adj", "gloss": "czerwony"}]
    )
    prompt = LOOKUP_CATEGORY_EXPAND_PROMPT_V1.format(
        native_name="Polish",
        learning_name="Spanish",
        text="czerwony",
        theme="Colors",
        pair_guidance="pair",
        lookup_output_form_rules=lookup_output_form_rules_text("pl", "es"),
        already_block=already,
    )
    assert "rojo" in prompt
    assert "do NOT repeat" in prompt
    assert "czerwony" in prompt


def test_rank_category_puts_seed_first():
    ranked = rank_category_candidates(
        [
            {"lemma": "azul", "pos": "adj", "gloss": "niebieski"},
            {"lemma": "rojo", "pos": "adj", "gloss": "czerwony"},
            {"lemma": "verde", "pos": "adj", "gloss": "zielony"},
        ],
        "czerwony",
        learning_lang="es",
    )
    assert ranked[0]["lemma"] == "rojo"
    assert {c["lemma"] for c in ranked} == {"azul", "rojo", "verde"}


def test_unrelated_lexicon_hit_is_not_a_confident_seed():
    assert not candidate_is_confident(
        {"lemma": "trabajo", "pos": "noun", "gloss": "praca"},
        "czerwony",
        learning_lang="es",
    )
    assert candidate_is_confident(
        {"lemma": "rojo", "pos": "adj", "gloss": "czerwony"},
        "czerwony",
        learning_lang="es",
    )


def test_category_draft_merges_onto_seed_without_dropping_it():
    seed = [{"lemma": "rojo", "pos": "adj", "gloss": "czerwony"}]
    draft = [
        {"lemma": "rojo", "pos": "adj", "gloss": "czerwony"},
        {"lemma": "azul", "pos": "adj", "gloss": "niebieski"},
        {"lemma": "verde", "pos": "adj", "gloss": "zielony"},
    ]
    merged, added = append_lookup_candidates(
        seed, draft, learning_lang="es", limit=LOOKUP_CATEGORY_LIMIT
    )
    ranked = rank_category_candidates(merged, "czerwony", learning_lang="es")
    assert LOOKUP_CATEGORY_DRAFT_LIMIT == 8
    assert added == 2
    assert ranked[0]["lemma"] == "rojo"
    assert {c["lemma"] for c in ranked} == {"rojo", "azul", "verde"}

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


def test_category_cache_key_is_prefixed():
    svc = LexicalService(db=None)  # type: ignore[arg-type]
    key = svc._category_cache_key("Czerwony!")
    word = svc._query_cache_key("Czerwony!")
    assert key.startswith(CATEGORY_QUERY_PREFIX)
    assert key != word
    assert key == CATEGORY_QUERY_PREFIX + word


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

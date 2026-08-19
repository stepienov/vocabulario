"""Koszt LLM — prompty, cache, lookup skip."""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.prompts.v1 import build_enrichment_core_prompt_parts, build_similar_words_prompt_parts
from app.services.card_jobs import _card_lookup_resolved


def test_enrichment_prompt_static_before_lemma():
    static, dynamic = build_enrichment_core_prompt_parts(
        native="pl",
        learning="es",
        lemma="hablar",
        pos="verb",
        cefr="B1",
        gloss_hint="mówić",
    )
    assert "hablar" not in static
    assert "hablar" in dynamic
    assert "mówić" in dynamic
    assert len(static) > len(dynamic)


def test_similar_words_prompt_static_before_lemma():
    static, dynamic = build_similar_words_prompt_parts(
        native="pl",
        learning="es",
        lemma="hablar",
        pos="verb",
        count=12,
    )
    assert "hablar" not in static
    assert "hablar" in dynamic


def test_card_lookup_resolved_with_gloss_and_pos():
    card = SimpleNamespace(
        lexical_entry_id=None,
        gloss_primary="mówić",
        pos="verb",
    )
    assert _card_lookup_resolved(card)


def test_card_lookup_resolved_with_lexical_entry_only():
    card = SimpleNamespace(
        lexical_entry_id="00000000-0000-0000-0000-000000000001",
        gloss_primary=None,
        pos=None,
    )
    assert _card_lookup_resolved(card)


def test_card_lookup_not_resolved_without_gloss():
    card = SimpleNamespace(
        lexical_entry_id=None,
        gloss_primary=None,
        pos="verb",
    )
    assert not _card_lookup_resolved(card)

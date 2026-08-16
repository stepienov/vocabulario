from types import SimpleNamespace

from app.core.lemma_keys import cache_lookup_keys, canonical_lemma
from app.services.card_jobs import (
    entry_compatible_with_card,
    lexical_lookup_variants,
    pick_ready_entry,
    public_enrichment_error,
    same_headword,
)


def test_lookup_variants_match_article_and_bare():
    variants = lexical_lookup_variants("el negocio", "es")
    assert "el negocio" in variants
    assert "negocio" in variants


def test_lookup_variants_match_l1_gloss_style():
    variants = lexical_lookup_variants("el sueño", "fr")
    assert "sueño" in variants
    assert "el sueño" in variants


def test_canonical_lemma_strips_article_punct_and_parenthetical():
    assert canonical_lemma("el resultado") == "resultado"
    assert canonical_lemma("resultado (efecto)") == "resultado"
    assert canonical_lemma("El Resultado.") == "resultado"
    assert canonical_lemma("le résultat") == "résultat"
    assert canonical_lemma("l'amour") == "amour"
    assert canonical_lemma("  el   resultado,  ") == "resultado"


def test_el_resultado_hits_cached_french_gloss():
    """Dokładny miss z produkcji: karta 'el resultado', PG L1 'resultado (efecto)'."""
    keys = cache_lookup_keys("el resultado", None)
    stored_l1 = canonical_lemma("resultado (efecto)")
    stored_l2 = canonical_lemma("le résultat")
    assert "resultado" in keys
    assert stored_l1 in keys
    assert stored_l2 not in keys


def test_public_enrichment_error_hides_openai_billing():
    err = public_enrichment_error(
        Exception(
            "Error code: 429 - {'error': {'message': 'You have no credits remaining.'"
        )
    )
    assert err == "enrichment_unavailable"
    assert "credits" not in err


def _entry(pos: str, lemma: str = "play"):
    return SimpleNamespace(
        pos=pos,
        lemma_l2=lemma,
        lemma_l1_primary="x",
        content={"pos": pos, "meanings": [{"gloss_l1": "x"}]},
    )


def test_pick_ready_entry_does_not_return_other_pos():
    verb = _entry("verb")
    assert pick_ready_entry([verb], "noun") is None
    assert pick_ready_entry([verb], "verb") is verb


def test_pick_ready_entry_selects_matching_homograph():
    verb = _entry("verb")
    noun = _entry("noun")
    assert pick_ready_entry([verb, noun], "noun") is noun
    assert pick_ready_entry([verb, noun], "verb") is verb


def test_entry_compatible_with_card_rejects_pos_mismatch():
    card = SimpleNamespace(pos="noun", lemma_l2="play")
    verb_entry = SimpleNamespace(pos="verb", lemma_l2="play", content={"pos": "verb"})
    noun_entry = SimpleNamespace(pos="noun", lemma_l2="play", content={"pos": "noun"})
    assert not entry_compatible_with_card(card, verb_entry)
    assert entry_compatible_with_card(card, noun_entry)


def test_same_headword_allows_article_not_synonym():
    assert same_headword("acabar", "acabar")
    assert same_headword("el negocio", "negocio")
    assert not same_headword("acabar", "terminar")


def test_pick_ready_entry_does_not_swap_synonym_with_same_gloss():
    acabar = _entry("verb", "acabar")
    terminar = _entry("verb", "terminar")
    assert pick_ready_entry([terminar, acabar], "verb", require_lemma="acabar") is acabar
    assert pick_ready_entry([terminar], "verb", require_lemma="acabar") is None


def test_entry_compatible_rejects_synonym_headword():
    card = SimpleNamespace(pos="verb", lemma_l2="acabar")
    terminar = SimpleNamespace(pos="verb", lemma_l2="terminar", content={"pos": "verb"})
    acabar = SimpleNamespace(pos="verb", lemma_l2="acabar", content={"pos": "verb"})
    assert not entry_compatible_with_card(card, terminar)
    assert entry_compatible_with_card(card, acabar)


def test_lexical_id_never_falls_back_to_other_pos():
    from app.services.lexical import lexical_entry_for_candidate

    verb = SimpleNamespace(id="verb-id", pos="verb")
    by_key = {("play", "verb"): verb}
    assert lexical_entry_for_candidate(by_key, "play", "verb") is verb
    assert lexical_entry_for_candidate(by_key, "play", "noun") is None

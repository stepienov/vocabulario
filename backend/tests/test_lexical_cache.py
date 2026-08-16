from app.core.lemma_keys import cache_lookup_keys, canonical_lemma
from app.services.card_jobs import lexical_lookup_variants, public_enrichment_error


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

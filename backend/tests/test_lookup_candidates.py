# -*- coding: utf-8 -*-
"""Lookup matching must be HIGH RECALL.

The word lookup is the core feature of the app: a missed suggestion is a fatal bug,
an extra plausible one is harmless. These tests pin down that the matcher tolerates the
real ways users diverge from canonical spelling — missing diacritics, stroke letters,
transposed/dropped/doubled letters, adjacent-key slips and stray punctuation — and that
ranking surfaces the intended word first WITHOUT ever dropping the alternatives.
"""

import pytest

from app.services.lookup_candidates import (
    candidate_is_confident,
    dedupe_lookup_candidates,
    edit_distance,
    gloss_identifies_query,
    gloss_query_score,
    has_confident_match,
    is_diacritic_only_variant,
    lemma_matches_query,
    merge_candidates,
    rank_lookup_candidates,
    sanitize_lookup_candidates,
    token_similarity,
)

# Canonical (correctly spelled) forms
KSIAZKA = "książka"
CZESC_GREETING = "cześć"
CZESC_PART = "część"
ZUBR = "żubr"
GORA = "góra"
WAZ = "wąż"
LODZ = "Łódź"
NINO = "niño"
CAFE = "café"
CORAZON = "corazón"
ELEVE = "élève"
GRUN = "grün"
STRASSE = "straße"


# ---------------------------------------------------------------------------
# 1. Missing diacritics == same word (the #1 real-world case)
# ---------------------------------------------------------------------------

DIACRITIC_PAIRS = [
    ("ksiazka", KSIAZKA),
    ("czesc", CZESC_GREETING),
    ("czesc", CZESC_PART),
    ("zubr", ZUBR),
    ("gora", GORA),
    ("waz", WAZ),
    ("nino", NINO),
    ("cafe", CAFE),
    ("corazon", CORAZON),
    ("eleve", ELEVE),
    ("grun", GRUN),
    ("strasse", STRASSE),
]


@pytest.mark.parametrize("typed,canonical", DIACRITIC_PAIRS)
def test_missing_diacritics_is_same_word(typed, canonical):
    assert is_diacritic_only_variant(typed, canonical)
    assert token_similarity(typed, canonical) == 1.0
    assert gloss_identifies_query(canonical, typed)
    assert lemma_matches_query(canonical, typed)


@pytest.mark.parametrize("typed,canonical", DIACRITIC_PAIRS)
def test_diacritic_gloss_score_is_perfect(typed, canonical):
    assert gloss_query_score(canonical, typed) == 1.0


# ---------------------------------------------------------------------------
# 2. Stroke letters that NFD does not decompose (ł→l, ø→o, …)
# ---------------------------------------------------------------------------

STROKE_PAIRS = [
    ("lodz", LODZ),
    ("lyzka", "łyżka"),
    ("dzialac", "działać"),
    ("smorrebrod", "smørrebrød"),
]


@pytest.mark.parametrize("typed,canonical", STROKE_PAIRS)
def test_stroke_letters_typed_as_plain_latin(typed, canonical):
    assert is_diacritic_only_variant(typed, canonical)
    assert token_similarity(typed, canonical) == 1.0
    assert gloss_identifies_query(canonical, typed)


# ---------------------------------------------------------------------------
# 3. Letter transpositions count as a single edit (Damerau)
# ---------------------------------------------------------------------------

TRANSPOSITIONS = [
    ("form", "from"),
    ("ksaizka", "ksiazka"),
    ("recieve", "receive"),
    ("libor", "libro"),
    ("teh", "the"),
]


@pytest.mark.parametrize("a,b", TRANSPOSITIONS)
def test_single_transposition_is_one_edit(a, b):
    assert edit_distance(a, b) == 1
    assert token_similarity(a, b) >= 0.79


def test_transposed_diacritic_word_still_close():
    # "ksaizka" (swap) is a typo of "książka"; not exact, but clearly close.
    assert token_similarity("ksaizka", KSIAZKA) >= 0.79
    assert not is_diacritic_only_variant("ksaizka", KSIAZKA)


# ---------------------------------------------------------------------------
# 4. Ordinary small typos: substitution / insertion / deletion
# ---------------------------------------------------------------------------

SMALL_TYPOS = [
    ("ksiazkaa", "ksiazka"),   # doubled letter
    ("ksizka", "ksiazka"),     # dropped letter
    ("ksiaska", "ksiazka"),    # adjacent-key substitution
    ("hetl", "help"),          # jumbled short word (edit 2)
    ("przyjacel", "przyjaciel"),
]


@pytest.mark.parametrize("typed,target", SMALL_TYPOS)
def test_small_typo_is_high_similarity(typed, target):
    assert token_similarity(typed, target) >= 0.72


def test_unrelated_words_are_low_similarity():
    assert token_similarity("ksiazka", "samochod") < 0.4
    assert token_similarity("libro", "mesa") < 0.4


# ---------------------------------------------------------------------------
# 5. Stray punctuation and whitespace are ignored
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "noisy",
    ["książka.", " książka ", "książka,", '"książka"', "ksi,azka", "ksiazka."],
)
def test_stray_punctuation_ignored(noisy):
    assert gloss_identifies_query(noisy, "ksiazka") or is_diacritic_only_variant(
        noisy, "ksiazka"
    )
    assert token_similarity(noisy, "ksiazka") == 1.0


def test_lemma_matches_query_ignores_trailing_punct():
    assert lemma_matches_query("libro", "libro,")
    assert lemma_matches_query("libro", " libro ")
    assert lemma_matches_query("brać", "brac")


# ---------------------------------------------------------------------------
# 6. Ranking: diacritic completion wins, alternatives are NEVER dropped
# ---------------------------------------------------------------------------

def test_ksiazka_prefers_libro_but_keeps_kiszka():
    candidates = [
        {"lemma": "morcilla", "pos": "noun", "gloss": "kiszka"},
        {"lemma": "libro", "pos": "noun", "gloss": KSIAZKA},
    ]
    ranked = rank_lookup_candidates(candidates, "ksiazka")
    assert ranked[0]["lemma"] == "libro"          # intended word first
    assert len(ranked) == 2                         # kiszka reading kept
    assert {c["lemma"] for c in ranked} == {"libro", "morcilla"}


def test_exact_l2_lemma_ranks_first():
    candidates = [
        {"lemma": "casa", "pos": "noun", "gloss": "house"},
        {"lemma": "libro", "pos": "noun", "gloss": "book"},
    ]
    ranked = rank_lookup_candidates(candidates, "libro", learning_lang="es")
    assert ranked[0]["lemma"] == "libro"


def test_el_libro_ranks_first_among_fuzzy_neighbors():
    """User types L2 headword without article — exact stem must beat edit neighbors."""
    candidates = [
        {"lemma": "la libra", "pos": "noun", "gloss": "libra"},
        {"lemma": "la libido", "pos": "noun", "gloss": "libido"},
        {"lemma": "el libelo", "pos": "noun", "gloss": "libel"},
        {"lemma": "el hígado", "pos": "noun", "gloss": "liver"},
        {"lemma": "el libro", "pos": "noun", "gloss": "book"},
    ]
    ranked = rank_lookup_candidates(candidates, "libro", learning_lang="es")
    assert ranked[0]["lemma"] == "el libro"


def test_near_l2_transposition_typo_ranks_high():
    candidates = [
        {"lemma": "mesa", "pos": "noun", "gloss": "table"},
        {"lemma": "libro", "pos": "noun", "gloss": "book"},
    ]
    ranked = rank_lookup_candidates(candidates, "libor", learning_lang="es")  # swap of libro
    assert ranked[0]["lemma"] == "libro"


def test_diacritic_lemma_reading_ranks_first():
    # L2=Polish, user typed "brac" meaning the verb "brać".
    candidates = [
        {"lemma": "bachor", "pos": "noun", "gloss": "brat"},
        {"lemma": "brać", "pos": "verb", "gloss": "to take"},
    ]
    ranked = rank_lookup_candidates(candidates, "brac")
    assert ranked[0]["lemma"] == "brać"


def test_ranking_never_drops_candidates():
    candidates = [
        {"lemma": "morcilla", "pos": "noun", "gloss": "kiszka"},
        {"lemma": "libro", "pos": "noun", "gloss": KSIAZKA},
        {"lemma": "casa", "pos": "noun", "gloss": "dom"},
    ]
    ranked = rank_lookup_candidates(candidates, "ksiazka")
    assert len(ranked) == len(candidates)


# ---------------------------------------------------------------------------
# 7. has_confident_match drives the recovery pass
# ---------------------------------------------------------------------------

def test_no_confident_match_triggers_recovery():
    # Only a different-word typo reading present -> we must still look further.
    candidates = [{"lemma": "morcilla", "pos": "noun", "gloss": "kiszka"}]
    assert not has_confident_match(candidates, "ksiazka")


def test_confident_when_gloss_completes_diacritics():
    candidates = [{"lemma": "libro", "pos": "noun", "gloss": KSIAZKA}]
    assert has_confident_match(candidates, "ksiazka")
    assert candidate_is_confident(candidates[0], "ksiazka")


def test_confident_when_lemma_is_l2_headword():
    candidates = [{"lemma": "brać", "pos": "verb", "gloss": "to take"}]
    assert has_confident_match(candidates, "brac")


def test_confident_when_lemma_has_article_prefix():
    candidates = [{"lemma": "el libro", "pos": "noun", "gloss": "book"}]
    assert has_confident_match(candidates, "libro", learning_lang="es")


def test_confident_scans_whole_list_not_only_top():
    candidates = [
        {"lemma": "morcilla", "pos": "noun", "gloss": "kiszka"},
        {"lemma": "libro", "pos": "noun", "gloss": KSIAZKA},
    ]
    assert has_confident_match(candidates, "ksiazka")


def test_empty_is_not_confident():
    assert not has_confident_match([], "ksiazka")


# ---------------------------------------------------------------------------
# 8. Damerau edit-distance sanity
# ---------------------------------------------------------------------------

def test_edit_distance_basic():
    assert edit_distance("dom", "dom") == 0
    assert edit_distance("dom", "doem") == 1        # insertion
    assert edit_distance("house", "houes") == 1      # transposition
    assert edit_distance("", "abc") == 3
    assert edit_distance("abc", "") == 3


# ---------------------------------------------------------------------------
# 9. sanitize keeps valid headwords, rejects junk phrases
# ---------------------------------------------------------------------------

def test_sanitize_keeps_simple_headwords():
    cands = [
        {"lemma": "libro", "pos": "noun", "gloss": "książka"},
        {"lemma": "brać", "pos": "verb", "gloss": "to take"},
    ]
    out = sanitize_lookup_candidates(cands, learning_lang="es")
    assert len(out) == 2


def test_sanitize_drops_missing_gloss_or_lemma():
    cands = [
        {"lemma": "libro", "pos": "noun", "gloss": ""},
        {"lemma": "", "pos": "noun", "gloss": "book"},
        {"lemma": "casa", "pos": "noun", "gloss": "house"},
    ]
    out = sanitize_lookup_candidates(cands, learning_lang="es")
    assert [c["lemma"] for c in out] == ["casa"]


# ---------------------------------------------------------------------------
# 10. Article variants — el libro ≈ libro (keep article form only)
# ---------------------------------------------------------------------------

def test_dedupe_el_libro_and_libro():
    cands = [
        {"lemma": "el libro", "pos": "noun", "gloss": "książka"},
        {"lemma": "libro", "pos": "noun", "gloss": "książka"},
    ]
    out = dedupe_lookup_candidates(cands, learning_lang="es")
    assert len(out) == 1
    assert out[0]["lemma"] == "el libro"


def test_dedupe_prefers_article_when_bare_comes_first():
    cands = [
        {"lemma": "libro", "pos": "noun", "gloss": "książka"},
        {"lemma": "el libro", "pos": "noun", "gloss": "książka"},
    ]
    out = sanitize_lookup_candidates(cands, learning_lang="es")
    assert len(out) == 1
    assert out[0]["lemma"] == "el libro"


def test_ksizka_scenario_no_duplicate_libro():
    cands = [
        {"lemma": "el libro", "pos": "sustantivo masculino", "gloss": "książka"},
        {"lemma": "el intestino", "pos": "sustantivo masculino", "gloss": "kiszka"},
        {"lemma": "la tripa", "pos": "sustantivo femenino", "gloss": "kiszka"},
        {"lemma": "la morcilla", "pos": "sustantivo femenino", "gloss": "kiszka"},
        {"lemma": "libro", "pos": "noun", "gloss": "książka"},
        {"lemma": "tripa", "pos": "noun", "gloss": "kiszka"},
        {"lemma": "morcilla", "pos": "noun", "gloss": "kiszka"},
    ]
    out = sanitize_lookup_candidates(cands, learning_lang="es")
    lemmas = [c["lemma"] for c in out]
    assert lemmas.count("el libro") == 1
    assert "libro" not in lemmas
    assert "tripa" not in lemmas
    assert all(c["pos"] == "noun" for c in out)
    assert len(lemmas) == 4


def test_merge_candidates_dedupes_across_groups():
    a = [{"lemma": "el libro", "pos": "noun", "gloss": "książka"}]
    b = [{"lemma": "libro", "pos": "noun", "gloss": "książka"}]
    out = merge_candidates(a, b, learning_lang="es")
    assert len(out) == 1
    assert out[0]["lemma"] == "el libro"

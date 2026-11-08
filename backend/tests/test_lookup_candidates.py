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
    cached_lookup_covers_query,
    candidate_is_confident,
    dedupe_lookup_candidates,
    drop_implausible_lookup_rows,
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


def test_exact_gloss_outranks_near_lemma():
    """L1 query must keep its real translation above an edit-neighbor lemma."""
    candidates = [
        {"lemma": "don", "pos": "noun", "gloss": "pan"},
        {"lemma": "la casa", "pos": "noun", "gloss": "dom"},
    ]
    ranked = rank_lookup_candidates(candidates, "dom", learning_lang="es")
    assert ranked[0]["lemma"] == "la casa"


def test_exact_matches_keep_model_order():
    candidates = [
        {"lemma": "el camino", "pos": "noun", "gloss": "droga"},
        {"lemma": "la carretera", "pos": "noun", "gloss": "droga"},
        {"lemma": "el sendero", "pos": "noun", "gloss": "ścieżka"},
    ]
    ranked = rank_lookup_candidates(candidates, "droga", learning_lang="es")
    assert [c["lemma"] for c in ranked[:2]] == ["el camino", "la carretera"]


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
    assert [c["lemma"] for c in out] == ["la casa"]


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


def test_merge_keeps_same_lemma_different_pos():
    verb = [{"lemma": "play", "pos": "verb", "gloss": "grać"}]
    noun = [{"lemma": "play", "pos": "noun", "gloss": "sztuka"}]
    out = merge_candidates(verb, noun, learning_lang="en")
    pos = {c["pos"] for c in out}
    assert pos == {"verb", "noun"}
    assert len(out) == 2


def test_cached_lookup_does_not_cover_single_pos_homograph():
    verb_only = [{"lemma": "play", "pos": "verb", "gloss": "grać"}]
    assert not cached_lookup_covers_query(verb_only, "play", learning_lang="en")
    both = verb_only + [{"lemma": "play", "pos": "noun", "gloss": "sztuka"}]
    assert cached_lookup_covers_query(both, "play", learning_lang="en")


def test_sanitize_keeps_plural_citation_los_cascos():
    out = sanitize_lookup_candidates(
        [{"lemma": "los cascos", "pos": "noun", "gloss": "słuchawki (nauszne)"}],
        learning_lang="es",
    )
    assert len(out) == 1
    assert out[0]["lemma"] == "los cascos"
    assert out[0]["gloss"] == "słuchawki (nauszne)"


def test_english_list_keeps_the_noun_gloss_lista():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "letter", "pos": "noun", "gloss": "list"},
            {"lemma": "list", "pos": "noun", "gloss": "lista"},
            {"lemma": "list", "pos": "verb", "gloss": "wymieniać"},
        ],
        "list",
        learning_lang="en",
    )
    assert ("list", "lista") in {(c["lemma"], c["gloss"]) for c in out}
    assert ("letter", "list") in {(c["lemma"], c["gloss"]) for c in out}


def test_native_word_is_never_the_lemma():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "drogi", "pos": "adjective", "gloss": "drogi, kosztowny"},
            {"lemma": "caro", "pos": "adjective", "gloss": "drogi"},
            {"lemma": "la droga", "pos": "noun", "gloss": "narkotyk"},
        ],
        "drogie",
        learning_lang="es",
        native_lang="pl",
    )
    assert [c["lemma"] for c in out] == ["caro", "la droga"]


def test_polish_adjective_gloss_is_the_citation():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "guapo", "pos": "adj", "gloss": "ładna"},
            {"lemma": "barato", "pos": "adj", "gloss": "tania"},
            {"lemma": "querido", "pos": "adj", "gloss": "drodzy"},
            {"lemma": "rojo", "pos": "adj", "gloss": "czerwone"},
            {"lemma": "caro", "pos": "adj", "gloss": "drogiego, drogiej"},
        ],
        "x",
        learning_lang="es",
        native_lang="pl",
    )
    assert [c["gloss"] for c in out] == ["ładny", "tani", "drogi", "czerwony", "drogi"]


def test_grammar_description_is_not_a_gloss():
    out = drop_implausible_lookup_rows(
        [
            {
                "lemma": "drogiego",
                "pos": "adjective",
                "gloss": "dopełniacz/biernik rodzaju męskiego lub nijakiego od „drogi”",
            },
            {"lemma": "caro", "pos": "adjective", "gloss": "drogi"},
        ],
        "drogiego",
        learning_lang="es",
        native_lang="pl",
    )
    assert [c["lemma"] for c in out] == ["caro"]


def test_spanish_adjective_is_masculine_singular():
    out = sanitize_lookup_candidates(
        [
            {"lemma": "la bonita", "pos": "adjetivo", "gloss": "ładny"},
            {"lemma": "queridos", "pos": "adj", "gloss": "drogi"},
            {"lemma": "costosa", "pos": "adj", "gloss": "drogi"},
            {"lemma": "grandes", "pos": "adj", "gloss": "duży"},
            {"lemma": "felices", "pos": "adj", "gloss": "szczęśliwy"},
            {"lemma": "rosa", "pos": "adj", "gloss": "różowy"},
            {"lemma": "optimista", "pos": "adj", "gloss": "optymistyczny"},
        ],
        learning_lang="es",
    )
    assert [c["lemma"] for c in out] == [
        "bonito",
        "querido",
        "costoso",
        "grande",
        "feliz",
        "rosa",
        "optimista",
    ]


def test_adjective_echo_is_not_rewritten_into_a_spanish_word():
    out = sanitize_lookup_candidates(
        [{"lemma": "droga", "pos": "adj", "gloss": "droga"}],
        learning_lang="es",
    )
    assert out == []


def test_polish_adjective_query_pasted_as_lemma_is_dropped():
    """droga/drogi must not become drogo; caro has to come from the model."""
    out = sanitize_lookup_candidates(
        [{"lemma": "droga", "pos": "adj", "gloss": "drogi", "word": "droga"}],
        learning_lang="es",
    )
    assert out == []


def test_spanish_feminine_adjective_still_becomes_masculine():
    out = sanitize_lookup_candidates(
        [{"lemma": "cara", "pos": "adj", "gloss": "drogi", "word": "cara"}],
        learning_lang="es",
    )
    assert [c["lemma"] for c in out] == ["caro"]


def test_spanish_noun_without_article_is_dropped():
    out = sanitize_lookup_candidates(
        [
            {"lemma": "grande", "pos": "noun", "gloss": "duży banknot"},
            {"lemma": "camino", "pos": "noun", "gloss": "droga"},
        ],
        learning_lang="es",
    )
    assert [c["lemma"] for c in out] == ["el camino"]


def test_row_must_translate_the_word_the_model_read():
    from app.services.lookup_candidates import row_translates_its_word

    def ok(row, query="x"):
        return row_translates_its_word(row, query, learning_lang="es")

    assert ok({"word": "quiero", "lemma": "querer", "gloss": "chcieć"}, "quiero")

    assert not ok({"word": "rodzian", "lemma": "rozrodzian", "gloss": "rozrodziany"})
    assert not ok({"word": "kobieta", "lemma": "querido", "gloss": "kochany"})
    assert ok({"word": "kobieta", "lemma": "la mujer", "gloss": "kobieta"})
    assert ok({"word": "drogie", "lemma": "caro", "gloss": "drogi"})
    assert ok({"word": "droga", "lemma": "la droga", "gloss": "narkotyk"})
    assert ok({"word": "perro", "lemma": "el perro", "gloss": "pies"})
    assert ok({"lemma": "el camino", "gloss": "droga"})
    assert ok(
        {"word": "kara", "lemma": "la cara", "gloss": "twarz"},
        "cara",
    )


def test_a_farther_word_drops_when_a_closer_one_is_present():
    from app.services.lookup_candidates import drop_rows_past_one_change

    kept = drop_rows_past_one_change(
        [
            {"word": "drogi", "lemma": "caro", "pos": "adj", "gloss": "drogi"},
            {"word": "droga", "lemma": "el camino", "pos": "noun", "gloss": "droga"},
            {"word": "drogie", "lemma": "la droga", "pos": "noun", "gloss": "narkotyk"},
        ],
        "drogie",
        learning_lang="es",
    )
    assert [row["lemma"] for row in kept] == ["caro"]

    inflection = drop_rows_past_one_change(
        [{"word": "iść", "lemma": "ir", "pos": "verb", "gloss": "iść"}],
        "idę",
        learning_lang="es",
    )
    assert inflection[0]["lemma"] == "ir"
    verb_beside_neighbor = drop_rows_past_one_change(
        [
            {"word": "ser", "lemma": "ser", "pos": "verb", "gloss": "być"},
            {"word": "somos", "lemma": "la somos", "pos": "noun", "gloss": "suma"},
        ],
        "somos",
        learning_lang="es",
    )
    assert [row["lemma"] for row in verb_beside_neighbor] == ["ser", "la somos"]

    conjugated_label = drop_rows_past_one_change(
        [
            {"word": "somos", "lemma": "ser", "pos": "verb", "gloss": "być"},
            {"word": "somos", "lemma": "el somo", "pos": "noun", "gloss": "grzbiet"},
        ],
        "somos",
        learning_lang="es",
    )
    assert [row["lemma"] for row in conjugated_label] == ["ser", "el somo"]


def test_digits_fall_off_before_the_lookup_key():
    from app.services.lookup_candidates import letters_of_query, normalize_lookup_query

    assert letters_of_query("drogie3") == "drogie"
    assert letters_of_query("idę") == "idę"
    assert normalize_lookup_query("drogie3") == normalize_lookup_query("drogie")


def test_first_name_is_not_vocabulary():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "la Tania", "pos": "noun", "gloss": "Tania"},
            {"lemma": "barato", "pos": "adj", "gloss": "tani"},
        ],
        "tania",
        learning_lang="es",
        native_lang="pl",
    )
    assert [c["lemma"] for c in out] == ["barato"]


def test_two_labels_in_one_pos_take_the_first():
    from app.services.pos_normalize import normalize_pos_bucket

    assert normalize_pos_bucket("adjective/adverb") == "adj"
    assert normalize_pos_bucket("adjetivo/adverbio") == "adj"


def test_a_copied_spelling_is_not_a_finished_answer():
    from app.services.lookup_candidates import rows_are_spelling_echoes

    echo = [{"lemma": "la droga", "pos": "noun", "gloss": "droga"}]
    assert rows_are_spelling_echoes(echo, "droga", learning_lang="es")
    roads = echo + [{"lemma": "el camino", "pos": "noun", "gloss": "droga"}]
    assert not rows_are_spelling_echoes(roads, "droga", learning_lang="es")


def test_cognate_gloss_is_not_thrown_away():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "el problema", "pos": "noun", "gloss": "problem"},
            {"lemma": "la noche", "pos": "noun", "gloss": "noc"},
        ],
        "problema",
        learning_lang="es",
    )
    assert [c["lemma"] for c in out] == ["el problema", "la noche"]
    noche = drop_implausible_lookup_rows(
        [{"lemma": "noc", "pos": "noun", "gloss": "noche"}],
        "noche",
        learning_lang="es",
    )
    assert noche == []


def test_plural_drug_becomes_the_singular_citation():
    out = sanitize_lookup_candidates(
        [{"lemma": "las drogas", "pos": "noun", "gloss": "narkotyki"}],
        learning_lang="es",
    )
    assert out[0]["lemma"] == "la droga"


def test_spelling_echo_drops_when_a_real_translation_is_present():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "la droga", "pos": "noun", "gloss": "droga"},
            {"lemma": "el camino", "pos": "noun", "gloss": "droga"},
            {"lemma": "la carretera", "pos": "noun", "gloss": "droga"},
        ],
        "droga",
        learning_lang="es",
    )
    assert [c["lemma"] for c in out] == ["el camino", "la carretera"]


def test_shared_loanword_stays_when_it_is_the_only_row():
    out = drop_implausible_lookup_rows(
        [{"lemma": "el hotel", "pos": "noun", "gloss": "hotel"}],
        "hotel",
        learning_lang="es",
    )
    assert out[0]["lemma"] == "el hotel"


def test_l2_query_does_not_keep_a_polish_lemma():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "książka", "pos": "noun", "gloss": "libro"},
            {"lemma": "okulary", "pos": "noun", "gloss": "gafas"},
        ],
        "libros",
        learning_lang="es",
    )
    assert out[0]["lemma"] == "el libro"
    assert out[0]["gloss"] == "książka"
    glasses = drop_implausible_lookup_rows(
        [{"lemma": "okulary", "pos": "noun", "gloss": "gafas"}],
        "gafas",
        learning_lang="es",
    )
    assert glasses[0]["lemma"] == "las gafas"
    assert glasses[0]["gloss"] == "okulary"


def test_reversed_polish_lemma_is_turned_back_into_spanish():
    out = drop_implausible_lookup_rows(
        [
            {"lemma": "dużo", "pos": "adv", "gloss": "mucho"},
            {"lemma": "duży", "pos": "adj", "gloss": "mucho"},
        ],
        "mucho",
        learning_lang="es",
    )
    assert [(c["lemma"], c["pos"], c["gloss"]) for c in out] == [
        ("mucho", "adv", "dużo"),
    ]


def test_drop_query_stretched_into_a_different_word():
    rows = [
        {"lemma": "much", "pos": "noun", "gloss": "mucha"},
        {"lemma": "mucho", "pos": "adj", "gloss": "dużo"},
        {"lemma": "mucho", "pos": "adv", "gloss": "dużo"},
        {"lemma": "mucho", "pos": "pron", "gloss": "dużo"},
        {"lemma": "el oído", "pos": "noun", "gloss": "ucho"},
    ]
    out = drop_implausible_lookup_rows(rows, "much", learning_lang="es")
    assert [(c["lemma"], c["pos"]) for c in out] == [("mucho", "adv"), ("el oído", "noun")]


def test_adverb_gloss_is_not_left_on_an_adjective():
    rows = [
        {"lemma": "mucho", "pos": "adj", "gloss": "dużo"},
        {"lemma": "mucho", "pos": "adv", "gloss": "bardzo"},
        {"lemma": "mucha", "pos": "noun", "gloss": "mucha"},
    ]
    out = drop_implausible_lookup_rows(rows, "much", learning_lang="es")
    assert [(c["lemma"], c["pos"], c["gloss"]) for c in out] == [("mucho", "adv", "dużo")]


def test_drop_keeps_a_loanword_and_a_real_second_reading():
    hotel = drop_implausible_lookup_rows(
        [{"lemma": "el hotel", "pos": "noun", "gloss": "hotel"}],
        "hotel",
        learning_lang="es",
    )
    assert hotel[0]["lemma"] == "el hotel"
    pies = drop_implausible_lookup_rows(
        [
            {"lemma": "el perro", "pos": "noun", "gloss": "pies"},
            {"lemma": "el pie", "pos": "noun", "gloss": "stopa"},
        ],
        "pies",
        learning_lang="es",
    )
    assert [c["lemma"] for c in pies] == ["el perro", "el pie"]


def test_lookup_form_rules_plural_citation_and_gloss_paren():
    from app.ai.prompts.v1 import lookup_output_form_rules_text

    text = lookup_output_form_rules_text("pl", "es")
    assert "los cascos" in text
    assert "słuchawki (nauszne)" in text
    assert "książki" in text

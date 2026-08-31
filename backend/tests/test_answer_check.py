from app.services.answer_check import (
    check_answer,
    collect_acceptable_answers,
    format_lemma_with_article,
    max_allowed_typos,
    typo_tolerance_ok,
)


def test_exact_match():
    ok, expected, typo, synonym = check_answer("dog", ["dog"], "tolerate")
    assert ok is True
    assert expected is None
    assert typo is False
    assert synonym is False


def test_one_letter_substitution_accepted_as_typo():
    ok, expected, typo, synonym = check_answer("doc", ["dog"], "tolerate")
    assert ok is True
    assert expected == "dog"
    assert typo is True
    assert synonym is False


def test_two_letter_difference_rejected_on_short_word():
    ok, _, typo, synonym = check_answer("cat", ["dog"], "tolerate")
    assert ok is False
    assert typo is False
    assert synonym is False


def test_diacritic_only_typo():
    ok, _, typo, synonym = check_answer("cafe", ["café"], "tolerate")
    assert ok is True
    assert typo is True
    assert synonym is False


def test_single_char_not_fuzzy_matched():
    assert typo_tolerance_ok("a", "b") is False


def test_strict_mode_rejects_typo():
    ok, _, typo, synonym = check_answer("doc", ["dog"], "strict")
    assert ok is False
    assert typo is False
    assert synonym is False


def test_max_allowed_typos_short_word():
    assert max_allowed_typos(3) == 1


def test_max_allowed_typos_twelve_letters():
    assert max_allowed_typos(12) == 2


def test_twelve_letter_word_allows_two_typos():
    answer = "abcdefghijkl"
    typed = "xbcddefghijkl"
    ok, _, typo, synonym = check_answer(typed, [answer], "tolerate")
    assert ok is True
    assert typo is True
    assert synonym is False


def test_exact_synonym_is_not_typo():
    ok, expected, typo, synonym = check_answer("lograr", ["alcanzar", "lograr"], "tolerate")
    assert ok is True
    assert expected is None
    assert typo is False
    assert synonym is True


def test_omitted_noun_article_is_typo():
    ok, expected, typo, synonym = check_answer("casa", ["la casa"], "tolerate")
    assert ok is True
    assert expected == "la casa"
    assert typo is True
    assert synonym is False


def test_omitted_article_plus_missing_accent_is_typo():
    ok, expected, typo, synonym = check_answer("conclusion", ["la conclusión"], "tolerate")
    assert ok is True
    assert expected == "la conclusión"
    assert typo is True
    assert synonym is False


def test_extra_article_on_verb_is_error():
    ok, _, typo, synonym = check_answer("el trabajar", ["trabajar"], "tolerate")
    assert ok is False
    assert typo is False
    assert synonym is False


def test_synonym_with_article_is_exact_synonym():
    answers = collect_acceptable_answers(
        {
            "lemma": "la conclusión",
            "synonyms_l2": [
                {"lemma": "resultado", "article": "el", "gloss_l1": "wynik"},
            ],
        },
        "l1_to_l2",
    )
    assert "resultado" in answers
    assert "el resultado" in answers
    ok, expected, typo, synonym = check_answer("el resultado", answers, "tolerate")
    assert ok is True
    assert expected is None
    assert typo is False
    assert synonym is True


def test_synonym_typo_flags_both():
    ok, expected, typo, synonym = check_answer(
        "resultadp",
        ["la conclusión", "resultado", "el resultado"],
        "tolerate",
    )
    assert ok is True
    assert expected == "resultado"
    assert typo is True
    assert synonym is True


def test_format_lemma_with_article_elision():
    assert format_lemma_with_article("homme", "l'") == "l'homme"
    assert format_lemma_with_article("resultado", "el") == "el resultado"
    assert format_lemma_with_article("el resultado", "el") == "el resultado"

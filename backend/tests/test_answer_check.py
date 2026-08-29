from app.services.answer_check import check_answer, max_allowed_typos, typo_tolerance_ok


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

from app.services.tenses import normalize_tense_key, normalize_tense_keys


def test_polish_aliases_apply_only_for_polish():
    assert normalize_tense_key("present", "pl") == "czas_terazniejszy"
    assert normalize_tense_key("present", "ko") == "present"
    assert normalize_tense_key("present") == "present"


def test_spanish_aliases_do_not_rewrite_portuguese_futuro():
    assert normalize_tense_key("futuro", "es") == "futuro_simple"
    assert normalize_tense_key("futuro", "pt-br") == "futuro"
    assert normalize_tense_key("futuro", "pt-pt") == "futuro"


def test_diacritic_aliases_are_global():
    assert normalize_tense_key("czas_teraźniejszy", "ko") == "czas_terazniejszy"
    assert normalize_tense_keys(["present", "czas_przeszły"], "pl") == [
        "czas_terazniejszy",
        "czas_przeszly",
    ]

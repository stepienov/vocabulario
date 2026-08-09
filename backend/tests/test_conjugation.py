"""Tests for conjugation prompt helpers and post-LLM validation."""

from app.ai.conjugation import (
    conjugation_paradigm_rules,
    conjugation_rules_for_prompt,
    validate_conjugation,
)


def test_polish_prompt_forbids_placeholders_and_gender_present():
    prompt = conjugation_rules_for_prompt("robić", native="pl", learning="pl")
    assert "NEVER use placeholders" in prompt or 'no "—"' in prompt
    assert "ja_m" in prompt
    assert "czas_terazniejszy" in prompt
    assert "PERFECTIVE" in prompt.upper() or "perfective" in prompt.lower()


def test_polish_paradigm_rules_include_lemma():
    rules = conjugation_paradigm_rules("pl", "pojechać")
    assert "pojechać" in rules
    assert "czas_terazniejszy" in rules


def test_validate_drops_all_placeholder_tense():
    raw = {
        "tenses": {
            "czas_terazniejszy": {
                "ja_m": "—",
                "ja_f": "—",
                "ty_m": "—",
            }
        },
        "non_finite": {},
    }
    result = validate_conjugation(raw, "pl")
    assert result == {}


def test_validate_drops_polish_present_with_gender_grid():
    raw = {
        "tenses": {
            "czas_terazniejszy": {
                "ja_m": "robię",
                "ja_f": "robię",
                "ty_m": "robisz",
                "ty_f": "robisz",
            },
            "czas_przeszly": {
                "ja_m": "robiłem",
                "ja_f": "robiłam",
            },
        },
        "non_finite": {"bezokolicznik": "robić"},
    }
    result = validate_conjugation(raw, "pl")
    assert "czas_terazniejszy" not in result.get("tenses", {})
    assert result["tenses"]["czas_przeszly"]["ja_m"] == "robiłem"
    assert result["non_finite"]["bezokolicznik"] == "robić"


def test_validate_keeps_valid_polish_present():
    raw = {
        "tenses": {
            "czas_terazniejszy": {
                "ja": "robię",
                "ty": "robisz",
                "on": "robi",
                "ona": "robi",
                "ono": "robi",
                "my": "robimy",
                "wy": "robicie",
                "oni": "robią",
                "one": "robią",
            }
        },
        "non_finite": {},
    }
    result = validate_conjugation(raw, "pl")
    assert result["tenses"]["czas_terazniejszy"]["ja"] == "robię"

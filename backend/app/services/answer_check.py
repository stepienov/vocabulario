import re
import unicodedata
from difflib import SequenceMatcher


def normalize_answer(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return unicodedata.normalize("NFC", text)


def strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def levenshtein_one_char_ok(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def check_answer(
    user_answer: str,
    correct_answers: list[str],
    tolerance: str = "tolerate",
) -> tuple[bool, str | None, bool]:
    """Returns (correct, canonical_or_expected, accepted_as_typo). Always high tolerance."""
    normalized_user = normalize_answer(user_answer)
    normalized_correct = [normalize_answer(c) for c in correct_answers if c]

    for correct in normalized_correct:
        if normalized_user == correct:
            return True, None, False

    # Always tolerate: diacritics, minor typos, spacing/case already normalized
    for correct in normalized_correct:
        if strip_diacritics(normalized_user) == strip_diacritics(correct):
            return True, correct, True
        if levenshtein_one_char_ok(normalized_user, correct):
            return True, correct, True

    return False, normalized_correct[0] if normalized_correct else None, False


def collect_acceptable_answers(content: dict, direction: str) -> list[str]:
    answers: list[str] = []
    if direction == "l2_to_l1":
        for meaning in content.get("meanings", []):
            if gloss := meaning.get("gloss_l1"):
                answers.append(gloss)
            answers.extend(meaning.get("synonyms_l1", []))
    else:
        if lemma := content.get("lemma"):
            answers.append(lemma)
        for item in content.get("synonyms_l2", []):
            if isinstance(item, dict) and item.get("lemma"):
                answers.append(item["lemma"])
            elif isinstance(item, str) and item.strip():
                answers.append(item)
    return list(dict.fromkeys(a for a in answers if a))

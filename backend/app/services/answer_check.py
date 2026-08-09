import math
import re
import unicodedata


def normalize_answer(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return unicodedata.normalize("NFC", text)


def strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def levenshtein_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        return levenshtein_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            ins = curr[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]


def max_allowed_typos(word_len: int) -> int:
    """Wider of: always 1 typo, or ~15% of length (85% similarity)."""
    if word_len < 2:
        return 0
    by_ratio = math.ceil(word_len * 0.15)
    return max(1, by_ratio)


def similarity_ratio(a: str, b: str) -> float:
    n = max(len(a), len(b))
    if n == 0:
        return 1.0
    return 1.0 - levenshtein_distance(a, b) / n


def typo_tolerance_ok(a: str, b: str) -> bool:
    """Accept if ≤1 typo OR similarity ≥85% — whichever is more lenient."""
    if a == b:
        return True
    if not a or not b:
        return False
    if min(len(a), len(b)) < 2:
        return False
    distance = levenshtein_distance(a, b)
    n = max(len(a), len(b))
    if distance <= 1:
        return True
    if similarity_ratio(a, b) >= 0.85:
        return True
    return distance <= max_allowed_typos(n)


def check_answer(
    user_answer: str,
    correct_answers: list[str],
    tolerance: str = "tolerate",
) -> tuple[bool, str | None, bool]:
    """Returns (correct, canonical_or_expected, accepted_as_typo)."""
    normalized_user = normalize_answer(user_answer)
    normalized_correct = [normalize_answer(c) for c in correct_answers if c]

    for correct in normalized_correct:
        if normalized_user == correct:
            return True, None, False

    if tolerance == "strict":
        return False, normalized_correct[0] if normalized_correct else None, False

    for correct in normalized_correct:
        if strip_diacritics(normalized_user) == strip_diacritics(correct):
            return True, correct, True
        if typo_tolerance_ok(normalized_user, correct):
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

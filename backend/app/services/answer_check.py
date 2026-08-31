import math
import re
import unicodedata

# Mirror Android LemmaKeys / formatLemmaWithArticle — leading citation article only.
_ANSWER_ARTICLES = frozenset(
    {
        "el",
        "la",
        "los",
        "las",
        "le",
        "les",
        "un",
        "une",
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "the",
        "a",
        "an",
        "il",
        "lo",
        "i",
        "gli",
        "o",
        "os",
        "as",
    }
)
_AR_DEFINITE = "ال"


def normalize_answer(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return unicodedata.normalize("NFC", text)


def strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def stem_without_article(text: str) -> str:
    """Leading el/la/l'/ال… only. Same rules as Android lemmaKey."""
    lower = (text or "").strip().lower()
    if not lower:
        return ""
    parts = lower.split()
    rest = " ".join(parts[1:]) if len(parts) > 1 and parts[0] in _ANSWER_ARTICLES else lower
    if rest.startswith("l'"):
        rest = rest[2:]
    elif rest.startswith("l’"):
        rest = rest[2:]
    elif rest.startswith(_AR_DEFINITE):
        rest = rest[len(_AR_DEFINITE) :]
    return rest.strip()


def format_lemma_with_article(lemma: str, article: str | None) -> str:
    """Join citation article + lemma. Same rules as Android formatLemmaWithArticle."""
    stem = (lemma or "").strip()
    art = (article or "").strip()
    if not stem:
        return art
    if not art:
        return stem
    stem_lower = stem.lower()
    art_lower = art.lower()
    if stem_lower == art_lower:
        return stem
    if (
        stem_lower.startswith(art_lower)
        and len(art) < len(stem)
        and not stem[len(art)].isalpha()
    ):
        return stem
    if art == _AR_DEFINITE and stem.startswith(_AR_DEFINITE):
        return stem
    if art.endswith("'") or art.endswith("’") or art == _AR_DEFINITE:
        return art + stem
    return f"{art} {stem}"


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


def _article_only_typo(user: str, correct: str) -> bool:
    """Expected has a citation article; stems match (diacritics ignored); forms differ."""
    corr_stem = stem_without_article(correct)
    if not corr_stem or corr_stem == correct:
        return False
    user_stem = stem_without_article(user) or user
    if not user_stem:
        return False
    return strip_diacritics(user_stem) == strip_diacritics(corr_stem)


def check_answer(
    user_answer: str,
    correct_answers: list[str],
    tolerance: str = "tolerate",
) -> tuple[bool, str | None, bool, bool]:
    """Returns (correct, canonical_or_expected, accepted_as_typo, accepted_as_synonym)."""
    normalized_user = normalize_answer(user_answer)
    normalized_correct = [normalize_answer(c) for c in correct_answers if c]

    for index, correct in enumerate(normalized_correct):
        if normalized_user == correct:
            return True, None, False, index > 0

    if tolerance == "strict":
        return False, normalized_correct[0] if normalized_correct else None, False, False

    for index, correct in enumerate(normalized_correct):
        if _article_only_typo(normalized_user, correct):
            return True, correct, True, index > 0

    for index, correct in enumerate(normalized_correct):
        if strip_diacritics(normalized_user) == strip_diacritics(correct):
            return True, correct, True, index > 0
        if typo_tolerance_ok(normalized_user, correct):
            return True, correct, True, index > 0

    return False, normalized_correct[0] if normalized_correct else None, False, False


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
                lemma = item["lemma"]
                answers.append(lemma)
                with_art = format_lemma_with_article(lemma, item.get("article"))
                if with_art != lemma:
                    answers.append(with_art)
            elif isinstance(item, str) and item.strip():
                answers.append(item)
    return list(dict.fromkeys(a for a in answers if a))

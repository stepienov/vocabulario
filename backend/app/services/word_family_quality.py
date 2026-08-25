"""Filtry jakości rodziny wyrazów — bez DB, bez podobieństwa zapisu.

Rodzina = derywacja sufiksalna / konwersja. Nie fleksja, nie negacja prefiksalna,
nie prefiks zmieniający znaczenie. Look-alike (libro/libre) tu nie łapiemy
heurystyką zapisu — to robi merge (detach) + prompt.
"""

from __future__ import annotations

from app.core.lemma_keys import canonical_lemma
from app.services.pos_normalize import normalize_pos_bucket

MAX_FAMILY_MEMBERS = 16

POS_TIEBREAK = {"verb": 0, "noun": 1, "adj": 2, "adv": 3}

# Dłuższe prefiksy pierwsze.
_NEGATIVE_PREFIXES: dict[str, tuple[str, ...]] = {
    "es": ("des", "in", "im", "ir", "il"),
    "it": ("dis", "in", "im", "ir", "il"),
    "fr": ("des", "dé", "non", "in", "im", "ir", "il"),
    "pt-br": ("des", "in", "im", "ir"),
    "pt-pt": ("des", "in", "im", "ir"),
    "en": ("non", "dis", "un", "in", "im", "ir", "il"),
    "de": ("un", "in"),
    "pl": ("nie",),
    "ru": ("не",),
    "tr": ("anti",),
}

_LEXICAL_PREFIXES: dict[str, tuple[str, ...]] = {
    "es": ("sobre", "entre", "re", "pre", "sub"),
    "it": ("sopra", "re", "pre", "sub"),
    "fr": ("re", "pré", "sur", "sous"),
    "pt-br": ("sobre", "re", "pre", "sub"),
    "pt-pt": ("sobre", "re", "pre", "sub"),
    "en": ("over", "under", "out", "pre", "re"),
    "de": ("aus", "ein", "auf", "unter", "über", "vor", "nach", "mit", "ab", "an", "zu", "um"),
    "pl": ("prze", "roz", "nad", "pod", "od", "do", "wy", "za", "na", "po", "u"),
    "ru": ("пере", "раз", "про", "при", "под", "над", "от", "за", "вы", "по", "на", "у"),
}

# Końcówki nieosobowe — odrzucamy tylko gdy kandydat MA TĘ SAMĄ POS co hasło (czasownik).
_VERB_INFLECTION_SUFFIXES: dict[str, tuple[str, ...]] = {
    "es": ("ándome", "iéndome", "ando", "iendo", "ándose", "iéndose"),
    "it": ("andomi", "endomi", "ando", "endo"),
    "fr": ("ant",),
    "pt-br": ("ando", "endo", "indo"),
    "pt-pt": ("ando", "endo", "indo"),
    "en": ("ing",),
    "de": ("end",),
    "pl": ("ąc",),
    "ru": ("ая", "яя", "уя"),
}


def member_key(lemma: str | None, pos: str | None) -> tuple[str, str] | None:
    stem = canonical_lemma(lemma)
    bucket = normalize_pos_bucket(pos)
    if not stem or bucket == "unknown":
        return None
    return stem, bucket


def is_same_member(
    lemma_a: str | None, pos_a: str | None, lemma_b: str | None, pos_b: str | None
) -> bool:
    ka, kb = member_key(lemma_a, pos_a), member_key(lemma_b, pos_b)
    return ka is not None and ka == kb


def _prefixes_for(table: dict[str, tuple[str, ...]], lang: str) -> tuple[str, ...]:
    return table.get((lang or "").strip().lower(), ())


def _strip_prefix(lemma: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in sorted(prefixes, key=len, reverse=True):
        if lemma.startswith(prefix) and len(lemma) - len(prefix) >= 3:
            return lemma[len(prefix) :]
    return None


def is_negative_prefix_pair(left: str | None, right: str | None, lang: str) -> bool:
    a, b = canonical_lemma(left), canonical_lemma(right)
    if not a or not b or a == b:
        return False
    prefixes = _prefixes_for(_NEGATIVE_PREFIXES, lang)
    rest_a = _strip_prefix(a, prefixes)
    rest_b = _strip_prefix(b, prefixes)
    return rest_a == b or rest_b == a


def is_lexical_prefix_pair(left: str | None, right: str | None, lang: str) -> bool:
    a, b = canonical_lemma(left), canonical_lemma(right)
    if not a or not b or a == b:
        return False
    prefixes = _prefixes_for(_LEXICAL_PREFIXES, lang)
    rest_a = _strip_prefix(a, prefixes)
    rest_b = _strip_prefix(b, prefixes)
    return rest_a == b or rest_b == a


def is_verb_inflection_of(candidate: str | None, head: str | None, lang: str) -> bool:
    """True gdy kandydat wygląda na nieosobową formę TEGO hasła (nie derywat)."""
    c, h = canonical_lemma(candidate), canonical_lemma(head)
    if not c or not h or c == h:
        return False
    suffixes = _prefixes_for(_VERB_INFLECTION_SUFFIXES, lang)
    for suffix in sorted(suffixes, key=len, reverse=True):
        if c.endswith(suffix) and c[: -len(suffix)] == h:
            return True
    return False


def belongs_in_family(
    candidate_lemma: str | None,
    candidate_pos: str | None,
    members: list[tuple[str | None, str | None]],
    learning_lang: str,
) -> bool:
    key = member_key(candidate_lemma, candidate_pos)
    if key is None:
        return False
    cand_pos = key[1]
    for lemma, pos in members:
        other = member_key(lemma, pos)
        if other is None:
            continue
        if key == other:
            return True
        if is_negative_prefix_pair(candidate_lemma, lemma, learning_lang):
            return False
        if is_lexical_prefix_pair(candidate_lemma, lemma, learning_lang):
            return False
        if cand_pos == "verb" and other[1] == "verb" and is_verb_inflection_of(
            candidate_lemma, lemma, learning_lang
        ):
            return False
    return True


def _lemma_seen_key(item: dict) -> str:
    return (item.get("lemma") or "").casefold().strip()


def merge_related_lists(base: list[dict], extra: list[dict]) -> list[dict]:
    seen = {_lemma_seen_key(item) for item in base}
    out = list(base)
    for item in extra:
        key = _lemma_seen_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def filter_word_family(
    head_lemma: str,
    head_pos: str | None,
    family: list[dict],
    antonyms: list[dict],
    learning_lang: str,
) -> tuple[list[dict], list[dict]]:
    """Odrzuca negacje/fleksję/prefiksy; negacje tej samej POS → antonimy."""
    extra_antonyms: list[dict] = []
    kept: list[dict] = []
    head_pos_n = normalize_pos_bucket(head_pos)
    for item in family:
        lemma = item.get("lemma")
        pos = item.get("pos")
        if is_same_member(lemma, pos, head_lemma, head_pos):
            continue
        if canonical_lemma(lemma) == canonical_lemma(head_lemma) and (
            not pos or normalize_pos_bucket(pos) == "unknown"
        ):
            continue
        if is_negative_prefix_pair(lemma, head_lemma, learning_lang):
            cand_pos = normalize_pos_bucket(pos)
            if cand_pos == head_pos_n and cand_pos != "unknown":
                extra_antonyms.append(item)
            continue
        if is_lexical_prefix_pair(lemma, head_lemma, learning_lang):
            continue
        if (
            normalize_pos_bucket(pos) == "verb"
            and head_pos_n == "verb"
            and is_verb_inflection_of(lemma, head_lemma, learning_lang)
        ):
            continue
        kept.append(item)
    return kept[:MAX_FAMILY_MEMBERS], merge_related_lists(antonyms, extra_antonyms)


def related_item_from_member(
    *,
    lemma: str,
    pos: str,
    article: str | None,
    gloss_l1: str | None,
) -> dict:
    item: dict = {
        "lemma": lemma,
        "pos": pos,
        "gloss_l1": (gloss_l1 or "").strip() or "?",
        "article": article,
    }
    return item


def sort_family_items(items: list[dict]) -> list[dict]:
    def key(item: dict) -> tuple:
        pos = normalize_pos_bucket(item.get("pos"))
        return (POS_TIEBREAK.get(pos, 9), (item.get("lemma") or "").casefold())

    return sorted(items, key=key)

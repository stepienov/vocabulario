from difflib import SequenceMatcher
import re
import unicodedata

from app.lsp.lang_utils import articles_for
from app.services.pos_normalize import (
    canonicalize_lookup_candidate,
    lemma_stem,
    lookup_dedup_key,
    merge_lookup_variants,
    normalize_pos_bucket,
)


def _normalize_lemma(lemma: str) -> str:
    return " ".join(lemma.lower().split())


def _article_set(learning_lang: str) -> set[str]:
    return {a.lower() for a in articles_for(learning_lang)}


def dedupe_lookup_candidates(
    candidates: list[dict],
    *,
    learning_lang: str = "en",
    limit: int | None = None,
) -> list[dict]:
    """Collapse duplicates: same headword + canonical pos; prefer article lemma."""
    order: list[tuple[str, str]] = []
    by_key: dict[tuple[str, str], dict] = {}
    for item in candidates:
        item = canonicalize_lookup_candidate(item, learning_lang=learning_lang)
        lemma = (item.get("lemma") or "").strip()
        if not lemma:
            continue
        key = lookup_dedup_key(lemma, item.get("pos"), learning_lang=learning_lang)
        if key not in by_key:
            order.append(key)
            by_key[key] = item
        else:
            by_key[key] = merge_lookup_variants(
                by_key[key], item, learning_lang=learning_lang
            )
    out = [by_key[k] for k in order]
    return out[:limit] if limit is not None else out


# Punctuation that users insert/omit by accident and that never changes word identity
# for fuzzy comparison (commas, periods, quotes, brackets, apostrophes, …).
_STRAY_PUNCT_RE = re.compile(r"""[.,;:!?¿¡"'`´“”‘’«»()\[\]{}]""")


def _strip_stray_punct(text: str) -> str:
    return _STRAY_PUNCT_RE.sub("", text).strip()


def _norm_token(text: str) -> str:
    text = unicodedata.normalize("NFC", (text or "").strip().casefold())
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_diacritics(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# Letters that carry a stroke/ligature and are NOT decomposed by NFD, yet users
# routinely type the plain latin base instead (Polish ł→l is extremely common).
_STROKE_MAP = str.maketrans(
    {
        "ł": "l",
        "ø": "o",
        "đ": "d",
        "ð": "d",
        "ħ": "h",
        "ŧ": "t",
        "ı": "i",
        "ĸ": "k",
        "œ": "oe",
        "æ": "ae",
    }
)


def _fold(text: str) -> str:
    """Comparison form: lowercased, base latin letters, no stray punctuation.

    Neutralises the three ways users diverge from canonical spelling: missing/wrong
    diacritics, stroke letters typed as plain latin (łódź→lodz), and stray punctuation.
    """
    t = _strip_stray_punct(_norm_token(text)).translate(_STROKE_MAP)
    return _strip_diacritics(t)


def edit_distance(a: str, b: str) -> int:
    """Damerau (optimal string alignment) distance — counts a letter swap as 1."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    la, lb = len(a), len(b)
    prev2: list[int] = []
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cb = b[j - 1]
            cost = 0 if ca == cb else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            if (
                i > 1
                and j > 1
                and ca == b[j - 2]
                and a[i - 2] == cb
            ):
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[lb]


def token_similarity(a: str, b: str) -> float:
    """1.0 exact / diacritic-only; high for small typos, transpositions, stray punct."""
    aa = _strip_stray_punct(_norm_token(a))
    bb = _strip_stray_punct(_norm_token(b))
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    fa, fb = _fold(a), _fold(b)
    # Missing/extra diacritics, stroke letters or stray punctuation → same word.
    if fa and fa == fb:
        return 1.0
    if abs(len(fa) - len(fb)) > 3:
        return 0.0
    # Compare on folded forms so accents/strokes never inflate the distance.
    dist = edit_distance(fa, fb)
    if dist == 0:
        return 1.0
    if dist > 2:
        return SequenceMatcher(None, fa, fb).ratio() * 0.55
    # length-aware: doem/dom=1, przyjacel/przyjaciel=1, houes/house=2
    max_len = max(len(fa), len(fb))
    base = 1.0 - (dist / max(max_len, 1))
    ratio = SequenceMatcher(None, fa, fb).ratio()
    sim = max(base, ratio)
    # A single edit (incl. a transposition) is a strong typo signal even on short
    # words, where the length-aware base would otherwise under-score it (teh→the).
    if dist == 1:
        sim = max(sim, 0.82)
    return sim


def gloss_query_score(gloss: str, query: str) -> float:
    """Best similarity between query and any gloss headword token."""
    q = _strip_stray_punct(_norm_token(query))
    if not q:
        return 0.0
    g = _norm_token(gloss)
    if not g:
        return 0.0
    if q in g:
        return 1.0
    parts = re.split(r"[,;/|]| - | — ", g)
    tokens: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        tokens.append(part)
        tokens.extend(t for t in re.split(r"\s+", part) if len(t) >= 2)
    if not tokens:
        tokens = [g]
    best = 0.0
    for t in tokens:
        if is_diacritic_only_variant(t, q):
            best = max(best, 1.0)
        else:
            best = max(best, token_similarity(q, t))
    return best


def is_diacritic_only_variant(a: str, b: str) -> bool:
    """Same word up to diacritics and stray punctuation (książka. ≈ ksiazka)."""
    fa, fb = _fold(a), _fold(b)
    if not fa or not fb:
        return False
    return fa == fb


def primary_gloss_token(gloss: str) -> str:
    g = _norm_token(gloss)
    if not g:
        return ""
    return re.split(r"[,;/|]| - | — ", g)[0].strip()


def gloss_tokens(gloss: str) -> list[str]:
    g = _norm_token(gloss)
    if not g:
        return []
    tokens: list[str] = []
    for part in re.split(r"[,;/|]| - | — ", g):
        part = part.strip()
        if not part:
            continue
        tokens.append(part)
        tokens.extend(t for t in re.split(r"\s+", part) if len(t) >= 2)
    return tokens or [g]


def gloss_identifies_query(gloss: str, query: str) -> bool:
    """Gloss names the same L1 word as the query (incl. missing diacritics/punct)."""
    q = _fold(query)
    if not q:
        return False
    for token in gloss_tokens(gloss):
        if _fold(token) == q:
            return True
    return False


def _lemma_query_term(lemma: str, learning_lang: str | None = None) -> str:
    """Headword used when comparing lemma to user query (article stripped when known)."""
    raw = _norm_token(lemma)
    if not raw:
        return ""
    if learning_lang:
        stem = lemma_stem(lemma, learning_lang)
        if stem:
            return stem
    return raw


def lemma_matches_query(
    lemma: str, query: str, *, learning_lang: str | None = None
) -> bool:
    """Exact or diacritic/punct-insensitive lemma match (brac ≈ brać; libro ≈ el libro)."""
    a = _lemma_query_term(lemma, learning_lang)
    b = _norm_token(query)
    if not a or not b:
        return False
    if a == b:
        return True
    return _fold(a) == _fold(b)


def lemma_relates_to_query(
    lemma: str, query: str, *, learning_lang: str | None = None
) -> bool:
    term = _lemma_query_term(lemma, learning_lang)
    q = _norm_token(query)
    if not term or not q:
        return False
    if lemma_matches_query(term, q, learning_lang=learning_lang):
        return True
    if is_diacritic_only_variant(term, q):
        return True
    return token_similarity(term, q) >= 0.85


def drop_query_echo_lemmas(candidates: list[dict], query: str) -> list[dict]:
    """Drop L1 typed as fake L2 lemma when real L2 translations exist.

    Keep genuine L2 headwords that equal the query (e.g. PL 'brat' when query
    is 'brat'). Only drop when lemma≈query AND gloss also repeats the query
    (classic echo: EN 'house' → lemma 'house', gloss 'house music').
    """
    q = _norm_token(query)
    if not q:
        return candidates
    has_other = any(
        not lemma_matches_query(c.get("lemma") or "", q) for c in candidates
    )
    if not has_other:
        return candidates
    kept: list[dict] = []
    for c in candidates:
        lemma = c.get("lemma") or ""
        if lemma_matches_query(lemma, q) and gloss_query_score(c.get("gloss") or "", q) >= 0.72:
            continue
        kept.append(c)
    return kept if kept else candidates


def rank_lookup_candidates(
    candidates: list[dict],
    query: str,
    *,
    learning_lang: str | None = None,
) -> list[dict]:
    """Stable rank: closest L2 headword first, then L1 gloss match, then model order."""
    q = _norm_token(query)
    if not q or not candidates:
        return candidates

    def lemma_component(lemma: str, gloss: str) -> float:
        term = _lemma_query_term(lemma, learning_lang)
        if lemma_matches_query(term, q, learning_lang=learning_lang):
            return 1.0
        folded_q, folded_t = _fold(q), _fold(term)
        near_l2 = (
            0.85
            if term
            and not lemma_matches_query(term, q, learning_lang=learning_lang)
            and abs(len(folded_q) - len(folded_t)) <= 1
            and edit_distance(folded_q, folded_t) == 1
            else 0.0
        )
        if near_l2 > 0:
            return near_l2
        stem_sim = token_similarity(term, q) if term else 0.0
        # L1 query: ignore weak accidental L2 string similarity (morcilla vs ksiazka).
        if gloss_identifies_query(gloss, q):
            return 0.0
        if stem_sim >= 0.72:
            return stem_sim
        return 0.0

    def sort_key(item: tuple[int, dict]) -> tuple:
        idx, c = item
        lemma = c.get("lemma") or ""
        gloss = c.get("gloss") or ""
        gloss_hit = gloss_query_score(gloss, q)
        if gloss_identifies_query(gloss, q):
            effective_gloss = 1.0
        elif gloss_hit >= 0.72:
            # Fuzzy gloss neighbor of a different word (kiszka for ksiazka).
            effective_gloss = 0.71
        else:
            effective_gloss = gloss_hit
        return (-lemma_component(lemma, gloss), -effective_gloss, idx)

    indexed = list(enumerate(candidates))
    indexed.sort(key=sort_key)
    return [c for _, c in indexed]


def demote_spurious_l2_near_matches(candidates: list[dict], query: str) -> list[dict]:
    """Drop L2 'typo corrections' that are edit-neighbors of an L1 typo query.

    Example: query 'doem' → lemma 'don' (bad); keep 'casa' with gloss 'dom'.
    Never demote diacritic-only near-matches (brac → brać).
    """
    q = _norm_token(query)
    if not q or not candidates:
        return candidates
    if any(lemma_matches_query(c.get("lemma") or "", q) for c in candidates):
        return candidates

    kept: list[dict] = []
    for c in candidates:
        lemma = _norm_token(c.get("lemma") or "")
        gloss_score = gloss_query_score(c.get("gloss") or "", q)
        # Compare without diacritics so brać/brac is never treated as spurious.
        lemma_cmp = _strip_diacritics(lemma)
        q_cmp = _strip_diacritics(q)
        if lemma_cmp == q_cmp:
            kept.append(c)
            continue
        lemma_dist = edit_distance(q_cmp, lemma_cmp) if lemma else 99
        # Same-script near lemma + weak gloss → almost certainly false L2 typo hit.
        if lemma_dist <= 2 and gloss_score < 0.72:
            continue
        kept.append(c)
    return kept if kept else candidates


def prefer_fuzzy_gloss_match(
    candidates: list[dict], query: str, *, learning_lang: str | None = None
) -> list[dict]:
    """Rank by fuzzy similarity of gloss headwords to the query (L1 typos)."""
    return rank_lookup_candidates(candidates, query, learning_lang=learning_lang)


def prefer_exact_query_lemmas(
    candidates: list[dict], query: str, *, learning_lang: str | None = None
) -> list[dict]:
    """Compat wrapper — full ranking lives in rank_lookup_candidates."""
    return rank_lookup_candidates(candidates, query, learning_lang=learning_lang)


def prefer_gloss_match(candidates: list[dict], query: str) -> list[dict]:
    return rank_lookup_candidates(candidates, query)


def best_gloss_score(candidates: list[dict], query: str) -> float:
    if not candidates:
        return 0.0
    return max(gloss_query_score(c.get("gloss") or "", query) for c in candidates)


def candidate_is_confident(
    candidate: dict, query: str, *, learning_lang: str | None = None
) -> bool:
    """A candidate we trust as the (a) intended word: exact/diacritic lemma or gloss."""
    lemma = candidate.get("lemma") or ""
    gloss = candidate.get("gloss") or ""
    return lemma_matches_query(
        lemma, query, learning_lang=learning_lang
    ) or gloss_identifies_query(gloss, query)


def cached_lookup_covers_query(
    candidates: list[dict],
    query: str,
    *,
    learning_lang: str | None = None,
) -> bool:
    """Skip AI only when this query already has 2+ distinct POS in cache.

    One cached reading (play/verb) must not hide the other (play/noun).
    """
    if not has_confident_match(candidates, query, learning_lang=learning_lang):
        return False
    buckets: set[str] = set()
    for c in candidates:
        lemma = c.get("lemma") or ""
        if not lemma_matches_query(lemma, query, learning_lang=learning_lang):
            continue
        bucket = normalize_pos_bucket(c.get("pos"))
        if bucket != "unknown":
            buckets.add(bucket)
    return len(buckets) >= 2


def has_confident_match(
    candidates: list[dict], query: str, *, learning_lang: str | None = None
) -> bool:
    """True if ANY candidate is an exact / diacritic-completed reading of the query.

    Used to decide whether we still need the extra L1-typo recovery pass. It looks at
    the whole list (not just the top) so we never skip recovery just because one weak
    guess happened to sort first.
    """
    q = _fold(query)
    if not q or not candidates:
        return False
    return any(
        candidate_is_confident(c, query, learning_lang=learning_lang)
        for c in candidates
    )


def looks_like_spurious_l2_top(candidates: list[dict], query: str) -> bool:
    """Legacy gate: top result is a fuzzy guess of a DIFFERENT word than intended.

    Kept for compatibility; orchestration now prefers has_confident_match + union.
    """
    if not candidates:
        return True
    q = _norm_token(query)
    top = candidates[0]
    lemma = top.get("lemma") or ""
    gloss = top.get("gloss") or ""
    if lemma_matches_query(lemma, q):
        return False
    if gloss_identifies_query(gloss, q):
        return False
    gloss_score = gloss_query_score(gloss, q)
    # Fuzzy gloss neighbor of a different word (kiszka for ksiazka) with unrelated L2.
    if gloss_score >= 0.72 and not lemma_relates_to_query(lemma, q):
        return True
    lemma_n = _norm_token(lemma)
    if lemma_n and edit_distance(_fold(q), _fold(lemma_n)) <= 2:
        return True
    return gloss_score < 0.55


def merge_candidates(
    *groups: list[dict],
    limit: int = 8,
    learning_lang: str = "en",
) -> list[dict]:
    combined: list[dict] = []
    for group in groups:
        combined.extend(group)
    return dedupe_lookup_candidates(combined, learning_lang=learning_lang, limit=limit)


def sanitize_lookup_candidates(
    candidates: list[dict],
    *,
    learning_lang: str = "en",
) -> list[dict]:
    cleaned: list[dict] = []
    articles = _article_set(learning_lang)
    multi_pos = {"phrase", "construction", "particle", "expression", "idiom", "collocation"}

    for item in candidates:
        if not isinstance(item, dict):
            continue
        lemma = (item.get("lemma") or "").strip()
        gloss = (item.get("gloss") or "").strip()
        if not lemma or not gloss:
            continue

        item = canonicalize_lookup_candidate(item, learning_lang=learning_lang)
        lemma = (item.get("lemma") or "").strip()
        bucket = normalize_pos_bucket(item.get("pos"))
        words = lemma.split()
        n = len(words)

        if bucket == "verb":
            if n < 1 or n > 3:
                continue
        elif bucket == "noun":
            if n == 1:
                pass  # bare allowed; canonicalize may add article when gender known
            elif n == 2 and words[0].lower().rstrip("'") in articles:
                pass
            else:
                continue
        elif bucket in multi_pos:
            if n < 1 or n > 6:
                continue
        elif bucket == "unknown":
            if n == 1:
                pass
            elif n == 2 and words[0].lower().rstrip("'") in articles:
                pass
            elif 2 <= n <= 4:
                pass
            else:
                continue
        else:
            if n < 1 or n > 4:
                continue

        if n > 6:
            continue
        cleaned.append(item)

    return dedupe_lookup_candidates(cleaned, learning_lang=learning_lang, limit=8)

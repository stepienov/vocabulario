from difflib import SequenceMatcher
import re
import unicodedata

from app.lsp.lang_utils import articles_for
from app.services.lookup_pos import refine_lookup_pos
from app.services.pos_normalize import (
    canonicalize_lookup_candidate,
    lemma_stem,
    lookup_dedup_key,
    merge_lookup_variants,
    normalize_pos_bucket,
)

# Soft cap for a stored lookup list. Ranking never drops extras below this.
LOOKUP_CACHE_LIMIT = 16
LOOKUP_CATEGORY_DRAFT_LIMIT = 8
LOOKUP_CATEGORY_LIMIT = 24


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
    """Collapse a real duplicate: same word, part of speech, and translation.

    A copy without an article drops when the same translation already has one.
    A different translation of the same word stays.
    """
    order: list[tuple[str, str, str]] = []
    by_key: dict[tuple[str, str, str], dict] = {}
    for item in candidates:
        item = canonicalize_lookup_candidate(item, learning_lang=learning_lang)
        lemma = (item.get("lemma") or "").strip()
        if not lemma:
            continue
        key = lookup_dedup_key(
            lemma, item.get("pos"), learning_lang=learning_lang, gloss=item.get("gloss")
        )
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


def letters_of_query(text: str) -> str:
    """Drop digits and symbols before a lookup. Letters of any script stay."""
    kept = [
        ch
        for ch in (text or "")
        if ch.isspace() or ch in "-'" or unicodedata.category(ch).startswith("L")
    ]
    return re.sub(r"\s+", " ", "".join(kept)).strip()


def normalize_lookup_query(text: str) -> str:
    """Cache key for a typed lookup: folded query, fallback to trimmed casefold."""
    folded = _fold(letters_of_query(text))
    if folded:
        return folded[:200]
    return _norm_token(text)[:200]


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
        # Exact lemma or exact gloss stays above every near-miss, in model order.
        exact = lemma_matches_query(
            lemma, q, learning_lang=learning_lang
        ) or gloss_identifies_query(gloss, q)
        gloss_hit = gloss_query_score(gloss, q)
        if gloss_identifies_query(gloss, q):
            effective_gloss = 1.0
        elif gloss_hit >= 0.72:
            # Fuzzy gloss neighbor of a different word (kiszka for ksiazka).
            effective_gloss = 0.71
        else:
            effective_gloss = gloss_hit
        return (
            0 if exact else 1,
            -lemma_component(lemma, gloss),
            -effective_gloss,
            idx,
        )

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
    """Whether a lemma list already has 2+ distinct POS for this query.

    Kept as a helper/test contract. Interactive lookup no longer uses this to skip
    OpenAI — query cache (`lookup_query_cache.ai_complete`) owns that decision.
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


def rank_category_candidates(
    candidates: list[dict],
    query: str,
    *,
    learning_lang: str = "en",
) -> list[dict]:
    """Seed (the typed word) first, then keep the model's theme order."""
    cleaned = sanitize_lookup_candidates(
        candidates, learning_lang=learning_lang, limit=None
    )
    seed: list[dict] = []
    rest: list[dict] = []
    for item in cleaned:
        if candidate_is_confident(item, query, learning_lang=learning_lang):
            seed.append(item)
        else:
            rest.append(item)
    return (seed + rest)[:LOOKUP_CATEGORY_LIMIT]


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


def _payload_candidate(item: dict) -> dict:
    out = {
        "lemma": (item.get("lemma") or "").strip(),
        "pos": item.get("pos"),
        "gloss": (item.get("gloss") or "").strip(),
    }
    reading = (item.get("reading") or "").strip()
    if reading:
        out["reading"] = reading
    typed = (item.get("typed_as") or "").strip()
    if typed:
        out["typed_as"] = typed
    return out


def append_lookup_candidates(
    existing: list[dict],
    incoming: list[dict],
    *,
    learning_lang: str = "en",
    limit: int | None = LOOKUP_CACHE_LIMIT,
) -> tuple[list[dict], int]:
    """Add new translations. A bare noun drops only when the same translation has an article.

    Returns (merged_payload, n_added).
    """
    incoming_clean = sanitize_lookup_candidates(
        incoming, learning_lang=learning_lang, limit=None
    )
    by_key: dict[tuple[str, str, str], dict] = {}
    order: list[tuple[str, str, str]] = []
    for item in existing:
        payload = _payload_candidate(item)
        if not payload["lemma"]:
            continue
        key = lookup_dedup_key(
            payload["lemma"],
            payload.get("pos"),
            learning_lang=learning_lang,
            gloss=payload.get("gloss"),
        )
        if key in by_key:
            by_key[key] = merge_lookup_variants(
                by_key[key], payload, learning_lang=learning_lang
            )
            continue
        order.append(key)
        by_key[key] = payload
    added = 0
    for item in incoming_clean:
        payload = _payload_candidate(item)
        if not payload["lemma"]:
            continue
        key = lookup_dedup_key(
            payload["lemma"],
            payload.get("pos"),
            learning_lang=learning_lang,
            gloss=payload.get("gloss"),
        )
        if key in by_key:
            by_key[key] = merge_lookup_variants(
                by_key[key], payload, learning_lang=learning_lang
            )
            continue
        if limit is not None and len(order) >= limit:
            break
        order.append(key)
        by_key[key] = payload
        added += 1
    return [by_key[k] for k in order], added


# Słowniki trzymają te hiszpańskie rzeczowniki w liczbie mnogiej. Reszta idzie do liczby pojedynczej.
_ES_PLURALIA = {
    "cascos",
    "gafas",
    "tijeras",
    "pantalones",
    "vaqueros",
    "vacaciones",
    "celos",
    "alrededores",
    "viveres",
    "víveres",
}
_ES_PLURAL_ARTICLE = {"los": "el", "las": "la"}
# Bez ó — ta sama litera jest w hiszpańskim (automóvil, región) i myliła _swap_reversed_reading.
_POLISH_LETTERS = set("ąćęłńśźż")


def _singular_spanish_noun(lemma: str) -> str:
    """las drogas → la droga. los cascos zostaje."""
    words = lemma.split()
    if len(words) != 2:
        return lemma
    article = words[0].casefold().rstrip("'")
    singular_article = _ES_PLURAL_ARTICLE.get(article)
    if singular_article is None:
        return lemma
    noun = words[1]
    key = _norm_token(_strip_diacritics(noun))
    if key in _ES_PLURALIA or noun.casefold() in _ES_PLURALIA:
        return lemma
    folded = noun.casefold()
    if len(folded) < 4 or not folded.endswith("s"):
        return lemma
    # paises / leones zostawiamy modelowi. Bezpieczne jest tylko samogłoska + s.
    if folded.endswith("es"):
        return lemma
    if folded[-2] not in "aeiouáéíóúü":
        return lemma
    return f"{singular_article} {noun[:-1]}"


# Adjectives that end in -a in the masculine singular too.
_ES_INVARIABLE_A = {
    "rosa",
    "naranja",
    "lila",
    "violeta",
    "malva",
    "fucsia",
    "turquesa",
    "agrícola",
    "hipócrita",
    "idiota",
    "patriota",
    "persa",
    "maya",
    "celta",
    "belga",
    "azteca",
    "inca",
    "cosmopolita",
    "homicida",
    "suicida",
    "entusiasta",
}
_ES_ARTICLES = {"el", "la", "los", "las", "un", "una", "unos", "unas", "lo"}


def _masculine_spanish_adjective(lemma: str) -> str:
    """bonitas / la bonita → bonito, queridos → querido, grandes → grande, felices → feliz."""
    words = lemma.split()
    if len(words) == 2 and words[0].casefold() in _ES_ARTICLES:
        words = words[1:]
    if len(words) != 1:
        return lemma
    word = words[0]
    low = word.casefold()
    if len(low) < 4 or low in _ES_INVARIABLE_A:
        return word
    if low.endswith("ces"):
        return word[:-3] + "z"
    if low.endswith(("os", "as")):
        word, low = word[:-1], low[:-1]
    elif low.endswith("es"):
        base = low[:-2]
        if base.endswith(("nd", "nt", "rd", "rt", "bl", "pl", "rv", "lc", "ld")):
            return word[:-1]
        if base.endswith(("l", "r", "n", "d", "j", "s")):
            return word[:-2]
        return word[:-1]
    if low in _ES_INVARIABLE_A or low.endswith("ista"):
        return word
    if low.endswith("ora") and len(low) > 5:
        return word[:-1]
    if low.endswith("a"):
        return word[:-1] + "o"
    return word


def _is_extension(word: str, query: str) -> bool:
    """word is the query plus at most two letters. Equality does not count."""
    return bool(query) and word.startswith(query) and 0 < len(word) - len(query) <= 2


def _near_query(word: str, query: str) -> bool:
    """True when one string is the other, or the other plus at most two letters."""
    if not word or not query or len(word) < 3 or len(query) < 3:
        return False
    if word == query:
        return True
    short, long = (word, query) if len(word) <= len(query) else (query, word)
    return long.startswith(short) and 0 < len(long) - len(short) <= 2


_SHADOWED_BY_ADVERB = {"adj", "pron", "det"}

# Glosses that are adverbs. The model keeps pasting them onto an adjective.
_ADVERB_GLOSSES = {
    "dużo",
    "mało",
    "bardzo",
    "trochę",
    "nagle",
    "często",
    "zawsze",
    "nigdy",
    "tutaj",
    "wcale",
    "dobrze",
    "źle",
}


def drop_implausible_lookup_rows(
    candidates: list[dict],
    query: str,
    *,
    learning_lang: str,
    native_lang: str | None = None,
) -> list[dict]:
    """Drop a lemma invented by stretching the query, and a duplicate part of speech.

    `much` / `mucha` is the query with one letter added, not a Spanish headword.
    The same gloss on an adjective and an adverb is the same meaning labeled twice.
    """
    q = _norm_token(_strip_diacritics(query))
    kept: list[dict] = []
    for item in candidates:
        item = _swap_reversed_reading(item, q, learning_lang)
        item = _native_gloss_citation(item, native_lang)
        if _is_grammar_note(item.get("gloss") or "", native_lang):
            continue
        if _is_corrected_echo(item, query, learning_lang):
            continue
        if _is_proper_name(item, query, learning_lang):
            continue
        stem = _norm_token(
            _strip_diacritics(lemma_stem(item.get("lemma") or "", learning_lang))
        )
        gloss_plain = _norm_token(item.get("gloss") or "")
        gloss = _norm_token(_strip_diacritics(gloss_plain))
        if _is_extension(stem, q) and (gloss == q or _is_extension(gloss, q)):
            continue
        if gloss_plain in _ADVERB_GLOSSES and normalize_pos_bucket(item.get("pos")) in _SHADOWED_BY_ADVERB:
            item = dict(item)
            item["pos"] = "adv"
        kept.append(item)
    collapsed = _collapse_adverb_shadows(kept, learning_lang)
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for item in collapsed:
        key = (
            _norm_token(lemma_stem(item.get("lemma") or "", learning_lang)),
            normalize_pos_bucket(item.get("pos")) or "",
            _norm_token(item.get("gloss") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return _drop_native_word_lemmas(unique, query, learning_lang)


def _gloss_is_the_query(gloss: str, query: str) -> bool:
    g = _norm_token(_strip_diacritics(gloss))
    if not g or not query:
        return False
    if g == query:
        return True
    # libros → glosa libro
    return query.startswith(g) and query[len(g):] in {"s", "es"}


def _lemma_looks_polish(lemma: str) -> bool:
    folded = lemma.casefold()
    if any(ch in folded for ch in _POLISH_LETTERS):
        return True
    # okulary, tani — hiszpańskie lematy prawie nigdy nie kończą się na samo y.
    return " " not in folded and folded.endswith("y") and len(folded) > 3


def _swap_reversed_reading(item: dict, query: str, learning_lang: str) -> dict:
    """Lemat po polsku i glosa będąca zapytaniem: pola są zamienione."""
    if not (learning_lang or "").lower().startswith("es"):
        return item
    lemma = (item.get("lemma") or "").strip()
    gloss = (item.get("gloss") or "").strip()
    stem = lemma_stem(lemma, learning_lang) or lemma
    if _has_article(lemma, learning_lang) and not _lemma_looks_polish(stem):
        return item
    if not _lemma_looks_polish(stem):
        return item
    if not _gloss_is_the_query(gloss, query):
        return item
    swapped = dict(item)
    swapped["lemma"] = gloss
    swapped["gloss"] = stem
    return swapped


def _has_article(lemma: str, learning_lang: str) -> bool:
    words = lemma.split()
    return len(words) >= 2 and words[0].lower().rstrip("'") in _article_set(learning_lang)


def _collapse_adverb_shadows(
    candidates: list[dict], learning_lang: str
) -> list[dict]:
    groups: dict[tuple[str, str], list[int]] = {}
    for index, item in enumerate(candidates):
        stem = _norm_token(lemma_stem(item.get("lemma") or "", learning_lang))
        gloss = _norm_token(item.get("gloss") or "")
        groups.setdefault((stem, gloss), []).append(index)
    drop: set[int] = set()
    for indexes in groups.values():
        buckets = {normalize_pos_bucket(candidates[i].get("pos")) for i in indexes}
        if "adv" not in buckets:
            continue
        for index in indexes:
            if normalize_pos_bucket(candidates[index].get("pos")) in _SHADOWED_BY_ADVERB:
                drop.add(index)
    return [item for index, item in enumerate(candidates) if index not in drop]


def _query_is_inflection_of(query: str, lemma: str, learning_lang: str) -> bool:
    """pies is the plural citation's query; el pie stays."""
    stem = _fold(lemma_stem(lemma, learning_lang))
    q = _fold(query)
    if not stem or not q or stem == q:
        return False
    if q in {stem + "s", stem + "es"}:
        return True
    return stem.endswith("z") and q == stem[:-1] + "ces"


def _drop_native_word_lemmas(
    candidates: list[dict], query: str, learning_lang: str
) -> list[dict]:
    """drogi / drogi, kosztowny next to caro / drogi: drogi is the native word, not an L2 headword.

    The lemma is dropped when another row uses it as the native gloss of a different lemma.
    A homograph typed exactly (para / dla beside el par / para) and an inflected L2 query
    (drogas → la droga) keep their row; a noun carrying an L2 article is L2 by form.
    """
    q = _fold(query)
    glossed_by: dict[str, set[str]] = {}
    for item in candidates:
        lemma_key = _norm_token(item.get("lemma") or "")
        for token in gloss_tokens(item.get("gloss") or ""):
            glossed_by.setdefault(_fold(token), set()).add(lemma_key)
    kept: list[dict] = []
    for item in candidates:
        lemma = item.get("lemma") or ""
        if _has_article(lemma, learning_lang):
            kept.append(item)
            continue
        stem = _fold(lemma_stem(lemma, learning_lang))
        others = glossed_by.get(stem, set()) - {_norm_token(lemma)}
        if (
            others
            and stem != q
            and not _query_is_inflection_of(query, lemma, learning_lang)
        ):
            continue
        kept.append(item)
    return kept


_PL_GRAMMAR_NOTE = (
    "dopełniacz",
    "biernik",
    "celownik",
    "narzędnik",
    "miejscownik",
    "wołacz",
    "mianownik",
    "liczba mnoga",
    "liczby mnogiej",
    "rodzaju",
    "forma ",
    " od „",
)

# Polish adjective endings → citation ending. Longest first; k/g stems take -i.
_PL_ADJ_ENDINGS = (
    ("iego", "i"),
    ("iemu", "i"),
    ("ego", "y"),
    ("emu", "y"),
    ("iej", "i"),
    ("ich", "i"),
    ("imi", "i"),
    ("ych", "y"),
    ("ymi", "y"),
    ("dzy", "gi"),
    ("rzy", "ry"),
    ("ej", "y"),
    ("ą", ""),
    ("a", ""),
    ("e", ""),
)


def _polish_adjective_citation(word: str) -> str:
    """droga, drogie, drogiego, drodzy → drogi; ładna → ładny; tania → tani."""
    if " " in word or len(word) < 3:
        return word
    lower = word.casefold()
    if lower.endswith(("y", "i")) and not lower.endswith(("dzy", "rzy")):
        return word
    for ending, citation in _PL_ADJ_ENDINGS:
        if not lower.endswith(ending):
            continue
        stem = word[: len(word) - len(ending)]
        if citation:
            return stem + citation
        if not stem:
            return word
        if stem.casefold().endswith("i"):
            return stem
        if stem.casefold().endswith(("k", "g")):
            return stem + "i"
        return stem + "y"
    return word


def _native_gloss_citation(item: dict, native_lang: str | None) -> dict:
    """Polish adjective glosses come back as the masculine singular citation."""
    if not (native_lang or "").lower().startswith("pl"):
        return item
    if normalize_pos_bucket(item.get("pos")) != "adj":
        return item
    gloss = (item.get("gloss") or "").strip()
    parts = [p.strip() for p in re.split(r"[,;]", gloss) if p.strip()]
    fixed = [_polish_adjective_citation(p) for p in parts]
    if fixed == parts:
        return item
    out = dict(item)
    seen: list[str] = []
    for word in fixed:
        if word not in seen:
            seen.append(word)
    out["gloss"] = ", ".join(seen)
    return out


def _is_corrected_echo(item: dict, query: str, learning_lang: str) -> bool:
    """el oko / oko for okon: the typo was fixed into the native word and copied as the lemma.

    A copy is only trusted when it is what the user typed (el hotel / hotel for hotel)
    or its plural (hoteles).
    """
    lemma = item.get("lemma") or ""
    stem = _fold(lemma_stem(lemma, learning_lang))
    tokens = gloss_tokens(item.get("gloss") or "")
    if not stem or not tokens or stem != _fold(tokens[0]):
        return False
    return stem != _fold(query) and not _query_is_inflection_of(query, lemma, learning_lang)


def _is_proper_name(item: dict, query: str, learning_lang: str) -> bool:
    """la Tania / Tania is a first name, not vocabulary. German nouns are capitalized."""
    if (learning_lang or "").lower().startswith("de") or query[:1].isupper():
        return False
    lemma = (item.get("lemma") or "").strip()
    words = lemma.split()
    if _has_article(lemma, learning_lang):
        words = words[1:]
    return bool(words) and words[0][:1].isupper()


def _same_word(a: str, b: str) -> bool:
    """drogie and drogi are one word; rodzian and rozrodziany are not."""
    a, b = _fold(a), _fold(b)
    if not a or not b:
        return False
    if a == b or _fold(_polish_adjective_citation(a)) == _fold(_polish_adjective_citation(b)):
        return True
    prefix = 0
    for x, y in zip(a, b):
        if x != y:
            break
        prefix += 1
    return prefix >= max(3, min(len(a), len(b)) - 2)


def _one_change_away(a: str, b: str) -> bool:
    """Exact match, or one replacement, insertion, deletion, or adjacent swap."""
    fa, fb = _fold(a), _fold(b)
    if not fa or not fb or abs(len(fa) - len(fb)) > 1:
        return False
    if fa == fb:
        return True
    return edit_distance(fa, fb) == 1


def row_translates_its_word(raw: dict, query: str, *, learning_lang: str) -> bool:
    """Keep a row that translates the word it names, or whose lemma or gloss is one change from the query.

    A row without `word`, or whose `word` is the query itself, is kept. A row that
    names a different word is kept when the visible lemma or gloss is the query
    or one letter away from it.
    """
    word = (raw.get("word") or "").strip()
    stem = lemma_stem(raw.get("lemma") or "", learning_lang)
    glosses = gloss_tokens(raw.get("gloss") or "")
    if not word or _fold(word) == _fold(query):
        return True
    if _one_change_away(stem, query) or any(_one_change_away(token, query) for token in glosses):
        return True
    if _same_word(word, stem):
        return True
    return any(_same_word(word, token) for token in glosses)


def _is_grammar_note(gloss: str, native_lang: str | None) -> bool:
    if not (native_lang or "").lower().startswith("pl"):
        return False
    low = (gloss or "").casefold()
    return any(term in low for term in _PL_GRAMMAR_NOTE)


def count_new_lookup_rows(
    before: list[dict], after: list[dict], *, learning_lang: str
) -> int:
    old = {
        lookup_dedup_key(
            item.get("lemma") or "",
            item.get("pos"),
            learning_lang=learning_lang,
            gloss=item.get("gloss"),
        )
        for item in before
        if (item.get("lemma") or "").strip()
    }
    return sum(
        1
        for item in after
        if (item.get("lemma") or "").strip()
        and lookup_dedup_key(
            item.get("lemma") or "",
            item.get("pos"),
            learning_lang=learning_lang,
            gloss=item.get("gloss"),
        )
        not in old
    )


def sanitize_lookup_candidates(
    candidates: list[dict],
    *,
    learning_lang: str = "en",
    limit: int | None = LOOKUP_CACHE_LIMIT,
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
        if (learning_lang or "").lower().startswith("es"):
            singular = _singular_spanish_noun(lemma)
            if normalize_pos_bucket(item.get("pos")) == "adj":
                # Polish query pasted as lemma (droga/droga or droga/drogi). Rewriting
                # -a→-o invents "drogo"; the real Spanish headword is caro. A real
                # Spanish feminine (cara/drogi, bonita/ładna) still becomes masculine.
                stem_fold = _fold(lemma_stem(lemma, learning_lang))
                gloss_fold = _fold(gloss)
                if stem_fold and stem_fold == gloss_fold:
                    continue
                typed = _fold(item.get("word") or "")
                if stem_fold and typed and stem_fold == typed:
                    gloss_cit = _fold(_polish_adjective_citation(gloss))
                    typed_cit = _fold(_polish_adjective_citation(typed))
                    stem_cit = _fold(_polish_adjective_citation(stem_fold))
                    if gloss_cit and gloss_cit in {typed_cit, stem_cit}:
                        continue
                singular = _masculine_spanish_adjective(singular)
            if singular != lemma:
                item = dict(item)
                item["lemma"] = singular

        item = canonicalize_lookup_candidate(item, learning_lang=learning_lang)
        lemma = (item.get("lemma") or "").strip()
        refined = refine_lookup_pos(lemma, item.get("pos"), learning_lang=learning_lang)
        item["pos"] = refined
        bucket = normalize_pos_bucket(refined)
        words = lemma.split()
        n = len(words)

        if bucket == "verb":
            if n < 1 or n > 3:
                continue
        elif bucket == "noun":
            if n == 1:
                pass  # bare noun stays bare; an article is kept only when the model wrote it
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

    return dedupe_lookup_candidates(cleaned, learning_lang=learning_lang, limit=limit)

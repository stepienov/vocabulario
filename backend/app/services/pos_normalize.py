"""Canonical POS + L2 headword normalization for lookup and enrichment.

Rules:
- pos is ALWAYS a short English bucket: noun, verb, adj, adv, prep, conj, pron, det, interj, …
- NEVER localized labels (rzeczownik, sustantivo, …) and NEVER gender in pos.
- Gender for article languages is encoded ONLY in the lemma prefix (el libro, la casa, der Mann).
"""

from __future__ import annotations

import re

from app.lsp.lang_utils import articles_for

# Canonical buckets returned to clients / stored on cards.
CANONICAL_POS_BUCKETS = frozenset(
    {
        "noun",
        "verb",
        "adj",
        "adv",
        "prep",
        "conj",
        "pron",
        "det",
        "interj",
        "phrase",
        "construction",
        "particle",
    }
)

# Exact aliases (already canonical or short codes).
_POS_ALIASES: dict[str, str] = {
    "n": "noun",
    "nn": "noun",
    "noun": "noun",
    "s": "noun",
    "substantive": "noun",
    "substantiv": "noun",
    "nom": "noun",
    "v": "verb",
    "vb": "verb",
    "verb": "verb",
    "verbum": "verb",
    "a": "adj",
    "adj": "adj",
    "adjective": "adj",
    "adjectif": "adj",
    "adjetivo": "adj",
    "aggettivo": "adj",
    "adjektiv": "adj",
    "przymiotnik": "adj",
    "прилагательное": "adj",
    "形容词": "adj",
    "形容詞": "adj",
    "형용사": "adj",
    "صفة": "adj",
    "विशेषण": "adj",
    "sıfat": "adj",
    "tính từ": "adj",
    "adv": "adv",
    "adverb": "adv",
    "adverbe": "adv",
    "adverbio": "adv",
    "avverbio": "adv",
    "advérbio": "adv",
    "przysłówek": "adv",
    "наречие": "adv",
    "副词": "adv",
    "副詞": "adv",
    "부사": "adv",
    "ظرف": "adv",
    "क्रियाविशेषण": "adv",
    "zarf": "adv",
    "trạng từ": "adv",
    "prep": "prep",
    "preposition": "prep",
    "przyimek": "prep",
    "präposition": "prep",
    "preposición": "prep",
    "preposizione": "prep",
    "préposition": "prep",
    "preposição": "prep",
    "предлог": "prep",
    "介词": "prep",
    "前置詞": "prep",
    "전치사": "prep",
    "حرف جر": "prep",
    "संबंधबोधक": "prep",
    "edat": "prep",
    "giới từ": "prep",
    "conj": "conj",
    "conjunction": "conj",
    "spójnik": "conj",
    "konjunktion": "conj",
    "conjunción": "conj",
    "congiunzione": "conj",
    "conjonction": "conj",
    "conjunção": "conj",
    "союз": "conj",
    "连词": "conj",
    "接続詞": "conj",
    "접속사": "conj",
    "حرف عطف": "conj",
    "संयोजक": "conj",
    "bağlaç": "conj",
    "liên từ": "conj",
    "pron": "pron",
    "pronoun": "pron",
    "zaimek": "pron",
    "pronome": "pron",
    "pronombre": "pron",
    "pronom": "pron",
    "местоимение": "pron",
    "代词": "pron",
    "代名詞": "pron",
    "대명사": "pron",
    "ضمير": "pron",
    "सर्वनाम": "pron",
    "zamir": "pron",
    "đại từ": "pron",
    "det": "det",
    "determiner": "det",
    "article": "det",
    "przedimek": "det",
    "artikel": "det",
    "artículo": "det",
    "articolo": "det",
    "déterminant": "det",
    "관형사": "det",
    "mạo từ": "det",
    "interj": "interj",
    "interjection": "interj",
    "wykrzyknik": "interj",
    "interjeição": "interj",
    "interjección": "interj",
    "interiezione": "interj",
    "interjektion": "interj",
    "междометие": "interj",
    "感叹词": "interj",
    "感動詞": "interj",
    "감탄사": "interj",
    "تعجب": "interj",
    "विस्मयादिबोधक": "interj",
    "ünlem": "interj",
    "thán từ": "interj",
    "sostantivo": "noun",
    "substantivo": "noun",
    "rzeczownik": "noun",
    "czasownik": "verb",
    "ww": "verb",
    "isim": "noun",
    "danh từ": "noun",
    "名詞": "noun",
    "名词": "noun",
    "명사": "noun",
    "اسم": "noun",
    "संज्ञा": "noun",
    "существительное": "noun",
    "verbo": "verb",
    "verbe": "verb",
    "fiil": "verb",
    "động từ": "verb",
    "動詞": "verb",
    "动词": "verb",
    "동사": "verb",
    "فعل": "verb",
    "क्रिया": "verb",
    "глагол": "verb",
    "phrase": "phrase",
    "expression": "phrase",
    "idiom": "phrase",
    "wyrażenie": "phrase",
    "construction": "construction",
    "konstrukcja": "construction",
    "particle": "particle",
}

# Substring hints for localized / verbose LLM labels (order: check noun before adj).
_NOUN_HINTS = (
    "rzeczownik",
    "sustantivo",
    "sostantivo",
    "substantivo",
    "substantiv",
    "nom ",
    "nomen",
    "noun",
    "существ",
    "名詞",
    "名词",
    "명사",
    "isim",
    "danh từ",
    "संज्ञा",
    "اسم",
)
_VERB_HINTS = (
    "czasownik",
    "verbo",
    "verbe",
    "verb",
    "глагол",
    "动词",
    "動詞",
    "동사",
    "fiil",
    "động từ",
    "क्रिया",
    "فعل",
)
_ADJ_HINTS = (
    "przymiotnik",
    "adjetivo",
    "adjectif",
    "aggettivo",
    "adjektiv",
    "adjective",
    "adj",
    "прилаг",
    "形容词",
    "形容詞",
    "형용사",
    "صفة",
    "विशेषण",
    "sıfat",
    "tính từ",
    "przym",
)
_ADV_HINTS = (
    "przysłówek",
    "adverbio",
    "adverbe",
    "avverbio",
    "adverb",
    "нареч",
    "副词",
    "副詞",
    "부사",
    "zarf",
    "trạng từ",
)
_PREP_HINTS = (
    "przyimek",
    "preposición",
    "preposizione",
    "préposition",
    "präposition",
    "preposição",
    "preposition",
    "предлог",
    "介词",
    "前置詞",
    "전치사",
    "edat",
    "giới từ",
)
_CONJ_HINTS = (
    "spójnik",
    "conjunción",
    "congiunzione",
    "conjonction",
    "konjunktion",
    "conjunção",
    "conjunction",
    "союз",
    "连词",
    "接続詞",
    "접속사",
    "bağlaç",
    "liên từ",
)
_PRON_HINTS = (
    "zaimek",
    "pronombre",
    "pronome",
    "pronom",
    "pronoun",
    "местоимение",
    "代词",
    "代名詞",
    "대명사",
    "zamir",
    "đại từ",
)
_DET_HINTS = (
    "przedimek",
    "artículo",
    "articolo",
    "artikel",
    "déterminant",
    "article",
    "determiner",
    "관형사",
    "mạo từ",
)
_INTERJ_HINTS = (
    "wykrzyknik",
    "interjección",
    "interiezione",
    "interjektion",
    "interjection",
    "междометие",
    "感叹词",
    "感動詞",
    "감탄사",
    "ünlem",
    "thán từ",
)

_BUCKET_HINTS = (
    (_NOUN_HINTS, "noun"),
    (_VERB_HINTS, "verb"),
    (_ADJ_HINTS, "adj"),
    (_ADV_HINTS, "adv"),
    (_PREP_HINTS, "prep"),
    (_CONJ_HINTS, "conj"),
    (_PRON_HINTS, "pron"),
    (_DET_HINTS, "det"),
    (_INTERJ_HINTS, "interj"),
)

_GENDER_MASC = ("masc", "männ", "męsk", "męż", "мужск", "masculin", "masculino")
_GENDER_FEM = ("femin", "fémin", "żeńsk", "weib", "женск", "feminin", "femenino", "feminino")
_GENDER_NEUT = ("neutr", "nijak", "säch", "средн", "neutro")

# Definite article to add when LLM returns bare noun + gender hint (singular).
_SINGULAR_DEFINITE: dict[str, dict[str, str]] = {
    "es": {"m": "el", "f": "la"},
    "fr": {"m": "le", "f": "la"},
    "de": {"m": "der", "f": "die", "n": "das"},
    "it": {"m": "il", "f": "la"},
    "pt-br": {"m": "o", "f": "a"},
    "pt-pt": {"m": "o", "f": "a"},
}

# Map leading article → gender (for inferring gender from existing lemma).
_ARTICLE_GENDER: dict[str, dict[str, str]] = {
    "es": {"el": "m", "la": "f", "los": "m", "las": "f"},
    "fr": {"le": "m", "la": "f", "les": "m", "l'": "m"},  # l' ambiguous; ok for dedup
    "de": {"der": "m", "die": "f", "das": "n"},
    "it": {"il": "m", "lo": "m", "la": "f", "i": "m", "gli": "m", "le": "f"},
    "pt-br": {"o": "m", "a": "f", "os": "m", "as": "f"},
    "pt-pt": {"o": "m", "a": "f", "os": "m", "as": "f"},
}


def normalize_pos_bucket(pos: str | None) -> str:
    """Map any LLM / legacy label to a canonical English POS bucket."""
    raw = (pos or "").strip().lower()
    if not raw or raw == "unknown":
        return "unknown"

    if raw in _POS_ALIASES:
        return _POS_ALIASES[raw]
    if raw in CANONICAL_POS_BUCKETS:
        return raw

    for hints, bucket in _BUCKET_HINTS:
        for hint in hints:
            if hint in raw:
                return bucket

    compact = re.sub(r"[^\w\s]", " ", raw, flags=re.UNICODE)
    compact = re.sub(r"\s+", " ", compact).strip()
    if compact in _POS_ALIASES:
        return _POS_ALIASES[compact]
    if compact in CANONICAL_POS_BUCKETS:
        return compact
    for hints, bucket in _BUCKET_HINTS:
        for hint in hints:
            if hint in compact:
                return bucket
    first = compact.split()[0] if compact else ""
    if first in _POS_ALIASES:
        return _POS_ALIASES[first]
    return "unknown"


def infer_gender_from_pos(pos: str | None) -> str | None:
    """Extract m/f/n from verbose pos like 'sustantivo masculino' (used only internally)."""
    p = (pos or "").lower()
    if not p:
        return None
    if any(g in p for g in _GENDER_NEUT):
        return "n"
    if any(g in p for g in _GENDER_FEM):
        return "f"
    if any(g in p for g in _GENDER_MASC):
        return "m"
    return None


def _article_set(learning_lang: str) -> set[str]:
    return {a.lower() for a in articles_for(learning_lang)}


def _resolve_lang(code: str) -> str:
    c = (code or "").strip().lower()
    return "pt-br" if c == "pt" else c


def lemma_has_article(lemma: str, learning_lang: str) -> bool:
    articles = _article_set(learning_lang)
    words = lemma.split()
    return len(words) >= 2 and words[0].lower().rstrip("'") in articles


def lemma_stem(lemma: str, learning_lang: str) -> str:
    """Headword without leading article."""
    articles = _article_set(learning_lang)
    words = lemma.split()
    if len(words) >= 2 and words[0].lower().rstrip("'") in articles:
        return " ".join(words[1:]).lower()
    return lemma.strip().lower()


def infer_gender_from_lemma(lemma: str, learning_lang: str) -> str | None:
    lang = _resolve_lang(learning_lang)
    mapping = _ARTICLE_GENDER.get(lang, {})
    words = lemma.split()
    if len(words) < 2:
        return None
    art = words[0].lower().rstrip("'")
    return mapping.get(art)


def ensure_noun_article(
    lemma: str,
    *,
    learning_lang: str,
    gender: str | None,
) -> str:
    """Add definite article to bare singular noun when gender is known."""
    lang = _resolve_lang(learning_lang)
    articles = _SINGULAR_DEFINITE.get(lang)
    if not articles or not gender:
        return lemma
    if lemma_has_article(lemma, learning_lang):
        return lemma
    words = lemma.split()
    if len(words) != 1:
        return lemma
    prefix = articles.get(gender)
    if not prefix:
        return lemma
    return f"{prefix} {lemma}"


def canonicalize_lookup_candidate(
    item: dict,
    *,
    learning_lang: str,
) -> dict:
    """Normalize pos + lemma for one lookup candidate."""
    lemma = (item.get("lemma") or "").strip()
    gloss = (item.get("gloss") or "").strip()
    raw_pos = item.get("pos")
    if not lemma or not gloss:
        return item

    bucket = normalize_pos_bucket(raw_pos)
    gender = infer_gender_from_lemma(lemma, learning_lang) or infer_gender_from_pos(raw_pos)

    if bucket == "noun":
        lemma = ensure_noun_article(lemma, learning_lang=learning_lang, gender=gender)

    out = dict(item)
    out["lemma"] = lemma
    out["pos"] = bucket if bucket != "unknown" else None
    return out


def merge_lookup_variants(
    kept: dict,
    new: dict,
    *,
    learning_lang: str,
) -> dict:
    """Merge two candidates for the same headword+pos; keep best lemma and gloss."""
    articles = _article_set(learning_lang)
    bucket = normalize_pos_bucket(kept.get("pos") or new.get("pos"))

    k_lemma = kept.get("lemma") or ""
    n_lemma = new.get("lemma") or ""

    if bucket == "noun" and articles:
        k_art = lemma_has_article(k_lemma, learning_lang)
        n_art = lemma_has_article(n_lemma, learning_lang)
        if n_art and not k_art:
            best_lemma = n_lemma
        elif k_art and not n_art:
            best_lemma = k_lemma
        else:
            best_lemma = k_lemma or n_lemma
        gender = (
            infer_gender_from_lemma(best_lemma, learning_lang)
            or infer_gender_from_lemma(n_lemma, learning_lang)
            or infer_gender_from_lemma(k_lemma, learning_lang)
            or infer_gender_from_pos(kept.get("pos"))
            or infer_gender_from_pos(new.get("pos"))
        )
        best_lemma = ensure_noun_article(
            best_lemma, learning_lang=learning_lang, gender=gender
        )
    else:
        best_lemma = k_lemma or n_lemma

    best_gloss = kept.get("gloss") or new.get("gloss") or ""
    merged = dict(kept)
    merged.update(new)
    merged["lemma"] = best_lemma
    merged["gloss"] = best_gloss
    merged["pos"] = bucket if bucket != "unknown" else None
    return merged


def lookup_dedup_key(lemma: str, pos: str | None, *, learning_lang: str) -> tuple[str, str]:
    """Dedup key: stem + canonical pos bucket (never raw sustantivo masculino)."""
    bucket = normalize_pos_bucket(pos)
    return (lemma_stem(lemma, learning_lang), bucket)

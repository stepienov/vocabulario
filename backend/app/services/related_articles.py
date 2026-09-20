"""Citation articles on related words — copy/lift from the LLM, never invent."""

from __future__ import annotations

from app.lsp.constants import normalize_l2_code
from app.services.pos_normalize import normalize_pos_bucket

# Languages whose dictionary citation form includes a definite article / ال.
ARTICLE_REQUIRED_LANGS = frozenset({"es", "fr", "de", "it", "pt-br", "pt-pt", "ar"})
AR_DEFINITE = "ال"

# Definite citation articles only (no un/une/ein/the).
_CITATION_ARTICLES: dict[str, tuple[str, ...]] = {
    "es": ("los", "las", "el", "la"),
    "fr": ("les", "le", "la"),
    "de": ("der", "die", "das"),
    "it": ("gli", "il", "lo", "la", "i", "le"),
    "pt-br": ("os", "as", "o", "a"),
    "pt-pt": ("os", "as", "o", "a"),
}


def _lang(code: str | None) -> str:
    c = normalize_l2_code(code)
    return "pt-br" if c == "pt" else c


def article_is_required(pos: str | None, learning_lang: str | None) -> bool:
    if normalize_pos_bucket(pos) != "noun":
        return False
    return _lang(learning_lang) in ARTICLE_REQUIRED_LANGS


def lift_article_from_lemma(lemma: str, learning_lang: str | None) -> tuple[str | None, str]:
    """If the LLM already put a citation article on the lemma, copy it off. No guessing."""
    text = (lemma or "").strip()
    if not text:
        return None, ""
    lang = _lang(learning_lang)
    if lang == "ar":
        if text.startswith(AR_DEFINITE) and len(text) > len(AR_DEFINITE):
            return AR_DEFINITE, text[len(AR_DEFINITE) :]
        return None, text
    lower = text
    if lang in ("fr", "it") and (lower.lower().startswith("l'") or lower.lower().startswith("l’")):
        return text[:2], text[2:].lstrip()
    articles = _CITATION_ARTICLES.get(lang, ())
    parts = text.split(None, 1)
    if len(parts) == 2 and parts[0].lower().rstrip("'’") in {a.lower() for a in articles}:
        return parts[0], parts[1]
    return None, text


def attach_article(
    entry: dict,
    raw_article: object,
    learning_lang: str | None,
) -> dict:
    """Copy LLM article (or lift from lemma). Non-gated rows always get article=None."""
    pos = entry.get("pos")
    lemma = str(entry.get("lemma") or "").strip()
    if not article_is_required(pos, learning_lang):
        entry["article"] = None
        entry["lemma"] = lemma
        return entry
    article = str(raw_article or "").strip() or None
    if not article:
        lifted, stem = lift_article_from_lemma(lemma, learning_lang)
        if lifted:
            article, lemma = lifted, stem
    else:
        _, stem = lift_article_from_lemma(lemma, learning_lang)
        if stem and lemma.lower().startswith(article.lower()):
            lemma = stem
    entry["lemma"] = lemma
    entry["article"] = article
    return entry


def related_needs_article(entry: dict, learning_lang: str | None) -> bool:
    return article_is_required(entry.get("pos"), learning_lang) and not (
        entry.get("article") or ""
    ).strip()


def drop_related_missing_articles(
    entries: list[dict],
    learning_lang: str | None,
) -> list[dict]:
    return [e for e in entries if not related_needs_article(e, learning_lang)]


def apply_article_repairs(entries: list[dict], repairs: dict[str, str]) -> list[dict]:
    """repairs maps lemma (as stored) -> article string from the 1× LLM fill."""
    if not repairs:
        return entries
    out: list[dict] = []
    for entry in entries:
        lemma = str(entry.get("lemma") or "")
        article = repairs.get(lemma) or repairs.get(lemma.casefold())
        if article and not (entry.get("article") or "").strip():
            entry = dict(entry)
            entry["article"] = str(article).strip()
        out.append(entry)
    return out


_RELATED_KEYS = ("synonyms_l2", "antonyms_l2", "word_family_l2", "associations_l2")


def related_items_missing_article(core: dict, learning_lang: str | None) -> list[dict]:
    missing: list[dict] = []
    for key in _RELATED_KEYS:
        for item in core.get(key) or []:
            if not isinstance(item, dict):
                continue
            if not article_is_required(item.get("pos"), learning_lang):
                continue
            if str(item.get("article") or "").strip():
                continue
            lifted, _ = lift_article_from_lemma(str(item.get("lemma") or ""), learning_lang)
            if lifted:
                continue
            missing.append(item)
    return missing


async def fill_related_articles_on_core(llm: object, core: dict, learning_lang: str | None) -> None:
    """One LLM pass to fill article only. Mock / empty → leave for the drop gate."""
    missing = related_items_missing_article(core, learning_lang)
    if not missing:
        return
    if getattr(llm, "mock", False):
        return
    repair_fn = getattr(llm, "repair_related_articles", None)
    if repair_fn is None:
        return
    payload = [
        {"lemma": str(item.get("lemma") or ""), "pos": item.get("pos")}
        for item in missing
        if item.get("lemma")
    ]
    repairs_raw = await repair_fn(payload, learning_lang)
    if not isinstance(repairs_raw, dict):
        return
    articles = repairs_raw.get("articles") if "articles" in repairs_raw else repairs_raw
    if not isinstance(articles, dict):
        return
    for item in missing:
        lemma = str(item.get("lemma") or "")
        article = articles.get(lemma) or articles.get(lemma.casefold())
        if article:
            item["article"] = str(article).strip()

"""Darmowe hasła ze słowników Wikimedia — zanim ruszy płatny model.

Źródło: Wikisłownik (MediaWiki, bez klucza). Szukamy tego samego napisu
w wydaniu języka UI i w wydaniu języka nauki, plus angielski Wiktionary
(jedyne z gotowym JSON-em części mowy).
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import unicodedata
from urllib.parse import quote

import httpx

from app.ai.language_typology import LANG_NAMES_EN
from app.ai.prompts.v1 import LANG_NAMES_PL
from app.core.config import get_settings
from app.core.lemma_keys import canonical_lemma
from app.services.pos_normalize import (
    canonicalize_lookup_candidate,
    ensure_noun_article,
    normalize_pos_bucket,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_MAX_CANDIDATES = 8

_FORM_POS = re.compile(
    r"forma\s+(czasownika|rzeczownika|przymiotnika|przysłówka)|verb form|inflected",
    re.I,
)
_PL_SECTION = re.compile(
    r"^==\s*(.+?)\s*==\s*$",
    re.M,
)
_EN_H2 = re.compile(r"^==\s*([^=]+?)\s*==\s*$", re.M)
_WIKILINK = re.compile(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]")
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_HTML_TAG = re.compile(r"<[^>]+>")
_T_TEMPLATE = re.compile(
    r"\{\{t{1,2}\+?\|(?P<lang>[a-z]{2,3}(?:-[a-z]+)?)\|(?P<lemma>[^}|]+)"
    r"(?:\|(?P<rest>[^}]*))?\}\}",
    re.I,
)
_GENDER_TOKEN = re.compile(r"\{\{\s*([żmfn]|f|m|n|mf)\s*\}\}", re.I)
_ES_NOUN_GENDER = re.compile(r"\{\{es-noun\|(?P<g>[fmn])", re.I)
_SENSE_LINE = re.compile(r"^:\s*\([^)]+\)\s*(.+)$", re.M)


def wiki_lang_code(code: str | None) -> str:
    c = (code or "").strip().lower()
    if c in {"pt-br", "pt-pt", "pt"}:
        return "pt"
    return c


def _wiki_host(code: str | None) -> str:
    return f"{wiki_lang_code(code)}.wiktionary.org"


def _user_agent() -> str:
    return (get_settings().wikimedia_user_agent or "").strip() or (
        "Vocabulario/1.0 (https://github.com/stepienov/vocabulario; wiktionary-lookup)"
    )


def _client_headers() -> dict[str, str]:
    ua = _user_agent()
    return {"User-Agent": ua, "Api-User-Agent": ua}


def strip_wiki_text(raw: str) -> str:
    text = html.unescape(_HTML_TAG.sub("", raw or ""))
    text = _WIKILINK.sub(r"\1", text)
    text = _TEMPLATE.sub("", text)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.I | re.S)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" .,;:–—")
    return text


def _gender_from_text(raw: str) -> str | None:
    blob = (raw or "").lower()
    if "żeńsk" in blob or "{{ż}}" in blob or re.search(r"\|f(?:\||}|$)", blob):
        if "męsk" not in blob[:80]:
            return "f"
    if re.search(r"\{\{\s*ż\s*\}\}", blob):
        return "f"
    if "nijak" in blob or re.search(r"\{\{\s*n\s*\}\}", blob):
        return "n"
    if "męsk" in blob or re.search(r"\{\{\s*m\s*\}\}", blob):
        return "m"
    m = _GENDER_TOKEN.search(raw or "")
    if m:
        tok = m.group(1).lower()
        if tok in {"ż", "f"}:
            return "f"
        if tok in {"m"}:
            return "m"
        if tok in {"n"}:
            return "n"
    m = _ES_NOUN_GENDER.search(raw or "")
    if m:
        g = m.group("g").lower()
        return "f" if g == "f" else "n" if g == "n" else "m"
    return None


def _pos_from_heading(heading: str) -> str | None:
    bucket = normalize_pos_bucket(heading)
    return None if bucket == "unknown" else bucket


def _lang_names_for(code: str) -> set[str]:
    wiki = wiki_lang_code(code)
    names: set[str] = set()
    en = LANG_NAMES_EN.get(wiki) or LANG_NAMES_EN.get(code, "")
    pl = LANG_NAMES_PL.get(wiki) or LANG_NAMES_PL.get(code, "")
    if en:
        names.add(en.casefold())
        names.add(en.split("(")[0].strip().casefold())
    if pl:
        names.add(pl.casefold())
        names.add(f"język {pl}".casefold())
    extra = {
        "es": {"español", "spanisch", "hiszpański", "spanish"},
        "en": {"english", "angielski", "englisch"},
        "fr": {"français", "french", "francuski", "französisch"},
        "de": {"deutsch", "german", "niemiecki"},
        "it": {"italiano", "italian", "włoski"},
        "pt": {"português", "portuguese", "portugalski"},
        "pl": {"polski", "polish", "polnisch"},
        "ru": {"русский", "russian", "rosyjski"},
        "zh": {"chinese", "chiński", "中文"},
        "ja": {"japanese", "japoński", "日本語"},
        "ko": {"korean", "koreański", "한국어"},
        "ar": {"arabic", "arabski", "العربية"},
        "hi": {"hindi"},
        "tr": {"turkish", "turecki", "türkçe"},
        "vi": {"vietnamese", "wietnamski"},
    }
    names.update(extra.get(wiki, set()))
    return {n for n in names if n}


def _heading_is_lang(heading: str, code: str) -> bool:
    h = (heading or "").casefold()
    return any(name in h for name in _lang_names_for(code))


def _split_pl_sections(wikitext: str) -> dict[str, str]:
    """Mapuje nagłówek sekcji PL → treść (np. 'casa ({{język hiszpański}})')."""
    matches = list(_PL_SECTION.finditer(wikitext or ""))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
        out[m.group(1).strip()] = wikitext[start:end]
    return out


def _first_gloss_lines(block: str, limit: int = 2) -> str:
    glosses: list[str] = []
    for m in _SENSE_LINE.finditer(block or ""):
        raw = m.group(1)
        if "{{forma" in raw.lower() or "forma verbal" in raw.lower():
            continue
        text = strip_wiki_text(raw)
        if text and text not in glosses:
            glosses.append(text)
        if len(glosses) >= limit:
            break
    return ", ".join(glosses)


def parse_pl_l2_section(block: str, *, lemma: str) -> list[dict]:
    """Hasło L2 na pl.wiktionary: część mowy + polska glosa."""
    znaczenia = block
    idx = block.find("{{znaczenia}}")
    if idx >= 0:
        znaczenia = block[idx:]
    chunks = re.split(r"\n''(.+?)''\s*\n", znaczenia)
    out: list[dict] = []
    if len(chunks) == 1:
        pos = _pos_from_heading(znaczenia[:200]) or "noun"
        if not _FORM_POS.search(znaczenia[:240]):
            gloss = _first_gloss_lines(znaczenia)
            if gloss:
                out.append(
                    {
                        "lemma": lemma,
                        "pos": pos,
                        "gloss": gloss,
                        "gender": _gender_from_text(znaczenia[:400]),
                    }
                )
        return out
    # split keeps headings in odd indices when using capturing split after preamble
    # chunks[0]=preamble, then heading, body, heading, body...
    i = 1
    while i + 1 < len(chunks):
        heading = chunks[i]
        body = chunks[i + 1]
        i += 2
        if _FORM_POS.search(heading):
            continue
        pos = _pos_from_heading(heading)
        if pos is None:
            continue
        gloss = _first_gloss_lines(body)
        if not gloss:
            continue
        out.append(
            {
                "lemma": lemma,
                "pos": pos,
                "gloss": gloss,
                "gender": _gender_from_text(heading + " " + body[:200]),
            }
        )
    return out


def parse_pl_translations(block: str, *, target_lang: str) -> list[dict]:
    """Tłumaczenia z hasła L1 na pl.wiktionary → lematy L2."""
    names = _lang_names_for(target_lang)
    names |= {LANG_NAMES_PL.get(wiki_lang_code(target_lang), "")}
    names = {n.casefold() for n in names if n}
    out: list[dict] = []
    for line in (block or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("*"):
            continue
        low = stripped.casefold()
        if not any(name and name in low.split(":")[0] for name in names):
            continue
        gender_line = _gender_from_text(stripped)
        for m in _WIKILINK.finditer(stripped):
            lemma = m.group(1).split("#")[0].strip()
            if not lemma or ":" in lemma:
                continue
            after = stripped[m.end() : m.end() + 24]
            gm = _GENDER_TOKEN.match(after.strip()) or _GENDER_TOKEN.search(after)
            if gm:
                tok = gm.group(1).lower()
                gender = "f" if tok in {"ż", "f"} else "n" if tok == "n" else "m"
            else:
                gender = gender_line
            out.append({"lemma": lemma, "pos": "noun", "gender": gender})
        if out:
            break
    return out[:_MAX_CANDIDATES]


def parse_en_rest_l2(payload: dict, *, learning_lang: str) -> list[dict]:
    key = wiki_lang_code(learning_lang)
    rows = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pos = _pos_from_heading(str(row.get("partOfSpeech") or ""))
        defs = row.get("definitions") or []
        gloss = ""
        if defs and isinstance(defs[0], dict):
            gloss = strip_wiki_text(str(defs[0].get("definition") or ""))
        if not pos and not gloss:
            continue
        out.append({"pos": pos, "gloss": gloss, "language": row.get("language")})
    return out


def parse_en_translation_lines(wikitext: str, *, target_lang: str) -> list[dict]:
    want = wiki_lang_code(target_lang)
    out: list[dict] = []
    seen: set[str] = set()
    for m in _T_TEMPLATE.finditer(wikitext or ""):
        if wiki_lang_code(m.group("lang")) != want:
            continue
        lemma = (m.group("lemma") or "").strip()
        if not lemma or lemma.casefold() in seen:
            continue
        seen.add(lemma.casefold())
        rest = m.group("rest") or ""
        gender = None
        if re.search(r"(^|\|)f(\||$)", rest):
            gender = "f"
        elif re.search(r"(^|\|)n(\||$)", rest):
            gender = "n"
        elif re.search(r"(^|\|)m(\||$)", rest):
            gender = "m"
        out.append({"lemma": lemma, "pos": "noun", "gender": gender})
        if len(out) >= _MAX_CANDIDATES:
            break
    return out


def _sense_key(text: str) -> str:
    base = canonical_lemma(text)
    nfd = unicodedata.normalize("NFD", base)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _gloss_keys(gloss: str) -> set[str]:
    keys: set[str] = set()
    for part in re.split(r"[,;/]", gloss or ""):
        key = _sense_key(part)
        if key:
            keys.add(key)
    whole = _sense_key(gloss)
    if whole:
        keys.add(whole)
    return keys


def readings_are_same_sense(query: str, learning: dict, native: dict) -> bool:
    """Polskie hasło to to samo, gdy jest znaczeniem / tłumaczeniem hiszpańskiego."""
    if _sense_key(learning.get("lemma") or "") == _sense_key(native.get("lemma") or ""):
        return True
    q = _sense_key(query)
    l2_gloss = _gloss_keys(str(learning.get("gloss") or ""))
    if q and q in l2_gloss:
        return True
    native_gloss = _gloss_keys(str(native.get("gloss") or ""))
    if native_gloss & l2_gloss:
        return True
    return False


def reconcile_bilingual_readings(
    query: str,
    learning: list[dict],
    native: list[dict],
) -> list[dict]:
    """Jedno hasło gdy znaczenie się pokrywa; oba odczyty gdy to dwa różne słowa."""
    if not native:
        return learning
    if not learning:
        return native
    unmatched_native: list[dict] = []
    for item in native:
        if any(readings_are_same_sense(query, other, item) for other in learning):
            continue
        unmatched_native.append(item)
    if not unmatched_native:
        return learning
    out: list[dict] = []
    for item in learning:
        tagged = dict(item)
        tagged["reading"] = "learning"
        out.append(tagged)
    for item in unmatched_native:
        tagged = dict(item)
        tagged["reading"] = "native"
        tagged["typed_as"] = query
        out.append(tagged)
    return out


def _candidate(
    lemma: str,
    pos: str | None,
    gloss: str,
    *,
    learning_lang: str,
    gender: str | None = None,
) -> dict | None:
    bucket = normalize_pos_bucket(pos) if pos else None
    if (bucket == "noun" or (pos or "").startswith("noun")) and gender:
        lemma = ensure_noun_article(lemma, learning_lang=learning_lang, gender=gender)
        pos = "noun"
    item = {"lemma": lemma, "pos": pos, "gloss": gloss, "lexical_entry_id": None}
    item = canonicalize_lookup_candidate(item, learning_lang=learning_lang)
    if not (item.get("lemma") or "").strip() or not (item.get("gloss") or "").strip():
        return None
    return {
        "lemma": item["lemma"],
        "pos": item.get("pos"),
        "gloss": item["gloss"],
        "lexical_entry_id": None,
    }


def _title_variants(text: str) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    out = [t]
    if t[:1].isupper() and t != t[:1].lower() + t[1:]:
        out.append(t[:1].lower() + t[1:])
    elif t[:1].islower():
        cap = t[:1].upper() + t[1:]
        if cap not in out:
            out.append(cap)
    # unique preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        k = x.casefold()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq


async def _http_json(
    client: httpx.AsyncClient, url: str
) -> dict | None:
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        logger.info("wiktionary fetch fail %s %s", url, exc)
        return None
    if resp.status_code == 404 or resp.status_code == 501:
        return None
    if resp.status_code >= 400:
        logger.info("wiktionary status %s %s", resp.status_code, url)
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _parse_api_url(host: str, title: str) -> str:
    return (
        f"https://{host}/w/api.php?action=parse&page={quote(title, safe='')}"
        f"&prop=wikitext&format=json&redirects=1"
    )


def _query_title_url(host: str, title: str) -> str:
    return (
        f"https://{host}/w/api.php?action=query&titles={quote(title, safe='')}"
        f"&format=json&redirects=1"
    )


def parse_wiktionary_title_exists(payload: dict | None) -> bool | None:
    """True/False when MediaWiki answered; None when the payload is unusable."""
    if not isinstance(payload, dict):
        return None
    query = payload.get("query")
    if not isinstance(query, dict):
        return None
    pages = query.get("pages")
    if not isinstance(pages, dict) or not pages:
        return None
    page = next(iter(pages.values()), None)
    if not isinstance(page, dict):
        return None
    if "missing" in page:
        return False
    try:
        page_id = int(page.get("pageid") or 0)
    except (TypeError, ValueError):
        return None
    if page_id < 0:
        return False
    return True


async def wiktionary_title_exists(
    title: str,
    lang: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool | None:
    """Does this title exist on {lang}.wiktionary.org? None = network/unknown."""
    variants = _title_variants(title)
    if not variants:
        return None
    host = _wiki_host(lang)
    own = client is None
    http = client or httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers=_client_headers(),
        follow_redirects=True,
    )
    try:
        saw_false = False
        for variant in variants:
            payload = await _http_json(http, _query_title_url(host, variant))
            exists = parse_wiktionary_title_exists(payload)
            if exists is True:
                return True
            if exists is False:
                saw_false = True
        return False if saw_false else None
    finally:
        if own:
            await http.aclose()



def _rest_def_url(title: str) -> str:
    return f"https://en.wiktionary.org/api/rest_v1/page/definition/{quote(title, safe='')}"


def _wikitext_from_parse(payload: dict | None) -> str:
    if not payload:
        return ""
    parse = payload.get("parse")
    if not isinstance(parse, dict):
        return ""
    wt = parse.get("wikitext")
    if isinstance(wt, dict):
        return str(wt.get("*") or "")
    return str(wt or "")


async def lookup_dictionary_candidates(
    text: str,
    *,
    app_lang: str,
    learning_lang: str,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Hasła słownikowe dla zapytania w języku UI albo języka nauki. Zero modelu."""
    variants = _title_variants(text)
    if not variants:
        return []
    title = variants[0]
    own = client is None
    http = client or httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers=_client_headers(),
        follow_redirects=True,
    )
    try:
        app_host = _wiki_host(app_lang)
        en_def_p = _http_json(http, _rest_def_url(title))
        app_parse_p = _http_json(http, _parse_api_url(app_host, title))
        trans_p = _http_json(http, _parse_api_url("en.wiktionary.org", f"{title}/translations"))
        en_def, app_parse, trans_parse = await _gather_three(en_def_p, app_parse_p, trans_p)
        return assemble_dictionary_candidates(
            query=title,
            app_lang=app_lang,
            learning_lang=learning_lang,
            en_rest=en_def,
            app_wikitext=_wikitext_from_parse(app_parse),
            en_translations=_wikitext_from_parse(trans_parse),
        )
    finally:
        if own:
            await http.aclose()


async def _gather_three(a, b, c):
    return await asyncio.gather(a, b, c)


def assemble_dictionary_candidates(
    *,
    query: str,
    app_lang: str,
    learning_lang: str,
    en_rest: dict | None,
    app_wikitext: str,
    en_translations: str,
) -> list[dict]:
    """Składa propozycje z już pobranych stron — do testów bez sieci."""
    app = wiki_lang_code(app_lang)
    pl_sections = _split_pl_sections(app_wikitext) if app == "pl" else {}
    en_l2 = parse_en_rest_l2(en_rest or {}, learning_lang=learning_lang)
    query_is_l1 = bool(
        isinstance(en_rest, dict) and app in en_rest and app != wiki_lang_code(learning_lang)
    )

    learning: list[dict] = []
    native: list[dict] = []

    pos_hint = en_l2[0].get("pos") if en_l2 else None
    if app == "pl":
        for heading, block in pl_sections.items():
            if _heading_is_lang(heading, learning_lang):
                for item in parse_pl_l2_section(block, lemma=query):
                    cand = _candidate(
                        item["lemma"],
                        item.get("pos") or pos_hint,
                        item.get("gloss") or "",
                        learning_lang=learning_lang,
                        gender=item.get("gender"),
                    )
                    if cand:
                        learning.append(cand)
                break
    if not learning and app == "en":
        for row in en_l2:
            cand = _candidate(
                query,
                row.get("pos"),
                row.get("gloss") or "",
                learning_lang=learning_lang,
                gender=_gender_from_text(app_wikitext),
            )
            if cand:
                learning.append(cand)

    native_block = ""
    if app == "pl":
        for heading, block in pl_sections.items():
            if _heading_is_lang(heading, app_lang):
                native_block = block
                break
        for item in parse_pl_translations(native_block, target_lang=learning_lang):
            cand = _candidate(
                item["lemma"],
                item.get("pos") or "noun",
                query,
                learning_lang=learning_lang,
                gender=item.get("gender"),
            )
            if cand:
                native.append(cand)

    if not native and (query_is_l1 or app == "en"):
        pos = None
        if query_is_l1 and isinstance(en_rest, dict):
            rows = en_rest.get(app) or []
            if rows and isinstance(rows[0], dict):
                pos = _pos_from_heading(str(rows[0].get("partOfSpeech") or ""))
        for item in parse_en_translation_lines(en_translations, target_lang=learning_lang):
            cand = _candidate(
                item["lemma"],
                item.get("pos") or pos or "noun",
                query,
                learning_lang=learning_lang,
                gender=item.get("gender"),
            )
            if cand:
                native.append(cand)

    found = reconcile_bilingual_readings(query, learning, native)

    out: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for c in found:
        key = (c["lemma"].casefold(), str(c.get("pos") or ""), str(c.get("reading") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= _MAX_CANDIDATES:
            break
    return out

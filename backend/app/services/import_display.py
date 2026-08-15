"""Import trybu „zachowaj fiszki”: role pól + bloki UI do renderu."""

from __future__ import annotations

import hashlib
import logging
import re
from html import unescape
from typing import Any

from app.ai.prompts.v1 import lang_name_pl
from app.services.import_format import ensure_deck_segmented
from app.services.import_package import ImportPackageError, RawImportDeck, sample_notes_for_llm
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

_COMPLEX_CHARS = 280
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+\n")
_MULTI_NL = re.compile(r"\n{3,}")
_SOUND_RE = re.compile(r"\[sound:[^\]]+\]", re.IGNORECASE)


def strip_anki_sound(value: str) -> str:
    """Usuń tagi Anki [sound:…] — audio obce; TTS robi aplikacja."""
    return _SOUND_RE.sub(" ", value or "").strip()


def strip_html(value: str) -> str:
    t = unescape(value or "")
    t = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", t)
    t = re.sub(r"(?is)<button\b[^>]*>.*?</button>", " ", t)
    t = strip_anki_sound(t)
    # Anki card front: prefer lemma node when TTS chrome is present
    m = re.search(
        r'class=["\'][^"\']*(?:front-word|answer-word|es-word)[^"\']*["\'][^>]*>([^<]+)',
        t,
        re.I,
    )
    if m and re.search(r"play-btn|AnkiDroid|speechSynthesis|front-word", value or "", re.I):
        # Only collapse to lemma when this looks like a Front HTML field
        if "<table" not in (value or "").lower() and "meanings" not in (value or "").lower():
            return m.group(1).strip()
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p\s*>", "\n\n", t)
    t = re.sub(r"(?i)</div\s*>", "\n", t)
    t = re.sub(r"(?i)</li\s*>", "\n", t)
    t = _TAG_RE.sub(" ", t)
    t = re.sub(r"[▶►]", " ", t)
    t = _WS_RE.sub("\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = _MULTI_NL.sub("\n\n", t)
    return t.strip()


def _cell_text(html: str) -> str:
    return strip_html(html or "").strip()


def html_structure_blocks(value: str) -> list[dict] | None:
    """Deterministic HTML → display blocks for <table>/<ul>/<ol> (before flat strip)."""
    raw = value or ""
    if "<table" not in raw.lower() and "<ul" not in raw.lower() and "<ol" not in raw.lower():
        return None
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    blocks: list[dict] = []

    for table_html in re.findall(r"(?is)<table\b[^>]*>.*?</table>", cleaned):
        rows_html = re.findall(r"(?is)<tr\b[^>]*>.*?</tr>", table_html)
        if not rows_html:
            continue
        parsed_rows: list[list[str]] = []
        for tr in rows_html:
            cells = re.findall(r"(?is)<t[hd]\b[^>]*>(.*?)</t[hd]>", tr)
            parsed_rows.append([_cell_text(c) for c in cells])
        parsed_rows = [r for r in parsed_rows if any(c.strip() for c in r)]
        if not parsed_rows:
            continue
        headers: list[str] | None = None
        body = parsed_rows
        if re.search(r"(?is)<th\b", rows_html[0]) or len(parsed_rows) > 1:
            headers = parsed_rows[0]
            body = parsed_rows[1:]
        b = _empty_block("table")
        b["headers"] = headers
        b["rows"] = body
        b["semantic"] = "conjugation"
        blocks.append(b)

    for m in re.finditer(r"(?is)<(ul|ol)\b[^>]*>(.*?)</\1>", cleaned):
        items = [_cell_text(li) for li in re.findall(r"(?is)<li\b[^>]*>(.*?)</li>", m.group(0))]
        items = [i for i in items if i]
        if not items:
            continue
        b = _empty_block("list")
        b["items"] = items
        blocks.append(b)

    return blocks or None


def _field(note: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(note):
        return ""
    return strip_html(note[index] or "")


def _field_raw(note: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(note):
        return ""
    return note[index] or ""


def _empty_block(type_: str = "paragraph") -> dict:
    return {
        "type": type_,
        "text": None,
        "emphasis": None,
        "field_index": None,
        "l2_field_index": None,
        "l1_field_index": None,
        "heading": None,
        "collapsed": None,
        "items": None,
        "headers": None,
        "rows": None,
        "split": None,
        "children": None,
        "align": None,
        "size": None,
        "semantic": None,
        "tts": None,
    }


def _split_paragraphs(text: str) -> list[dict]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not parts:
        return []
    if len(parts) == 1:
        b = _empty_block("paragraph")
        b["text"] = parts[0]
        return [b]
    out: list[dict] = []
    for p in parts:
        b = _empty_block("paragraph")
        b["text"] = p
        out.append(b)
    return out


def _split_headings(text: str, hints: list[str] | None = None) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines()]
    hints_l = {h.strip().lower() for h in (hints or []) if h.strip()}
    sections: list[dict] = []
    current_heading: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_heading
        body = "\n".join(buf).strip()
        buf = []
        if not body and not current_heading:
            return
        if current_heading:
            sec = _empty_block("section")
            sec["heading"] = current_heading
            sec["collapsed"] = len(body) > 160
            child = _empty_block("paragraph" if len(body) < 400 else "pre")
            child["text"] = body or None
            sec["children"] = [child] if body else []
            sections.append(sec)
        elif body:
            for b in _split_paragraphs(body):
                sections.append(b)
        current_heading = None

    for ln in lines:
        if not ln:
            buf.append("")
            continue
        is_hint = ln.lower() in hints_l
        is_short_header = (
            len(ln) <= 48
            and not ln.endswith(".")
            and (ln[0].isupper() or ln.endswith(":") or is_hint)
        )
        if is_hint or (is_short_header and buf and any(x.strip() for x in buf)):
            flush()
            current_heading = ln.rstrip(":")
            continue
        if is_short_header and not buf and current_heading is None and sections:
            flush()
            current_heading = ln.rstrip(":")
            continue
        buf.append(ln)
    flush()
    return sections or _split_paragraphs(text)


def _materialize_block(spec: dict, note: list[str]) -> dict | None:
    btype = (spec.get("type") or "paragraph").strip()
    out = _empty_block(btype)
    out["emphasis"] = spec.get("emphasis")
    out["heading"] = spec.get("heading")
    out["collapsed"] = spec.get("collapsed")
    out["split"] = spec.get("split")
    out["items"] = spec.get("items")
    out["headers"] = spec.get("headers")
    out["rows"] = spec.get("rows")
    out["align"] = spec.get("align")
    out["size"] = spec.get("size")
    out["semantic"] = spec.get("semantic")
    out["tts"] = spec.get("tts")

    if btype == "bilingual":
        l2 = _field(note, spec.get("l2_field_index"))
        l1 = _field(note, spec.get("l1_field_index"))
        if not l2 and not l1:
            return None
        out["text"] = l2
        out["items"] = [l1] if l1 else None
        return out

    if btype == "section":
        children_spec = spec.get("children") or []
        children: list[dict] = []
        for ch in children_spec:
            if not isinstance(ch, dict):
                continue
            got = _materialize_block(ch, note)
            if got:
                if got.get("type") == "_multi":
                    children.extend(got.get("children") or [])
                else:
                    children.extend(_expand_split(got, note))
        if spec.get("field_index") is not None:
            raw = _field_raw(note, spec.get("field_index"))
            structured = html_structure_blocks(raw) if raw else None
            if structured:
                children.extend(structured)
            elif raw:
                cleaned = strip_html(raw)
                split = (spec.get("split") or "none") or "none"
                tmp = _empty_block("text" if len(cleaned) < 400 else "section")
                if tmp["type"] == "section":
                    tmp["heading"] = out.get("heading") or "Content"
                    tmp["collapsed"] = True
                    child = _empty_block("text")
                    child["text"] = cleaned
                    tmp["children"] = [child]
                    children.append(tmp)
                else:
                    tmp["text"] = cleaned
                    tmp["split"] = split
                    children.extend(_expand_split(tmp, note))
        # Drop empty decorative sections (e.g. "Odmiana" without tables)
        if not children:
            return None
        out["children"] = children
        if out["collapsed"] is None:
            out["collapsed"] = True
        return out

    # Prefer structured HTML for table/list targets or rich fields
    if spec.get("field_index") is not None:
        raw = _field_raw(note, spec.get("field_index"))
        if btype in {"table", "list", "pre", "paragraph", "text"} or (
            raw and ("<table" in raw.lower() or "<ul" in raw.lower())
        ):
            structured = html_structure_blocks(raw)
            if structured:
                if len(structured) == 1:
                    first = structured[0]
                    for key in ("align", "size", "semantic", "tts", "heading", "collapsed"):
                        if out.get(key) is not None and first.get(key) is None:
                            first[key] = out[key]
                    return first
                # Multiple tables/lists from one field → wrap for caller
                wrap = _empty_block("_multi")
                wrap["children"] = structured
                return wrap

    text = (spec.get("text") or "").strip()
    if spec.get("field_index") is not None:
        text = _field(note, spec.get("field_index")) or text
    if not text and btype not in {"divider", "section", "table"}:
        if btype == "table" and (out.get("rows") or out.get("headers")):
            return out
        return None
    out["text"] = text or None
    return out


def _expand_split(block: dict, note: list[str]) -> list[dict]:
    if block.get("type") == "_multi":
        return list(block.get("children") or [])
    split = (block.get("split") or "none") or "none"
    text = (block.get("text") or "").strip()
    if split in (None, "none") or not text:
        return [block]
    if split == "paragraphs":
        return _split_paragraphs(text) or [block]
    if split == "headings":
        return _split_headings(text) or [block]
    return [block]


def materialize_side(template_blocks: list[dict], note: list[str]) -> list[dict]:
    out: list[dict] = []
    for spec in template_blocks:
        if not isinstance(spec, dict):
            continue
        block = _materialize_block(spec, note)
        if not block:
            continue
        if block.get("type") == "_multi":
            # Promote multi-table field into a collapsed conjugation section
            sec = _empty_block("section")
            sec["heading"] = spec.get("heading") or "Odmiana"
            sec["collapsed"] = True
            sec["semantic"] = "conjugation"
            sec["children"] = list(block.get("children") or [])
            out.append(sec)
            continue
        out.extend(_expand_split(block, note))
    return out


def _prompt_label(blocks: list[dict]) -> str:
    for b in blocks:
        if b.get("type") in {"headword", "title"} and (b.get("text") or "").strip():
            return (b["text"] or "").strip()[:120]
        if b.get("semantic") == "headword" and (b.get("text") or "").strip():
            return (b["text"] or "").strip()[:120]
    for b in blocks:
        if b.get("type") in {"paragraph", "text", "pre"} and (b.get("text") or "").strip():
            return (b["text"] or "").strip()[:120]
    return "Karta"


def _answer_label(blocks: list[dict]) -> str:
    for b in blocks:
        if b.get("type") == "gloss" and (b.get("text") or "").strip():
            return (b["text"] or "").strip()[:120]
        if b.get("semantic") == "translation" and (b.get("text") or "").strip():
            return (b["text"] or "").strip()[:120]
    for b in blocks:
        if b.get("type") in {"title", "paragraph", "text"} and (b.get("text") or "").strip():
            # Only first line — avoid dumping examples into list gloss
            return (b["text"] or "").strip().splitlines()[0][:120]
        if b.get("type") == "bilingual" and (b.get("items") or [None])[0]:
            return str(b["items"][0])[:120]
        if b.get("type") == "section":
            for ch in b.get("children") or []:
                if ch.get("type") == "gloss" and (ch.get("text") or "").strip():
                    return (ch["text"] or "").strip()[:120]
                if (ch.get("text") or "").strip():
                    return (ch["text"] or "").strip().splitlines()[0][:120]
    return ""


def _split_meanings_block(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Meanings_Block: 1. linia = gloss L1; dalej pary przykład ES + PL."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return "", []
    gloss_parts: list[str] = []
    pairs: list[tuple[str, str]] = []
    i = 0
    # First line (possibly "1. gloss") is primary translation
    first = re.sub(r"^\d+\.\s*", "", lines[0]).strip()
    if first:
        gloss_parts.append(first)
    i = 1
    while i < len(lines):
        ln = lines[i]
        sense = re.match(r"^(\d+)\.\s*(.+)$", ln)
        if sense:
            gloss_parts.append(sense.group(2).strip())
            i += 1
            continue
        l2 = ln
        l1 = ""
        if i + 1 < len(lines) and not re.match(r"^\d+\.\s*", lines[i + 1]):
            l1 = lines[i + 1]
            i += 2
        else:
            i += 1
        if l2 or l1:
            pairs.append((l2, l1))
    gloss = "; ".join(dict.fromkeys(gloss_parts))  # unique, keep order
    return gloss, pairs


_IRREG_RE = re.compile(
    r"(oboczno[sś][cć]|e\s*→\s*ie|o\s*→\s*ue|e\s*→\s*i|irregular)",
    re.I,
)


def _looks_like_irregularity(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 40:
        return False
    return bool(_IRREG_RE.search(t)) or bool(re.fullmatch(r"[eo]\s*[→\-]\s*[ie]{1,2}", t, re.I))


def _extract_cards_html_back(html: str) -> dict[str, Any]:
    """Parse Anki Cards HTML back: irregularity + meanings-raw + conjugation tables."""
    raw = html or ""
    irreg = None
    m = re.search(
        r'class=["\'][^"\']*irregularity[^"\']*["\'][^>]*>(.*?)</div>',
        raw,
        re.I | re.S,
    )
    if m:
        irreg = strip_html(m.group(1))
        irreg = re.sub(r"(?i)^oboczno[sś][cć]\s*:\s*", "", irreg).strip() or irreg
    meanings = None
    m = re.search(
        r'id=["\']meanings-raw["\'][^>]*>(.*?)</div>',
        raw,
        re.I | re.S,
    )
    if m:
        meanings = unescape(m.group(1)).strip()
        meanings = re.sub(r"<[^>]+>", "", meanings).strip()
    tables = html_structure_blocks(raw)
    return {"irregularity": irreg, "meanings": meanings, "tables": tables}


def _refine_card_blocks(
    prompt_blocks: list[dict],
    answer_blocks: list[dict],
    note: list[str],
    *,
    learning_lang: str,
    app_lang: str = "pl",
) -> tuple[list[dict], list[dict], bool]:
    """Post-AI cleanup: front=lemma only, split meanings, tables, no empty sections."""
    # Fast path: Anki Cards HTML with structured back
    if (
        len(note) >= 2
        and note[1]
        and (
            "meanings-raw" in note[1]
            or (
                "<table" in note[1].lower()
                and re.search(r"front-word|play-btn", note[0] or "", re.I)
            )
        )
    ):
        lemma = strip_html(note[0])
        parsed = _extract_cards_html_back(note[1])
        prompt = []
        if lemma:
            hb = _empty_block("headword")
            hb["text"] = lemma
            hb["align"] = "center"
            hb["size"] = "lemma"
            hb["semantic"] = "headword"
            hb["tts"] = {"enabled": True, "lang": learning_lang}
            prompt.append(hb)
        answer: list[dict] = []
        bidirectional = False
        if parsed.get("meanings"):
            gloss, pairs = _split_meanings_block(parsed["meanings"])
            if gloss:
                gb = _empty_block("gloss")
                gb["text"] = gloss
                gb["size"] = "gloss"
                gb["semantic"] = "translation"
                gb["align"] = "center"
                gb["tts"] = {"enabled": True, "lang": app_lang}
                answer.append(gb)
                bidirectional = True
            if pairs:
                sec = _empty_block("section")
                sec["heading"] = "Przykłady"
                sec["collapsed"] = False
                children = []
                for l2, l1 in pairs:
                    bi = _empty_block("bilingual")
                    bi["text"] = l2 or None
                    bi["items"] = [l1] if l1 else None
                    bi["semantic"] = "example"
                    children.append(bi)
                sec["children"] = children
                answer.append(sec)
        if parsed.get("irregularity"):
            chip = _empty_block("chip")
            chip["text"] = parsed["irregularity"]
            chip["size"] = "caption"
            chip["semantic"] = "note"
            insert_at = 1 if answer and answer[0].get("type") == "gloss" else 0
            answer.insert(insert_at, chip)
        if parsed.get("tables"):
            sec = _empty_block("section")
            sec["heading"] = "Odmiana"
            sec["collapsed"] = True
            sec["semantic"] = "conjugation"
            sec["children"] = list(parsed["tables"])
            answer.append(sec)
        if prompt and answer:
            p, a = _finalize_blocks(prompt, answer, learning_lang, app_lang)
            return p, a, bidirectional

    prompt = []
    moved_meta: list[dict] = []
    has_headword = False
    for b in prompt_blocks:
        btype = b.get("type")
        text = (b.get("text") or "").strip()
        if btype in {"chip", "meta", "note"} and _looks_like_irregularity(text):
            chip = _empty_block("chip")
            chip["text"] = re.sub(r"(?i)^oboczno[sś][cć]\s*:\s*", "", text).strip()
            chip["size"] = "caption"
            chip["semantic"] = "note"
            moved_meta.append(chip)
            continue
        if btype in {"chip", "meta"}:
            moved_meta.append(b)
            continue
        if btype in {"headword", "title"} or b.get("semantic") == "headword":
            clean = re.sub(r"[▶►]", "", text).strip()
            hb = dict(b)
            hb["type"] = "headword"
            hb["text"] = clean
            hb["align"] = "center"
            hb["size"] = "lemma"
            hb["semantic"] = "headword"
            prev = b.get("tts") if isinstance(b.get("tts"), dict) else {}
            lang = (prev.get("lang") or "").strip() or learning_lang
            hb["tts"] = {"enabled": True, "lang": lang}
            prompt.append(hb)
            has_headword = True
            continue
        if text:
            clean = re.sub(r"[▶►]", "", text).strip()
            if clean and not _looks_like_irregularity(clean):
                if not has_headword:
                    hb = _empty_block("headword")
                    hb["text"] = clean.splitlines()[0][:80]
                    hb["align"] = "center"
                    hb["size"] = "lemma"
                    hb["semantic"] = "headword"
                    prev = b.get("tts") if isinstance(b.get("tts"), dict) else {}
                    lang = (prev.get("lang") or "").strip() or learning_lang
                    hb["tts"] = {"enabled": True, "lang": lang}
                    prompt.append(hb)
                    has_headword = True
                else:
                    prompt.append(b)

    answer = []
    bidirectional = False
    meanings_done = False

    def _emit_meanings(raw_text: str) -> None:
        nonlocal bidirectional, meanings_done
        gloss, pairs = _split_meanings_block(raw_text)
        if gloss:
            gb = _empty_block("gloss")
            gb["text"] = gloss
            gb["size"] = "gloss"
            gb["semantic"] = "translation"
            gb["align"] = "center"
            gb["tts"] = {"enabled": True, "lang": app_lang}
            answer.append(gb)
            bidirectional = True
            meanings_done = True
        if pairs:
            sec = _empty_block("section")
            sec["heading"] = "Przykłady"
            sec["collapsed"] = False
            children = []
            for l2, l1 in pairs:
                bi = _empty_block("bilingual")
                bi["text"] = l2 or None
                bi["items"] = [l1] if l1 else None
                bi["semantic"] = "example"
                children.append(bi)
            sec["children"] = children
            answer.append(sec)

    for b in answer_blocks:
        btype = b.get("type")
        text = (b.get("text") or "").strip()
        if btype in {"gloss", "title", "paragraph", "text"} and text and not meanings_done:
            if "\n" in text or len(text) > 60:
                _emit_meanings(text)
                continue
            gb = _empty_block("gloss")
            gb["text"] = text
            gb["size"] = "gloss"
            gb["semantic"] = "translation"
            gb["align"] = "center"
            prev = b.get("tts") if isinstance(b.get("tts"), dict) else {}
            lang = (prev.get("lang") or "").strip() or app_lang
            gb["tts"] = {"enabled": True, "lang": lang}
            answer.append(gb)
            bidirectional = True
            meanings_done = True
            continue
        if btype == "section":
            children = list(b.get("children") or [])
            heading = (b.get("heading") or "").strip()
            if children and not meanings_done:
                blob = "\n".join(
                    (ch.get("text") or "").strip()
                    for ch in children
                    if (ch.get("text") or "").strip()
                )
                if blob and ("\n" in blob) and not any(
                    ch.get("type") == "table" for ch in children
                ):
                    _emit_meanings(blob)
                    continue
            if not children:
                continue
            nb = dict(b)
            if any(ch.get("type") == "table" for ch in children) or re.search(
                r"odmian|conjug", heading, re.I
            ):
                nb["heading"] = heading or "Odmiana"
                nb["collapsed"] = True
                nb["semantic"] = "conjugation"
            answer.append(nb)
            continue
        if btype == "table":
            sec = _empty_block("section")
            sec["heading"] = "Odmiana"
            sec["collapsed"] = True
            sec["semantic"] = "conjugation"
            sec["children"] = [b]
            answer.append(sec)
            continue
        if btype in {"chip", "meta"} and text:
            answer.append(b)
            continue
        if btype == "bilingual":
            answer.append(b)
            continue
        if text:
            answer.append(b)

    if moved_meta:
        insert_at = 1 if answer and answer[0].get("type") == "gloss" else 0
        for chip in moved_meta:
            answer.insert(insert_at, chip)
            insert_at += 1

    if not meanings_done and len(note) >= 2:
        cand = strip_html(note[1])
        if cand and "\n" in cand and len(strip_html(note[0])) <= 40:
            if not any(a.get("semantic") == "translation" for a in answer):
                # Avoid dumping conjugation wall into meanings
                if "<table" not in (note[1] or "").lower():
                    _emit_meanings(cand)
                else:
                    # Prefer first lines before 'Gerundio' / Presente
                    cut = re.split(r"(?i)\b(Gerundio|Presente|Odmiana)\b", cand, maxsplit=1)[0]
                    if cut.strip():
                        _emit_meanings(cut.strip())

    has_conj = any(
        (b.get("semantic") == "conjugation")
        or (
            b.get("type") == "section"
            and any(ch.get("type") == "table" for ch in (b.get("children") or []))
        )
        for b in answer
    )
    if not has_conj and note:
        for idx in range(len(note) - 1, -1, -1):
            raw = note[idx]
            if raw and "<table" in raw.lower():
                tables = html_structure_blocks(raw)
                if tables:
                    sec = _empty_block("section")
                    sec["heading"] = "Odmiana"
                    sec["collapsed"] = True
                    sec["semantic"] = "conjugation"
                    sec["children"] = tables
                    answer.append(sec)
                break

    if len(note) >= 4:
        irreg = strip_html(note[2])
        if _looks_like_irregularity(irreg):
            if not any(_looks_like_irregularity(a.get("text") or "") for a in answer):
                chip = _empty_block("chip")
                chip["text"] = irreg
                chip["size"] = "caption"
                chip["semantic"] = "note"
                insert_at = 1 if answer and answer[0].get("type") == "gloss" else 0
                answer.insert(insert_at, chip)

    if not prompt:
        prompt = list(prompt_blocks)
    prompt, answer = _finalize_blocks(prompt, answer, learning_lang, app_lang)
    return prompt, answer, bidirectional


def _finalize_blocks(
    prompt: list[dict],
    answer: list[dict],
    learning_lang: str,
    app_lang: str,
) -> tuple[list[dict], list[dict]]:
    """Strip Anki sound tags; ensure app TTS on L2 headword + L1 gloss."""

    def scrub(block: dict) -> dict:
        b = dict(block)
        if b.get("text"):
            b["text"] = strip_anki_sound(str(b["text"])).strip() or None
            if b["text"]:
                b["text"] = re.sub(r"[ \t]{2,}", " ", b["text"]).strip()
        if b.get("items"):
            b["items"] = [
                strip_anki_sound(str(x)).strip()
                for x in b["items"]
                if strip_anki_sound(str(x)).strip()
            ] or None
        if b.get("children"):
            b["children"] = [scrub(ch) for ch in b["children"] if isinstance(ch, dict)]
        return b

    prompt = [scrub(b) for b in prompt]
    answer = [scrub(b) for b in answer]

    for b in prompt:
        if not (b.get("text") or "").strip():
            continue
        if b.get("type") in {"headword", "title"} or b.get("semantic") == "headword":
            prev = b.get("tts") if isinstance(b.get("tts"), dict) else {}
            lang = (prev.get("lang") or "").strip() or learning_lang
            b["tts"] = {"enabled": True, "lang": lang}
    for b in answer:
        if not (b.get("text") or "").strip():
            continue
        if b.get("type") == "gloss" or b.get("semantic") == "translation":
            prev = b.get("tts") if isinstance(b.get("tts"), dict) else {}
            lang = (prev.get("lang") or "").strip() or app_lang
            b["tts"] = {"enabled": True, "lang": lang}

    prompt = [b for b in prompt if (b.get("text") or b.get("children") or b.get("rows") or b.get("items") or b.get("type") == "divider")]
    answer = [b for b in answer if (b.get("text") or b.get("children") or b.get("rows") or b.get("items") or b.get("type") == "divider")]
    return prompt, answer


def _card_key(note: list[str], index: int) -> str:
    raw = "\x1f".join(note)
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"n{index}_{digest}"


def _conjugation_deck_template(deck: RawImportDeck, learning_lang: str) -> dict | None:
    """Deterministic layout for Spanish/Meanings/Irregularity/Conjugation decks."""
    names = [((n or "").lower()) for n in (deck.field_names or [])]
    is_named = (
        any("spanish" in n for n in names)
        and any("meaning" in n for n in names)
        and any("conjug" in n for n in names)
    )
    is_shaped = False
    if deck.notes and len(deck.notes[0]) >= 4:
        last = deck.notes[0][-1]
        is_shaped = "<table" in last.lower() or "gerundio" in last.lower()
    if not (is_named or is_shaped):
        return None
    # Index mapping
    nfields = len(deck.field_names) if deck.field_names else len(deck.notes[0])
    idxs = list(range(nfields))
    spanish_i, meanings_i, irreg_i, conj_i = 0, 1, 2, 3
    if deck.field_names:
        for i, n in enumerate(names):
            if "spanish" in n or n in {"front", "lemma"}:
                spanish_i = i
            elif "meaning" in n:
                meanings_i = i
            elif "irreg" in n or "obocz" in n:
                irreg_i = i
            elif "conjug" in n or "odmian" in n:
                conj_i = i

    def blk(type_: str, **kwargs: Any) -> dict:
        b = _empty_block(type_)
        b.update(kwargs)
        return b

    roles = []
    role_map = {
        spanish_i: "prompt",
        meanings_i: "answer",
        irreg_i: "meta",
        conj_i: "detail",
    }
    for i in idxs:
        name = deck.field_names[i] if deck.field_names and i < len(deck.field_names) else None
        roles.append({"index": i, "name": name, "role": role_map.get(i, "ignore")})

    return {
        "prompt_style": "word",
        "field_roles": roles,
        "prompt_blocks": [
            blk(
                "headword",
                field_index=spanish_i,
                align="center",
                size="lemma",
                semantic="headword",
                tts={"enabled": True, "lang": learning_lang},
            )
        ],
        "answer_blocks": [
            blk(
                "gloss",
                field_index=meanings_i,
                size="gloss",
                semantic="translation",
                align="center",
            ),
            blk("chip", field_index=irreg_i, size="caption", semantic="note"),
            blk(
                "section",
                heading="Odmiana",
                collapsed=True,
                semantic="conjugation",
                field_index=conj_i,
                children=[],
            ),
        ],
        "answer_needs_structure": False,
        "bidirectional": True,
        "rationale": "deterministyczny layout decku conjugations (Spanish/Meanings/Irregularity/Conjugation)",
    }


def _mock_display_analysis(deck: RawImportDeck) -> dict:
    det = _conjugation_deck_template(deck, learning_lang="es")
    if det is not None:
        return det
    nfields = 0
    if deck.field_names:
        nfields = len(deck.field_names)
    elif deck.notes:
        nfields = max(len(n) for n in deck.notes)
    roles = []
    for i in range(nfields):
        name = deck.field_names[i] if deck.field_names and i < len(deck.field_names) else None
        if nfields == 1:
            role = "prompt"
        elif i == 0:
            role = "prompt"
        elif i == 1:
            role = "answer"
        else:
            role = "detail"
        # named heuristics
        if name:
            nl = name.lower()
            if any(x in nl for x in ("spanish", "front", "term", "lemma", "l2")):
                role = "prompt"
            elif any(x in nl for x in ("polish", "back", "def", "gloss", "l1", "meaning")):
                role = "answer"
            elif any(x in nl for x in ("tiempo", "tense", "tag", "irreg")):
                role = "meta"
            elif "example" in nl or "przyklad" in nl:
                role = "example"
            elif "conjug" in nl or "odmian" in nl:
                role = "detail"
        roles.append({"index": i, "name": name, "role": role})

    prompt_idx = next((r["index"] for r in roles if r["role"] == "prompt"), 0)
    answer_idx = next((r["index"] for r in roles if r["role"] == "answer"), min(1, max(0, nfields - 1)))
    meta_idxs = [r["index"] for r in roles if r["role"] == "meta"]
    example_idxs = [r["index"] for r in roles if r["role"] == "example"]
    detail_idxs = [r["index"] for r in roles if r["role"] == "detail"]

    prompt_blocks: list[dict] = []
    tb = _empty_block("headword")
    tb["field_index"] = prompt_idx
    tb["emphasis"] = "lemma"
    tb["align"] = "center"
    tb["size"] = "lemma"
    tb["semantic"] = "headword"
    prompt_blocks.append(tb)

    answer_blocks: list[dict] = []
    ab = _empty_block("gloss")
    ab["field_index"] = answer_idx
    ab["emphasis"] = "gloss"
    ab["size"] = "gloss"
    ab["semantic"] = "translation"
    answer_blocks.append(ab)
    for mi in meta_idxs:
        b = _empty_block("chip")
        b["field_index"] = mi
        b["size"] = "caption"
        answer_blocks.append(b)
    if len(example_idxs) >= 2:
        sec = _empty_block("section")
        sec["heading"] = "Przykłady"
        sec["collapsed"] = False
        bi = _empty_block("bilingual")
        bi["l2_field_index"] = example_idxs[0]
        bi["l1_field_index"] = example_idxs[1]
        sec["children"] = [bi]
        answer_blocks.append(sec)
    elif len(example_idxs) == 1:
        sec = _empty_block("section")
        sec["heading"] = "Przykłady"
        sec["collapsed"] = False
        p = _empty_block("paragraph")
        p["field_index"] = example_idxs[0]
        sec["children"] = [p]
        answer_blocks.append(sec)
    for di in detail_idxs:
        sec = _empty_block("section")
        name = roles[di]["name"] if di < len(roles) else None
        sec["heading"] = name or "Odmiana"
        sec["collapsed"] = True
        sample = deck.notes[0][di] if deck.notes and di < len(deck.notes[0]) else ""
        if sample and "<table" in sample.lower():
            pre = _empty_block("table")
        else:
            pre = _empty_block("text")
            pre["split"] = "headings"
        pre["field_index"] = di
        sec["children"] = [pre]
        answer_blocks.append(sec)

    bidirectional = prompt_idx != answer_idx and nfields >= 2

    return {
        "prompt_style": "word",
        "field_roles": roles,
        "prompt_blocks": prompt_blocks,
        "answer_blocks": answer_blocks,
        "answer_needs_structure": bool(detail_idxs) or nfields >= 4,
        "bidirectional": bidirectional,
        "rationale": "mock display layout",
    }


def _answer_text_blob(note: list[str], answer_blocks: list[dict]) -> str:
    parts: list[str] = []
    for spec in answer_blocks:
        if spec.get("field_index") is not None:
            parts.append(_field(note, spec["field_index"]))
        for ch in spec.get("children") or []:
            if isinstance(ch, dict) and ch.get("field_index") is not None:
                parts.append(_field(note, ch["field_index"]))
    return "\n\n".join(p for p in parts if p)


async def resolve_import_display_cards(
    deck: RawImportDeck,
    *,
    app_lang: str,
    learning_lang: str,
    llm: LLMService | None = None,
    max_cards: int | None = None,
) -> dict[str, Any]:
    """Zwraca karty z display.prompt/answer.blocks gotowe do UI.

    max_cards=None → cała talia (bez przycinania).
    """
    service = llm or LLMService()
    deck = await ensure_deck_segmented(
        deck,
        app_lang=app_lang,
        learning_lang=learning_lang,
        llm=service,
    )
    if not deck.notes:
        raise ImportPackageError("Brak notatek do zaimportowania.")

    samples = sample_notes_for_llm(deck, limit=8)

    # Known conjugation deck shape → deterministic template (stable, table-preserving)
    deterministic = _conjugation_deck_template(deck, learning_lang)

    analysis: dict[str, Any]
    if deterministic is not None:
        analysis = deterministic
    elif service.mock:
        analysis = _mock_display_analysis(deck)
    else:
        try:
            analysis = await service.analyze_import_layout(
                native=app_lang,
                learning=learning_lang,
                kind=deck.kind,
                field_names=deck.field_names,
                sample_notes=samples,
                total_notes=len(deck.notes),
            )
        except Exception:
            logger.exception("import layout AI failed — falling back to heuristics")
            analysis = _mock_display_analysis(deck)

    prompt_tmpl = analysis.get("prompt_blocks") or []
    answer_tmpl = analysis.get("answer_blocks") or []
    if not prompt_tmpl:
        # Ultimate fallback: single cleaned text section (never raw HTML).
        analysis = _mock_display_analysis(deck)
        prompt_tmpl = analysis.get("prompt_blocks") or []
        answer_tmpl = analysis.get("answer_blocks") or []
    if not prompt_tmpl:
        raise ImportPackageError("AI nie zwróciło szablonu frontu fiszki.")

    bidirectional = bool(analysis.get("bidirectional", False))

    structure_strategy = "none"
    heading_hints: list[str] = []
    # Skip second AI structure pass when we already have a deterministic / table layout
    if (
        deterministic is None
        and analysis.get("answer_needs_structure")
        and not service.mock
    ):
        blob0 = _answer_text_blob(deck.notes[0], answer_tmpl) if deck.notes else ""
        if len(blob0) >= _COMPLEX_CHARS or "<" in (deck.notes[0][-1] if deck.notes else ""):
            sample_blobs = []
            for n in deck.notes[:3]:
                sample_blobs.append(_answer_text_blob(n, answer_tmpl)[:2500])
            try:
                struct = await service.analyze_import_answer_structure(
                    native=app_lang,
                    learning=learning_lang,
                    samples=sample_blobs,
                )
                structure_strategy = struct.get("strategy") or "paragraphs"
                heading_hints = list(struct.get("heading_hints") or [])
            except Exception:
                logger.exception("import display: answer structure failed")
                structure_strategy = "paragraphs"

    cards: list[dict] = []
    for i, note in enumerate(deck.notes[:max_cards]):
        prompt_blocks = materialize_side(prompt_tmpl, note)
        answer_blocks = materialize_side(answer_tmpl, note)

        # post-process fat single paragraphs
        if structure_strategy in {"paragraphs", "headings", "keep_pre"} and answer_blocks:
            rebuilt: list[dict] = []
            for b in answer_blocks:
                text = (b.get("text") or "").strip()
                if b.get("type") in {"paragraph", "pre", "title"} and len(text) >= _COMPLEX_CHARS:
                    if structure_strategy == "keep_pre":
                        nb = _empty_block("section")
                        nb["heading"] = "Content"
                        nb["collapsed"] = False
                        child = _empty_block("pre")
                        child["text"] = text
                        nb["children"] = [child]
                        rebuilt.append(nb)
                    elif structure_strategy == "headings":
                        rebuilt.extend(_split_headings(text, heading_hints))
                    else:
                        rebuilt.extend(_split_paragraphs(text))
                else:
                    rebuilt.append(b)
            answer_blocks = rebuilt

        prompt_blocks, answer_blocks, refined_bi = _refine_card_blocks(
            prompt_blocks,
            answer_blocks,
            note,
            learning_lang=learning_lang,
            app_lang=app_lang,
        )
        card_bi = bool(refined_bi or bidirectional)

        if not prompt_blocks:
            continue
        lemma = strip_anki_sound(_prompt_label(prompt_blocks))
        gloss = strip_anki_sound(_answer_label(answer_blocks))

        cards.append(
            {
                "key": _card_key(note, i),
                "lemma_l2": lemma[:255],
                "gloss_primary": gloss[:255] if gloss else None,
                "display": {
                    "prompt": {"blocks": prompt_blocks},
                    "answer": {"blocks": answer_blocks},
                    "prompt_style": analysis.get("prompt_style") or "word",
                    "bidirectional": card_bi,
                },
            }
        )

    if not cards:
        raise ImportPackageError("Nie udało się zbudować żadnej fiszki do wyświetlenia.")

    logger.info(
        "import display: %s cards (notes=%s) structure=%s",
        len(cards),
        len(deck.notes),
        structure_strategy,
    )
    return {
        "mode": "preserve",
        "cards": cards,
        "field_roles": analysis.get("field_roles") or [],
        "rationale": analysis.get("rationale") or "",
        "total_notes": len(deck.notes),
    }

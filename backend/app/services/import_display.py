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


def strip_html(value: str) -> str:
    t = unescape(value or "")
    t = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p\s*>", "\n\n", t)
    t = re.sub(r"(?i)</div\s*>", "\n", t)
    t = re.sub(r"(?i)</li\s*>", "\n", t)
    t = _TAG_RE.sub(" ", t)
    t = _WS_RE.sub("\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = _MULTI_NL.sub("\n\n", t)
    return t.strip()


def _field(note: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(note):
        return ""
    return strip_html(note[index] or "")


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

    if btype == "bilingual":
        l2 = _field(note, spec.get("l2_field_index"))
        l1 = _field(note, spec.get("l1_field_index"))
        if not l2 and not l1:
            return None
        # store as text "l2\nl1" + keep bilingual type; renderer uses text lines
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
                children.extend(_expand_split(got, note))
        # also allow section body from field_index
        if spec.get("field_index") is not None:
            raw = _field(note, spec.get("field_index"))
            if raw:
                split = (spec.get("split") or "none") or "none"
                tmp = _empty_block("pre" if len(raw) > 400 else "paragraph")
                tmp["text"] = raw
                tmp["split"] = split
                children.extend(_expand_split(tmp, note))
        if not children and not out["heading"]:
            return None
        out["children"] = children
        if out["collapsed"] is None:
            out["collapsed"] = True
        return out

    text = (spec.get("text") or "").strip()
    if spec.get("field_index") is not None:
        text = _field(note, spec.get("field_index")) or text
    if not text and btype not in {"divider", "section"}:
        return None
    out["text"] = text or None
    return out


def _expand_split(block: dict, note: list[str]) -> list[dict]:
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
        out.extend(_expand_split(block, note))
    return out


def _prompt_label(blocks: list[dict]) -> str:
    for b in blocks:
        if b.get("type") in {"title", "paragraph", "pre"} and (b.get("text") or "").strip():
            return (b["text"] or "").strip()[:120]
        if b.get("type") == "meta" and (b.get("text") or "").strip():
            # keep looking for title
            continue
    metas = [b.get("text") for b in blocks if b.get("type") in {"meta", "chip"} and b.get("text")]
    if metas:
        return str(metas[0])[:120]
    return "Karta"


def _answer_label(blocks: list[dict]) -> str:
    for b in blocks:
        if b.get("type") in {"title", "paragraph"} and (b.get("text") or "").strip():
            return (b["text"] or "").strip()[:120]
        if b.get("type") == "bilingual" and (b.get("items") or [None])[0]:
            return str(b["items"][0])[:120]
        if b.get("type") == "section":
            for ch in b.get("children") or []:
                if (ch.get("text") or "").strip():
                    return (ch["text"] or "").strip()[:120]
    return ""


def _card_key(note: list[str], index: int) -> str:
    raw = "\x1f".join(note)
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"n{index}_{digest}"


def _mock_display_analysis(deck: RawImportDeck) -> dict:
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
            role = "prompt" if nfields == 2 else "meta"
        elif i == 1:
            role = "answer" if nfields == 2 else "prompt"
        elif i == 2:
            role = "answer"
        else:
            role = "detail"
        # named heuristics
        if name:
            nl = name.lower()
            if any(x in nl for x in ("spanish", "front", "term", "lemma", "l2")):
                role = "prompt"
            elif any(x in nl for x in ("polish", "back", "def", "gloss", "l1")):
                role = "answer"
            elif any(x in nl for x in ("tiempo", "tense", "tag")):
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
    for mi in meta_idxs:
        b = _empty_block("meta")
        b["field_index"] = mi
        prompt_blocks.append(b)
    tb = _empty_block("title")
    tb["field_index"] = prompt_idx
    tb["emphasis"] = "lemma"
    prompt_blocks.append(tb)

    answer_blocks: list[dict] = []
    ab = _empty_block("title")
    ab["field_index"] = answer_idx
    ab["emphasis"] = "gloss"
    answer_blocks.append(ab)
    if len(example_idxs) >= 2:
        sec = _empty_block("section")
        sec["heading"] = "Example"
        sec["collapsed"] = False
        bi = _empty_block("bilingual")
        bi["l2_field_index"] = example_idxs[0]
        bi["l1_field_index"] = example_idxs[1]
        sec["children"] = [bi]
        answer_blocks.append(sec)
    elif len(example_idxs) == 1:
        sec = _empty_block("section")
        sec["heading"] = "Example"
        sec["collapsed"] = False
        p = _empty_block("paragraph")
        p["field_index"] = example_idxs[0]
        sec["children"] = [p]
        answer_blocks.append(sec)
    for di in detail_idxs:
        sec = _empty_block("section")
        name = roles[di]["name"] if di < len(roles) else None
        sec["heading"] = name or "Details"
        sec["collapsed"] = True
        pre = _empty_block("pre")
        pre["field_index"] = di
        pre["split"] = "headings"
        sec["children"] = [pre]
        answer_blocks.append(sec)

    return {
        "prompt_style": "word",
        "field_roles": roles,
        "prompt_blocks": prompt_blocks,
        "answer_blocks": answer_blocks,
        "answer_needs_structure": bool(detail_idxs) or nfields >= 4,
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
    max_cards: int = 2000,
) -> dict[str, Any]:
    """Zwraca karty z display.prompt/answer.blocks gotowe do UI."""
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

    if service.mock:
        analysis = _mock_display_analysis(deck)
    else:
        analysis = await service.analyze_import_display(
            native=app_lang,
            learning=learning_lang,
            kind=deck.kind,
            field_names=deck.field_names,
            sample_notes=samples,
            total_notes=len(deck.notes),
        )

    prompt_tmpl = analysis.get("prompt_blocks") or []
    answer_tmpl = analysis.get("answer_blocks") or []
    if not prompt_tmpl:
        raise ImportPackageError("AI nie zwróciło szablonu frontu fiszki.")

    structure_strategy = "none"
    heading_hints: list[str] = []
    if analysis.get("answer_needs_structure") and not service.mock:
        # sprawdź czy odpowiedź to głównie 1–2 grube pola
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

        if not prompt_blocks:
            continue
        lemma = _prompt_label(prompt_blocks)
        gloss = _answer_label(answer_blocks)
        # meta prefix for uniqueness on list (ser appears in many tenses)
        meta_bits = [
            b.get("text")
            for b in prompt_blocks
            if b.get("type") in {"meta", "chip"} and (b.get("text") or "").strip()
        ]
        list_label = lemma
        if meta_bits:
            list_label = f"{meta_bits[0]} · {lemma}"

        cards.append(
            {
                "key": _card_key(note, i),
                "lemma_l2": list_label[:255],
                "gloss_primary": gloss[:255] if gloss else None,
                "display": {
                    "prompt": {"blocks": prompt_blocks},
                    "answer": {"blocks": answer_blocks},
                    "prompt_style": analysis.get("prompt_style") or "word",
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

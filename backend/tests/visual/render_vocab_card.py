"""HTML/PNG render for vocabulario.card.v1 (enriched dictionary cards)."""

from __future__ import annotations

import html
from typing import Any

from tests.visual.render_card import _esc


def vocab_card_to_html(content: dict, *, source: str, index: int, lemma: str | None = None) -> str:
    lemma_t = lemma or content.get("lemma") or "?"
    pos = content.get("pos") or ""
    ipa = content.get("ipa") or ""
    meanings = [m for m in (content.get("meanings") or []) if isinstance(m, dict)]
    syns = content.get("synonyms_l2") or []
    conj = content.get("conjugation") or {}

    meaning_html = []
    for i, m in enumerate(meanings[:3]):
        gloss = (m.get("gloss_l1") or "").strip()
        usages = [u for u in (m.get("usages") or []) if str(u).strip()][:2]
        examples = [e for e in (m.get("examples") or []) if isinstance(e, dict)][:2]
        parts = [f'<div class="gloss">{_esc(gloss)}</div>']
        for u in usages:
            parts.append(f'<div class="usage">{_esc(u)}</div>')
        for ex in examples:
            l2 = (ex.get("l2") or "").strip()
            l1 = (ex.get("l1") or "").strip()
            parts.append(
                '<div class="ex">'
                f'<div class="ex-l2">{_esc(l2)}</div>'
                f'<div class="ex-l1">{_esc(l1)}</div>'
                "</div>"
            )
        meaning_html.append(
            f'<section class="meaning"><div class="m-label">Znaczenie {i+1}</div>{"".join(parts)}</section>'
        )

    syn_bits = []
    for s in syns[:6]:
        if isinstance(s, dict):
            syn_bits.append(_esc(s.get("lemma") or s.get("word") or ""))
        else:
            syn_bits.append(_esc(s))
    syn_html = ""
    if syn_bits:
        syn_html = (
            '<section class="syn"><div class="m-label">Synonimy L2</div>'
            f'<div class="syn-list">{", ".join(x for x in syn_bits if x)}</div></section>'
        )

    conj_html = ""
    if isinstance(conj, dict) and conj:
        # Show a compact preview of first tense tables
        rows_out = []
        for tense, forms in list(conj.items())[:3]:
            if isinstance(forms, dict):
                cells = " · ".join(
                    f"{_esc(k)}: {_esc(v)}" for k, v in list(forms.items())[:4] if v
                )
            elif isinstance(forms, list):
                cells = " · ".join(_esc(str(x)) for x in forms[:4])
            else:
                cells = _esc(forms)
            if cells:
                rows_out.append(f"<div><b>{_esc(tense)}</b> — {cells}</div>")
        if rows_out:
            conj_html = (
                '<details class="section" open><summary>Odmiana (fragment)</summary>'
                f'<div class="section-body">{"".join(rows_out)}</div></details>'
            )

    if not meaning_html:
        meaning_html = ['<p class="muted">Brak znaczeń</p>']

    meta = f"source={source} · vocabulario #{index + 1} · schema={content.get('schema_version')}"
    return f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8" />
<title>{_esc(lemma_t)}</title>
<style>
:root {{ --bg:#f6f4ef; --card:#fff; --ink:#1c1917; --muted:#78716c; --line:#e7e5e4; --accent:#0f766e; --chip:#ecfccb; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--ink); padding:16px; }}
.frame {{ width:390px; margin:0 auto; background:var(--card); border:1px solid var(--line); border-radius:18px; overflow:hidden; }}
.badge {{ background:#ecfccb; color:#3f6212; font-size:11px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; padding:8px 14px; }}
.meta {{ font-size:11px; color:var(--muted); padding:8px 14px; border-bottom:1px solid var(--line); word-break:break-all; }}
.head {{ padding:14px 16px 10px; border-bottom:1px solid var(--line); text-align:center; }}
.head .lemma {{ font-size:28px; font-weight:700; margin:0; }}
.head .pos {{ color:var(--muted); font-size:13px; margin-top:4px; }}
.head .ipa {{ color:var(--accent); font-size:13px; margin-top:2px; }}
.body {{ padding:12px 16px 18px; }}
.meaning {{ margin:0 0 12px; padding:10px; border:1px solid var(--line); border-radius:12px; }}
.m-label {{ font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--accent); font-weight:700; margin-bottom:6px; }}
.gloss {{ font-size:18px; font-weight:600; margin-bottom:6px; }}
.usage {{ font-size:13px; color:var(--muted); margin:2px 0; }}
.ex {{ margin-top:8px; padding-top:8px; border-top:1px dashed var(--line); }}
.ex-l2 {{ font-weight:600; font-size:14px; }}
.ex-l1 {{ color:var(--muted); font-size:13px; }}
.syn {{ margin:0 0 12px; }}
.syn-list {{ font-size:13px; }}
.section {{ margin-top:8px; border:1px solid var(--line); border-radius:10px; padding:8px 10px; }}
.section summary {{ color:var(--accent); font-weight:700; font-size:13px; cursor:pointer; }}
.section-body {{ margin-top:8px; font-size:12px; line-height:1.45; }}
.muted {{ color:var(--muted); }}
</style></head>
<body>
<div class="frame" id="card">
  <div class="badge">Vocabulario</div>
  <div class="meta">{_esc(meta)}</div>
  <div class="head">
    <p class="lemma">{_esc(lemma_t)} 🔊</p>
    <div class="pos">{_esc(pos)}</div>
    <div class="ipa">{_esc(ipa)}</div>
  </div>
  <div class="body">
    {"".join(meaning_html)}
    {syn_html}
    {conj_html}
  </div>
</div>
</body></html>
"""


def placeholder_html(*, source: str, reason: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8" />
<title>brak</title>
<style>
body {{ margin:0; font-family:system-ui,sans-serif; background:#f6f4ef; padding:16px; }}
.frame {{ width:390px; margin:0 auto; background:#fff; border:1px dashed #d6d3d1; border-radius:18px; padding:24px; text-align:center; }}
.badge {{ display:inline-block; background:#f5f5f4; color:#78716c; font-size:11px; font-weight:700; text-transform:uppercase; padding:6px 10px; border-radius:999px; }}
h1 {{ font-size:18px; margin:16px 0 8px; }}
p {{ color:#78716c; font-size:13px; margin:0; }}
</style></head>
<body>
<div class="frame" id="card">
  <div class="badge">Vocabulario</div>
  <h1>Brak karty</h1>
  <p>{html.escape(source)}</p>
  <p style="margin-top:8px">{html.escape(reason)}</p>
</div>
</body></html>
"""


def card_dict_from_enrichment(content: dict, *, key: str) -> dict[str, Any]:
    meanings = content.get("meanings") or []
    gloss = None
    if meanings and isinstance(meanings[0], dict):
        gloss = meanings[0].get("gloss_l1")
    return {
        "key": key,
        "lemma_l2": content.get("lemma") or key,
        "gloss_primary": gloss,
        "mode": "vocabulario",
        "content": content,
    }

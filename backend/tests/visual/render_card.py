"""Render import display cards to HTML + PNG for visual inspection."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _block_html(block: dict, depth: int = 0) -> str:
    btype = (block.get("type") or "text").strip()
    align = block.get("align") or "start"
    size = block.get("size") or ""
    text = (block.get("text") or "").strip()
    heading = (block.get("heading") or "").strip()
    align_cls = "align-center" if align == "center" else "align-start"
    size_cls = f"size-{size}" if size else ""

    if btype in {"chip", "meta", "note"}:
        if not text:
            return ""
        return f'<span class="chip {_esc(size_cls)}">{_esc(text)}</span>'

    if btype in {"headword", "title", "gloss"}:
        if not text:
            return ""
        tag = "h1" if btype == "headword" or size == "lemma" else "h2"
        tts = block.get("tts") or {}
        tts_badge = ""
        if isinstance(tts, dict) and tts.get("enabled"):
            tts_badge = ' <span class="tts" title="TTS">🔊</span>'
        return (
            f'<{tag} class="block-{_esc(btype)} {_esc(align_cls)} {_esc(size_cls)}">'
            f"{_esc(text)}{tts_badge}</{tag}>"
        )

    if btype in {"text", "paragraph", "pre"}:
        if not text:
            return ""
        cls = "mono" if btype == "pre" else "body"
        return f'<p class="{cls} {_esc(align_cls)} {_esc(size_cls)}">{_esc(text)}</p>'

    if btype == "bilingual":
        l2 = text
        l1 = (block.get("items") or [None])[0]
        parts = []
        if l2:
            parts.append(f'<div class="bi-l2">{_esc(l2)}</div>')
        if l1:
            parts.append(f'<div class="bi-l1">{_esc(l1)}</div>')
        return f'<div class="bilingual {_esc(align_cls)}">{"".join(parts)}</div>'

    if btype == "list":
        items = [i for i in (block.get("items") or []) if str(i).strip()]
        if not items:
            return ""
        lis = "".join(f"<li>{_esc(i)}</li>" for i in items)
        return f'<ul class="list">{lis}</ul>'

    if btype == "table":
        headers = block.get("headers") or []
        rows = block.get("rows") or []
        if not headers and not rows:
            return ""
        thead = ""
        if headers:
            cells = "".join(f"<th>{_esc(h)}</th>" for h in headers)
            thead = f"<thead><tr>{cells}</tr></thead>"
        body_rows = []
        for row in rows:
            cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
            body_rows.append(f"<tr>{cells}</tr>")
        tbody = f"<tbody>{''.join(body_rows)}</tbody>" if body_rows else ""
        return f'<div class="table-wrap"><table>{thead}{tbody}</table></div>'

    if btype == "divider":
        return '<hr class="divider" />'

    if btype == "section":
        collapsed = block.get("collapsed")
        open_attr = "" if collapsed is False else ""
        # Always show expanded in screenshots so conjugation is visible
        children = "".join(_block_html(ch, depth + 1) for ch in (block.get("children") or []))
        title = heading or "Section"
        return (
            f'<details class="section" open>'
            f"<summary>{_esc(title)}</summary>"
            f'<div class="section-body">{children}</div>'
            f"</details>"
        )

    if text:
        return f'<p class="body {_esc(align_cls)}">{_esc(text)}</p>'
    return ""


def _side_html(side: dict | None, label: str) -> str:
    blocks = (side or {}).get("blocks") or []
    inner = "".join(_block_html(b) for b in blocks)
    if not inner.strip():
        inner = '<p class="muted">Brak bloków</p>'
    return f'<section class="side"><div class="side-label">{_esc(label)}</div>{inner}</section>'


def card_to_html(card: dict, *, source: str, index: int) -> str:
    display = card.get("display") or {}
    lemma = card.get("lemma_l2") or ""
    gloss = card.get("gloss_primary") or ""
    bidirectional = display.get("bidirectional")
    style = display.get("prompt_style") or ""
    meta = (
        f"source={source} · #{index + 1} · style={style} · "
        f"bidirectional={bidirectional} · key={card.get('key', '')}"
    )
    badge = ""
    if "[preserve]" in source.lower() or "preserve" in (card.get("mode") or "").lower():
        badge = '<div class="badge">Preserve</div>'
    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(lemma)}</title>
  <style>
    :root {{
      --bg: #f6f4ef;
      --card: #ffffff;
      --ink: #1c1917;
      --muted: #78716c;
      --line: #e7e5e4;
      --accent: #0f766e;
      --chip: #ccfbf1;
      --chip-ink: #115e59;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--ink);
      padding: 16px;
    }}
    .frame {{
      width: 390px;
      margin: 0 auto;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
    }}
    .badge {{
      background: #e0f2fe;
      color: #075985;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
      padding: 8px 14px;
    }}
    .meta {{
      font-size: 11px;
      color: var(--muted);
      padding: 10px 14px;
      border-bottom: 1px solid var(--line);
      word-break: break-all;
    }}
    .lemma-bar {{
      padding: 14px 16px 8px;
      border-bottom: 1px solid var(--line);
    }}
    .lemma-bar .lemma {{
      font-size: 22px;
      font-weight: 700;
      margin: 0;
    }}
    .lemma-bar .gloss {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .side {{
      padding: 14px 16px 18px;
    }}
    .side + .side {{
      border-top: 8px solid var(--bg);
    }}
    .side-label {{
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--accent);
      font-weight: 700;
      margin-bottom: 10px;
    }}
    h1, h2 {{
      margin: 0 0 8px;
      line-height: 1.2;
    }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 20px; font-weight: 600; }}
    .align-center {{ text-align: center; }}
    .size-lemma {{ font-size: 28px; font-weight: 700; }}
    .size-gloss {{ font-size: 20px; font-weight: 600; }}
    .size-caption {{ font-size: 12px; color: var(--muted); }}
    .body {{ margin: 0 0 8px; font-size: 15px; line-height: 1.45; white-space: pre-wrap; }}
    .mono {{
      margin: 0 0 8px;
      font-family: ui-monospace, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
      color: var(--muted);
    }}
    .chip {{
      display: inline-block;
      background: var(--chip);
      color: var(--chip-ink);
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 12px;
      font-weight: 600;
      margin: 0 6px 8px 0;
    }}
    .tts {{
      font-size: 14px;
      margin-left: 6px;
      opacity: 0.7;
    }}
    .bilingual {{ margin: 0 0 10px; }}
    .bi-l2 {{ font-weight: 600; font-size: 15px; }}
    .bi-l1 {{ color: var(--muted); font-size: 14px; margin-top: 2px; }}
    .list {{ margin: 0 0 10px; padding-left: 18px; }}
    .list li {{ margin: 3px 0; }}
    .table-wrap {{
      overflow-x: auto;
      margin: 0 0 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 12px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 6px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #fafaf9; color: var(--muted); font-weight: 700; }}
    .section {{
      margin: 0 0 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 10px;
    }}
    .section summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: 700;
      font-size: 13px;
    }}
    .section-body {{ margin-top: 8px; }}
    .divider {{ border: 0; border-top: 1px solid var(--line); margin: 10px 0; }}
    .muted {{ color: var(--muted); }}
  </style>
</head>
<body>
  <div class="frame" id="card">
    {badge}
    <div class="meta">{_esc(meta)}</div>
    <div class="lemma-bar">
      <p class="lemma">{_esc(lemma)}</p>
      <p class="gloss">{_esc(gloss)}</p>
    </div>
    {_side_html(display.get("prompt"), "Front (prompt)")}
    {_side_html(display.get("answer"), "Back (answer)")}
  </div>
</body>
</html>
"""


def write_card_html(card: dict, out_html: Path, *, source: str, index: int) -> Path:
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(card_to_html(card, source=source, index=index), encoding="utf-8")
    return out_html


def screenshot_html(html_path: Path, png_path: Path) -> Path:
    """Render HTML file to PNG via Playwright Chromium."""
    from playwright.sync_api import sync_playwright

    png_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": 430, "height": 900},
            device_scale_factor=2,
        )
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        # Full card frame — grow with content
        card = page.locator("#card")
        card.screenshot(path=str(png_path))
        browser.close()
    return png_path


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^\w\-]+", "_", value.strip(), flags=re.UNICODE)
    return value.strip("_")[:60] or "card"


def write_index(
    artifact_dir: Path,
    rows: list[dict],
    *,
    title: str = "Import — podgląd kart",
    summary_extra: str = "",
) -> Path:
    """Gallery grouped by source file — one horizontal row of cards per file."""
    from collections import OrderedDict

    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for row in rows:
        source = str(row.get("source") or "").strip()
        if not source:
            title_row = str(row.get("title") or "")
            source = title_row.split(" · ", 1)[0].strip() if " · " in title_row else "other"
        groups.setdefault(source, []).append(row)

    sections = []
    for source, items in groups.items():
        figures = []
        for row in items:
            caption = str(row.get("title") or "")
            if caption.startswith(source):
                caption = caption[len(source) :].lstrip(" ·")
            figures.append(
                "<figure>"
                f"<img src='{_esc(Path(row['png']).name)}' alt='{_esc(row.get('title', ''))}' />"
                f"<figcaption>{_esc(caption)}<br/><small>{_esc(row.get('meta', ''))}</small></figcaption>"
                "</figure>"
            )
        sections.append(
            "<section class='file-row'>"
            f"<h2>{_esc(source)} <span>({len(items)})</span></h2>"
            f"<div class='row'>{''.join(figures)}</div>"
            "</section>"
        )

    summary = f"{len(rows)} kart · {len(groups)} plików"
    if summary_extra:
        summary = f"{summary} · {summary_extra}"

    doc = f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8" />
<title>{_esc(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #f5f5f4; margin: 0; padding: 24px; color: #1c1917; }}
h1 {{ margin: 0 0 8px; font-size: 22px; }}
.summary {{ color: #78716c; margin: 0 0 28px; font-size: 14px; }}
.file-row {{ margin: 0 0 32px; }}
.file-row h2 {{
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 700;
  padding-bottom: 8px;
  border-bottom: 1px solid #e7e5e4;
}}
.file-row h2 span {{ color: #a8a29e; font-weight: 500; }}
.row {{
  display: flex;
  flex-wrap: nowrap;
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 8px;
}}
figure {{
  margin: 0;
  background: #fff;
  border: 1px solid #e7e5e4;
  border-radius: 12px;
  overflow: hidden;
  flex: 0 0 320px;
  max-width: 320px;
}}
img {{ width: 100%; display: block; background: #fafaf9; }}
figcaption {{ padding: 10px 12px; font-size: 13px; word-break: break-word; }}
small {{ color: #78716c; }}
</style></head>
<body>
<h1>{_esc(title)}</h1>
<p class="summary">{_esc(summary)}</p>
{"".join(sections)}
</body></html>
"""
    out = artifact_dir / "index.html"
    out.write_text(doc, encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return out

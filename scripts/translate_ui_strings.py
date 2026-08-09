"""Tłumaczenie values-en/strings.xml → nowe locale (partiami, tanio)."""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openai import AsyncOpenAI  # noqa: E402

from app.core.config import get_settings  # noqa: E402

SOURCE = ROOT / "android/app/src/main/res/values-en/strings.xml"
RES = ROOT / "android/app/src/main/res"
BATCH = 80
MODEL = "gpt-4o-mini"

LANGS = {
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "tr": "Turkish",
    "vi": "Vietnamese",
}

STRING_RE = re.compile(
    r'<string\s+name="([^"]+)"(?:\s+[^>]*)?>(.*?)</string>',
    re.DOTALL,
)


def parse_strings(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    return [(m.group(1), m.group(2)) for m in STRING_RE.finditer(text)]


def build_xml(entries: list[tuple[str, str]]) -> str:
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "", "<resources>", ""]
    for name, value in entries:
        safe = (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "\\'")
        )
        # restore android placeholders
        safe = safe.replace("&amp;lt;", "&lt;").replace("&amp;gt;", "&gt;")
        lines.append(f'    <string name="{name}">{safe}</string>')
        lines.append("")
    lines.append("</resources>")
    lines.append("")
    return "\n".join(lines)


async def translate_batch(
    client: AsyncOpenAI,
    lang_code: str,
    lang_name: str,
    batch: dict[str, str],
) -> dict[str, str]:
    prompt = (
        f"Translate Android UI strings to {lang_name} ({lang_code}).\n"
        "Rules:\n"
        "- Keep JSON keys unchanged.\n"
        "- Keep placeholders exactly: %1$s, %1$d, %2$s, etc.\n"
        "- Keep brand name Vocabulario.\n"
        "- Natural app UI tone, concise.\n"
        "- Return ONLY JSON object key→translation.\n\n"
        + json.dumps(batch, ensure_ascii=False)
    )
    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a professional UI translator."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    usage = resp.usage
    tok = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
    return data, tok


async def translate_lang(client: AsyncOpenAI, lang_code: str, lang_name: str, items: list[tuple[str, str]]) -> int:
    translated: dict[str, str] = {}
    total_tok = 0
    for i in range(0, len(items), BATCH):
        chunk = dict(items[i : i + BATCH])
        result, tok = await translate_batch(client, lang_code, lang_name, chunk)
        translated.update(result)
        total_tok += tok
        print(f"  {lang_code}: batch {i // BATCH + 1}, keys={len(chunk)}, tok≈{tok}", flush=True)

    ordered = [(k, translated.get(k, v)) for k, v in items]
    missing = [k for k, v in ordered if k not in translated]
    if missing:
        print(f"  WARN {lang_code}: missing {len(missing)} keys, keeping English", flush=True)

    out_dir = RES / f"values-{lang_code}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "strings.xml"
    out_path.write_text(build_xml(ordered), encoding="utf-8")
    print(f"  Wrote {out_path} ({len(ordered)} strings)", flush=True)
    return total_tok


async def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        print("Brak OPENAI_API_KEY")
        sys.exit(1)
    items = parse_strings(SOURCE)
    print(f"Source: {len(items)} strings from {SOURCE.name}", flush=True)
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    grand = 0
    for code, name in LANGS.items():
        print(f"\n=== {code} ({name}) ===", flush=True)
        grand += await translate_lang(client, code, name, items)
    print(f"\nŁącznie tokenów (szac.): {grand}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

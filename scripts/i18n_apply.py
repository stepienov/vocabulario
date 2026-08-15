#!/usr/bin/env python3
"""Wstawia brakujące klucze i podmienia skopiowany EN w strings.xml.

Źródło kluczy: values/strings.xml
Tłumaczenia: scripts/i18n_pack.json
values-en = kopia values/
Nie nadpisuje już przetłumaczonych wartości. Nie przepisuje całego pliku.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import unescape

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "android" / "app" / "src" / "main" / "res"
BASE = RES / "values" / "strings.xml"
PACK_PATH = ROOT / "scripts" / "i18n_pack.json"
STRING_RE = re.compile(r'<string name="([^"]+)">(.*?)</string>', re.S)
BLOCK_RE = re.compile(
    r'[ \t]*<string name="([^"]+)">.*?</string>\s*',
    re.S,
)

ALLOW_EN_COPY = {
    "app_name",
    "action_ok",
    "sort_lemma_asc",
    "sort_lemma_desc",
    "card_history_diff_ipa",
    "voice_start",
    "voice_stop",
    "settings_mode_choice",
    "card_history_actor_system",
}

LOCALE_TO_PACK = {
    "values-es": "es",
    "values-fr": "fr",
    "values-de": "de",
    "values-it": "it",
    "values-pt-rBR": "pt-br",
    "values-pt-rPT": "pt-pt",
    "values-zh": "zh",
    "values-ja": "ja",
    "values-ko": "ko",
    "values-ar": "ar",
    "values-ru": "ru",
    "values-hi": "hi",
    "values-tr": "tr",
    "values-vi": "vi",
}

DEAD_EXTRA = {
    "review_status_accepted",
    "review_status_rejected",
    "review_status_reported",
    "review_status_user_edited",
}


def parse(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in STRING_RE.finditer(text):
        out[m.group(1)] = unescape(m.group(2).replace("\\'", "'").replace('\\"', '"'))
    return out


def escape_android(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', '\\"')
        .replace("'", "\\'")
    )


def xml_entry(key: str, value: str) -> str:
    return f'    <string name="{key}">{escape_android(value)}</string>\n'


def main() -> int:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    en = parse(BASE)
    errors: list[str] = []

    shutil.copyfile(BASE, RES / "values-en" / "strings.xml")
    print("synced values-en <- values/")

    for folder, lang in LOCALE_TO_PACK.items():
        path = RES / folder / "strings.xml"
        text = path.read_text(encoding="utf-8")
        current = parse(path)
        trans = pack[lang]
        replaced = 0
        inserted = 0

        def replacer(match: re.Match[str]) -> str:
            nonlocal replaced
            key = match.group(1)
            if key in DEAD_EXTRA:
                return ""
            existing = current.get(key)
            is_en_copy = existing == en.get(key) and key not in ALLOW_EN_COPY
            if is_en_copy:
                value = trans.get(key)
                if not value:
                    errors.append(f"{folder}: brak tłumaczenia {key}")
                    return match.group(0)
                replaced += 1
                return xml_entry(key, value)
            return match.group(0)

        text = BLOCK_RE.sub(replacer, text)

        missing = [k for k in en if k not in current]
        if missing:
            additions = []
            for key in missing:
                value = trans.get(key)
                if not value:
                    if key in ALLOW_EN_COPY:
                        value = en[key]
                    else:
                        errors.append(f"{folder}: brak tłumaczenia {key}")
                        value = en[key]
                additions.append(xml_entry(key, value).rstrip("\n"))
                inserted += 1
            block = "\n".join(additions) + "\n"
            if "</resources>" not in text:
                errors.append(f"{folder}: brak </resources>")
            else:
                text = text.replace("</resources>", block + "\n</resources>", 1)

        path.write_text(text, encoding="utf-8")
        print(f"{folder}: replaced {replaced}, inserted {inserted}")

    if errors:
        print("BŁĘDY:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

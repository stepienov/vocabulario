"""Dump i18n gaps as JSON for filling translations."""
from __future__ import annotations

import json
import re
from pathlib import Path
from xml.sax.saxutils import unescape

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "android" / "app" / "src" / "main" / "res"
STRING_RE = re.compile(r'<string name="([^"]+)">(.*?)</string>', re.S)

ALLOW = {
    "app_name",
    "action_ok",
    "sort_lemma_asc",
    "sort_lemma_desc",
    "card_history_diff_ipa",
    "voice_start",
    "voice_stop",
    "settings_mode_choice",
    "card_history_actor_system",
    # Cognates / loanwords that match EN in some locale by design
    "action_filter_active",
    "filter_title",
    "auth_email",
    "auth_password",
    "list_name_hint",
    "import_file_label",
    "status_error",
    "kind_construction",
    "section_fallback",
    "correction_section_lemma",
    "correction_note_label",
    "correction_field_notes",
    "correction_field_lemma",
    "settings_notifications",
    "card_history_diff_lemma",
}


def parse(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in STRING_RE.finditer(text):
        out[m.group(1)] = unescape(m.group(2).replace("\\'", "'").replace('\\"', '"'))
    return out


def key_order(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return STRING_RE.findall(text) and [m.group(1) for m in STRING_RE.finditer(text)]


def main() -> None:
    base_path = RES / "values" / "strings.xml"
    en = parse(base_path)
    pl = parse(RES / "values-pl" / "strings.xml")
    order = key_order(base_path)

    need: set[str] = set()
    locales = []
    for d in sorted(RES.glob("values*/strings.xml")):
        loc = d.parent.name
        if loc in ("values", "values-pl", "values-en"):
            continue
        data = parse(d)
        locales.append(loc)
        need.update(set(en) - set(data))
        for k in set(en) & set(data):
            if k in ALLOW:
                continue
            if data[k] == en[k]:
                need.add(k)

    catalog = []
    for k in order:
        if k not in need:
            continue
        catalog.append({"key": k, "en": en[k], "pl": pl.get(k, "")})

    out = ROOT / "docs" / "_i18n_gaps.json"
    out.write_text(
        json.dumps({"locales": locales, "keys": catalog}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"keys needing translation: {len(catalog)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

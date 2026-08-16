#!/usr/bin/env python3
"""Uzupełnia ui_labels w manifestach LSP, audyt MD i fallback Android."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LSP = ROOT / "backend" / "app" / "lsp"
DOCS = ROOT / "docs" / "audyt-etykiet-czasow.md"
KOTLIN = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "vocabulario" / "app" / "data" / "TenseUiLabels.kt"

APP_LANGS = [
    "en", "es", "fr", "de", "it", "pt-br", "pt-pt",
    "zh", "ja", "ko", "ar", "ru", "hi", "tr", "vi", "pl",
]

# learning_lang -> app_lang -> tense_key -> label
# L2 name (label_l2) is always the header; these are translations for the subtitle.
FILL: dict[str, dict[str, dict[str, str]]] = {
    "en": {
        "pl": {
            "present_simple": "Czas teraźniejszy prosty",
            "present_continuous": "Czas teraźniejszy ciągły",
            "present_perfect": "Czas teraźniejszy dokonany",
            "past_simple": "Czas przeszły prosty",
            "past_continuous": "Czas przeszły ciągły",
            "past_perfect": "Czas zaprzeszły",
            "future_will": "Czas przyszły (will)",
            "going_to": "Konstrukcja going to",
            "conditionals": "Okresy warunkowe",
            "ing_form": "Forma -ing",
            "past_participle": "Imiesłów przeszły",
        },
        "es": {
            "present_simple": "Presente simple",
            "present_continuous": "Presente continuo",
            "present_perfect": "Presente perfecto",
            "past_simple": "Pasado simple",
            "past_continuous": "Pasado continuo",
            "past_perfect": "Pasado perfecto",
            "future_will": "Futuro (will)",
            "going_to": "Going to",
            "conditionals": "Condicionales",
            "ing_form": "Forma -ing",
            "past_participle": "Participio pasado",
        },
        "fr": {
            "present_simple": "Présent simple",
            "present_continuous": "Présent continu",
            "present_perfect": "Present perfect",
            "past_simple": "Prétérit",
            "past_continuous": "Passé continu",
            "past_perfect": "Plus-que-parfait",
            "future_will": "Futur (will)",
            "going_to": "Going to",
            "conditionals": "Conditionnels",
            "ing_form": "Forme -ing",
            "past_participle": "Participe passé",
        },
        "de": {
            "present_simple": "Simple Present",
            "present_continuous": "Present Progressive",
            "present_perfect": "Present Perfect",
            "past_simple": "Simple Past",
            "past_continuous": "Past Progressive",
            "past_perfect": "Past Perfect",
            "future_will": "Zukunft (will)",
            "going_to": "Going to",
            "conditionals": "Konditionalsätze",
            "ing_form": "ing-Form",
            "past_participle": "Partizip Perfekt",
        },
        "it": {
            "present_simple": "Presente semplice",
            "present_continuous": "Presente progressivo",
            "present_perfect": "Present perfect",
            "past_simple": "Passato semplice",
            "past_continuous": "Passato progressivo",
            "past_perfect": "Trapassato",
            "future_will": "Futuro (will)",
            "going_to": "Going to",
            "conditionals": "Periodi ipotetici",
            "ing_form": "Forma in -ing",
            "past_participle": "Participio passato",
        },
        "pt-br": {
            "present_simple": "Presente simples",
            "present_continuous": "Presente contínuo",
            "present_perfect": "Presente perfeito",
            "past_simple": "Passado simples",
            "past_continuous": "Passado contínuo",
            "past_perfect": "Passado perfeito",
            "future_will": "Futuro (will)",
            "going_to": "Going to",
            "conditionals": "Condicionais",
            "ing_form": "Forma -ing",
            "past_participle": "Particípio passado",
        },
        "ru": {
            "present_simple": "Настоящее простое",
            "present_continuous": "Настоящее длительное",
            "present_perfect": "Настоящее совершенное",
            "past_simple": "Прошедшее простое",
            "past_continuous": "Прошедшее длительное",
            "past_perfect": "Предпрошедшее",
            "future_will": "Будущее (will)",
            "going_to": "Конструкция going to",
            "conditionals": "Условные предложения",
            "ing_form": "Форма -ing",
            "past_participle": "Причастие прошедшего",
        },
        "zh": {
            "present_simple": "一般现在时",
            "present_continuous": "现在进行时",
            "present_perfect": "现在完成时",
            "past_simple": "一般过去时",
            "past_continuous": "过去进行时",
            "past_perfect": "过去完成时",
            "future_will": "一般将来时（will）",
            "going_to": "be going to",
            "conditionals": "条件句",
            "ing_form": "-ing 形式",
            "past_participle": "过去分词",
        },
        "ja": {
            "present_simple": "現在形",
            "present_continuous": "現在進行形",
            "present_perfect": "現在完了",
            "past_simple": "過去形",
            "past_continuous": "過去進行形",
            "past_perfect": "過去完了",
            "future_will": "未来形（will）",
            "going_to": "going to",
            "conditionals": "条件文",
            "ing_form": "-ing形",
            "past_participle": "過去分詞",
        },
        "ko": {
            "present_simple": "현재 단순",
            "present_continuous": "현재 진행",
            "present_perfect": "현재 완료",
            "past_simple": "과거 단순",
            "past_continuous": "과거 진행",
            "past_perfect": "과거 완료",
            "future_will": "미래 (will)",
            "going_to": "going to",
            "conditionals": "조건문",
            "ing_form": "-ing형",
            "past_participle": "과거분사",
        },
        "ar": {
            "present_simple": "المضارع البسيط",
            "present_continuous": "المضارع المستمر",
            "present_perfect": "المضارع التام",
            "past_simple": "الماضي البسيط",
            "past_continuous": "الماضي المستمر",
            "past_perfect": "الماضي التام",
            "future_will": "المستقبل (will)",
            "going_to": "going to",
            "conditionals": "الجمل الشرطية",
            "ing_form": "صيغة -ing",
            "past_participle": "التصريف الثالث",
        },
        "hi": {
            "present_simple": "सामान्य वर्तमान",
            "present_continuous": "वर्तमान सतत",
            "present_perfect": "पूर्ण वर्तमान",
            "past_simple": "सामान्य भूत",
            "past_continuous": "भूत सतत",
            "past_perfect": "पूर्ण भूत",
            "future_will": "भविष्य (will)",
            "going_to": "going to",
            "conditionals": "शर्त वाक्य",
            "ing_form": "-ing रूप",
            "past_participle": "भूतकालिक कृदंत",
        },
        "tr": {
            "present_simple": "Geniş zaman",
            "present_continuous": "Şimdiki zaman",
            "present_perfect": "Yakın geçmiş",
            "past_simple": "Geçmiş zaman",
            "past_continuous": "Şimdiki zamanın hikâyesi",
            "past_perfect": "Miş’li geçmiş",
            "future_will": "Gelecek (will)",
            "going_to": "going to",
            "conditionals": "Koşul cümleleri",
            "ing_form": "-ing biçimi",
            "past_participle": "Üçüncü hali",
        },
        "vi": {
            "present_simple": "Hiện tại đơn",
            "present_continuous": "Hiện tại tiếp diễn",
            "present_perfect": "Hiện tại hoàn thành",
            "past_simple": "Quá khứ đơn",
            "past_continuous": "Quá khứ tiếp diễn",
            "past_perfect": "Quá khứ hoàn thành",
            "future_will": "Tương lai (will)",
            "going_to": "going to",
            "conditionals": "Câu điều kiện",
            "ing_form": "Dạng -ing",
            "past_participle": "Quá khứ phân từ",
        },
    },
    "es": {
        "pl": {
            "presente": "Czas teraźniejszy",
            "preterito_perfecto": "Czas teraźniejszy dokonany",
            "preterito_indefinido": "Czas przeszły prosty",
            "preterito_imperfecto": "Czas przeszły niedokonany",
            "futuro_simple": "Czas przyszły",
            "condicional_simple": "Tryb warunkowy",
            "presente_subjuntivo": "Tryb łączący — teraźniejszy",
            "imperfecto_subjuntivo": "Tryb łączący — przeszły",
            "futuro_subjuntivo": "Tryb łączący — przyszły",
            "preterito_pluscuamperfecto": "Czas zaprzeszły",
            "condicional_compuesto": "Tryb warunkowy złożony",
            "futuro_perfecto": "Czas przyszły dokonany",
            "imperativo_afirmativo": "Tryb rozkazujący (twierdzący)",
            "imperativo_negativo": "Tryb rozkazujący (przeczący)",
            "gerundio": "Gerundium",
            "participio": "Imiesłów",
        },
    },
    "fr": {
        "pl": {
            "present": "Czas teraźniejszy",
            "passe_compose": "Czas przeszły złożony",
            "imparfait": "Czas przeszły niedokonany",
            "futur_simple": "Czas przyszły",
            "conditionnel": "Tryb warunkowy",
            "subjonctif_present": "Tryb łączący — teraźniejszy",
            "plus_que_parfait": "Czas zaprzeszły",
            "imperatif": "Tryb rozkazujący",
            "infinitif": "Bezokolicznik",
            "participe_passe": "Imiesłów przeszły",
            "gerondif": "Gerundium",
        },
        "en": {
            "present": "Present",
            "passe_compose": "Passé composé",
            "imparfait": "Imperfect",
            "futur_simple": "Simple future",
            "conditionnel": "Conditional",
            "subjonctif_present": "Present subjunctive",
            "plus_que_parfait": "Pluperfect",
            "imperatif": "Imperative",
            "infinitif": "Infinitive",
            "participe_passe": "Past participle",
            "gerondif": "Gerund",
        },
    },
    "de": {
        "pl": {
            "prasens": "Czas teraźniejszy",
            "perfekt": "Czas przeszły złożony",
            "prateritum": "Czas przeszły prosty",
            "futur_i": "Czas przyszły",
            "plusquamperfekt": "Czas zaprzeszły",
            "konjunktiv_ii": "Tryb przypuszczający",
            "imperativ": "Tryb rozkazujący",
            "infinitiv": "Bezokolicznik",
            "partizip_ii": "Imiesłów II",
        },
        "en": {
            "prasens": "Present",
            "perfekt": "Present perfect",
            "prateritum": "Simple past",
            "futur_i": "Future I",
            "plusquamperfekt": "Pluperfect",
            "konjunktiv_ii": "Subjunctive II",
            "imperativ": "Imperative",
            "infinitiv": "Infinitive",
            "partizip_ii": "Past participle",
        },
    },
    "it": {
        "pl": {
            "presente": "Czas teraźniejszy",
            "passato_prossimo": "Czas przeszły złożony",
            "imperfetto": "Czas przeszły niedokonany",
            "futuro_semplice": "Czas przyszły",
            "condizionale": "Tryb warunkowy",
            "congiuntivo_presente": "Tryb łączący — teraźniejszy",
            "imperativo": "Tryb rozkazujący",
            "gerundio": "Gerundium",
            "participio": "Imiesłów",
        },
        "en": {
            "presente": "Present",
            "passato_prossimo": "Present perfect",
            "imperfetto": "Imperfect",
            "futuro_semplice": "Simple future",
            "condizionale": "Conditional",
            "congiuntivo_presente": "Present subjunctive",
            "imperativo": "Imperative",
            "gerundio": "Gerund",
            "participio": "Participle",
        },
    },
    "pt-br": {
        "pl": {
            "presente": "Czas teraźniejszy",
            "preterito_perfeito": "Czas przeszły dokonany",
            "preterito_imperfeito": "Czas przeszły niedokonany",
            "futuro": "Czas przyszły",
            "condicional": "Tryb warunkowy",
            "subjuntivo_presente": "Tryb łączący — teraźniejszy",
            "imperativo": "Tryb rozkazujący",
            "gerundio": "Gerundium",
            "participio": "Imiesłów",
        },
        "en": {
            "presente": "Present",
            "preterito_perfeito": "Preterite",
            "preterito_imperfeito": "Imperfect",
            "futuro": "Future",
            "condicional": "Conditional",
            "subjuntivo_presente": "Present subjunctive",
            "imperativo": "Imperative",
            "gerundio": "Gerund",
            "participio": "Participle",
        },
    },
    "pt-pt": {
        "pl": {
            "presente": "Czas teraźniejszy",
            "preterito_perfeito": "Czas przeszły dokonany",
            "preterito_imperfeito": "Czas przeszły niedokonany",
            "futuro": "Czas przyszły",
            "condicional": "Tryb warunkowy",
            "subjuntivo_presente": "Tryb łączący — teraźniejszy",
            "imperativo": "Tryb rozkazujący",
            "infinitivo_pessoal": "Bezokolicznik osobowy",
            "gerundio": "Gerundium",
            "participio": "Imiesłów",
        },
        "en": {
            "presente": "Present",
            "preterito_perfeito": "Preterite",
            "preterito_imperfeito": "Imperfect",
            "futuro": "Future",
            "condicional": "Conditional",
            "subjuntivo_presente": "Present subjunctive",
            "imperativo": "Imperative",
            "infinitivo_pessoal": "Personal infinitive",
            "gerundio": "Gerund",
            "participio": "Participle",
        },
    },
    "pl": {
        "en": {
            "czas_terazniejszy": "Present tense",
            "czas_przeszly": "Past tense",
            "czas_przyszly": "Future tense",
            "tryb_rozkazujacy": "Imperative",
            "tryb_przypuszczajacy": "Conditional",
            "bezokolicznik": "Infinitive",
            "imieslow_przeszly": "Past participle",
            "imieslow_przyszly": "Future participle",
        },
    },
    "ru": {
        "pl": {
            "nastoyashchee": "Czas teraźniejszy",
            "proshedshee": "Czas przeszły",
            "budushchee": "Czas przyszły",
            "povelitelnoe": "Tryb rozkazujący",
            "infinitiv": "Bezokolicznik",
            "deeprichastie": "Imiesłów przysłówkowy",
        },
        "en": {
            "nastoyashchee": "Present",
            "proshedshee": "Past",
            "budushchee": "Future",
            "povelitelnoe": "Imperative",
            "infinitiv": "Infinitive",
            "deeprichastie": "Adverbial participle",
        },
    },
    "ja": {
        "pl": {
            "jisho": "Forma słownikowa",
            "masu": "Forma grzecznościowa",
            "te": "Forma て",
            "ta": "Forma た",
            "nai": "Forma przecząca",
            "potential": "Forma potencjalna",
            "imperative": "Tryb rozkazujący",
        },
        "en": {
            "jisho": "Dictionary form",
            "masu": "Polite form",
            "te": "Te-form",
            "ta": "Ta-form",
            "nai": "Negative form",
            "potential": "Potential form",
            "imperative": "Imperative",
        },
    },
    "ko": {
        "pl": {
            "present": "Czas teraźniejszy",
            "past": "Czas przeszły",
            "future": "Czas przyszły",
            "imperative": "Tryb rozkazujący",
            "base": "Temat czasownika",
        },
        "en": {
            "present": "Present",
            "past": "Past",
            "future": "Future",
            "imperative": "Imperative",
            "base": "Verb stem",
        },
    },
    "zh": {
        "pl": {
            "present": "Czas teraźniejszy",
            "past": "Czas przeszły",
            "future": "Czas przyszły",
            "progressive": "Aspekt ciągły",
            "perfect": "Aspekt dokonany",
            "base": "Forma podstawowa",
        },
        "en": {
            "present": "Present",
            "past": "Past",
            "future": "Future",
            "progressive": "Progressive",
            "perfect": "Perfect",
            "base": "Base form",
        },
    },
    "vi": {
        "pl": {
            "present": "Czas teraźniejszy",
            "past": "Czas przeszły",
            "future": "Czas przyszły",
            "imperative": "Tryb rozkazujący",
            "infinitive": "Bezokolicznik",
        },
        "en": {
            "present": "Present",
            "past": "Past",
            "future": "Future",
            "imperative": "Imperative",
            "infinitive": "Infinitive",
        },
    },
    "ar": {
        "pl": {
            "perfect": "Czas przeszły",
            "imperfect": "Czas teraźniejszy",
            "imperative": "Tryb rozkazujący",
            "masdar": "Rzeczownik odczasownikowy",
        },
        "en": {
            "perfect": "Past",
            "imperfect": "Present",
            "imperative": "Imperative",
            "masdar": "Verbal noun",
        },
    },
    "hi": {
        "pl": {
            "present": "Czas teraźniejszy",
            "past": "Czas przeszły",
            "future": "Czas przyszły",
            "imperative": "Tryb rozkazujący",
            "infinitive": "Bezokolicznik",
        },
        "en": {
            "present": "Present",
            "past": "Past",
            "future": "Future",
            "imperative": "Imperative",
            "infinitive": "Infinitive",
        },
    },
    "tr": {
        "pl": {
            "simdi_zaman": "Czas teraźniejszy",
            "genis_zaman": "Czas teraźniejszy ogólny",
            "gecmis_zaman": "Czas przeszły",
            "gelecek_zaman": "Czas przyszły",
            "mastar": "Bezokolicznik",
        },
        "en": {
            "simdi_zaman": "Present continuous",
            "genis_zaman": "Aorist",
            "gecmis_zaman": "Past",
            "gelecek_zaman": "Future",
            "mastar": "Infinitive",
        },
    },
}


def _copy_pt(src: dict[str, dict[str, str]]) -> None:
    if "pt-br" in src and "pt-pt" not in src:
        src["pt-pt"] = dict(src["pt-br"])


def load_manifest_keys(path: Path) -> tuple[str, list[tuple[str, str]], str]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    code = data["code"]
    verbs = data.get("verbs") or {}
    items: list[tuple[str, str]] = []
    for t in verbs.get("tenses") or []:
        items.append((t["key"], t["label_l2"]))
    for t in verbs.get("non_finite") or []:
        items.append((t["key"], t["label_l2"]))
    raw = path.read_text(encoding="utf-8")
    return code, items, raw


def yaml_quote(value: str) -> str:
    if value.startswith("-") or any(c in value for c in ":#{}[]&*!|>'\"%@`"):
        return json_escape(value)
    return value


def json_escape(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def merge_labels(code: str, items: list[tuple[str, str]], existing: dict) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    fill = FILL.get(code, {})
    _copy_pt(fill)
    keys = [k for k, _ in items]
    l2_by_key = {k: lab for k, lab in items}
    for app in APP_LANGS:
        merged: dict[str, str] = {}
        if app == code:
            merged.update(l2_by_key)
        existing_app = (existing.get("ui_labels") or {}).get(app) or {}
        fill_app = fill.get(app) or {}
        for key in keys:
            if key in existing_app and existing_app[key]:
                merged[key] = existing_app[key]
            elif key in fill_app:
                merged[key] = fill_app[key]
            elif app == code:
                merged[key] = l2_by_key[key]
            elif app == "en" and key in l2_by_key:
                # fallback: keep L2 if we have no English gloss yet — marked later as missing
                pass
        if merged:
            out[app] = merged
    return out


def dump_ui_labels(labels: dict[str, dict[str, str]]) -> str:
    lines = ["ui_labels:"]
    for app in APP_LANGS:
        block = labels.get(app)
        if not block:
            continue
        lines.append(f"  {app}:")
        for key, val in block.items():
            lines.append(f"    {key}: {yaml_quote(val)}")
    return "\n".join(lines) + "\n"


def replace_ui_labels(raw: str, block: str) -> str:
    idx = raw.find("\nui_labels:")
    if idx == -1:
        if raw.endswith("\n"):
            return raw + block
        return raw + "\n" + block
    return raw[: idx + 1] + block


def write_kotlin(table: dict[str, dict[str, dict[str, str]]]) -> None:
    lines = [
        "package com.vocabulario.app.data",
        "",
        "/** Fallback tłumaczeń czasów (LSP ui_labels). Nagłówek zawsze bierze L2. */",
        "object TenseUiLabels {",
        "    fun label(learningLang: String, appLang: String, key: String): String? {",
        "        val learn = learningLang.trim().lowercase()",
        "        val app = appLang.trim().lowercase()",
        "        val n = normalizeTenseKey(key)",
        "        val pack = TABLE[learn] ?: return null",
        "        val lang = pack[app] ?: return null",
        "        return lang[n] ?: lang[key]",
        "    }",
        "",
        "    private val TABLE: Map<String, Map<String, Map<String, String>>> = mapOf(",
    ]
    for learn, apps in table.items():
        lines.append(f'        "{learn}" to mapOf(')
        for app, keys in apps.items():
            lines.append(f'            "{app}" to mapOf(')
            for key, val in keys.items():
                esc = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'                "{key}" to "{esc}",')
            lines.append("            ),")
        lines.append("        ),")
    lines.append("    )")
    lines.append("}")
    lines.append("")
    KOTLIN.write_text("\n".join(lines), encoding="utf-8")


def write_audit(rows: list[dict]) -> None:
    lines = [
        "# Audyt etykiet czasów i form nieosobowych",
        "",
        "Nagłówek odmiany: **nazwa w języku uczonym** (środek, pogrubiona).",
        "Pod spodem: tłumaczenie w **języku aplikacji**, jeśli istnieje i różni się od oryginału.",
        "Ustawienie „etykiety czasów” zostało usunięte — zawsze ten sam układ.",
        "",
        "Języki UI / nauki (16 LSP): `en`, `es`, `fr`, `de`, `it`, `pt-br`, `pt-pt`, `zh`, `ja`, `ko`, `ar`, `ru`, `hi`, `tr`, `vi`, `pl`.",
        "",
    ]
    missing_total = 0
    for row in rows:
        code = row["code"]
        items = row["items"]
        labels = row["labels"]
        lines.append(f"## {code}")
        lines.append("")
        lines.append("| Klucz | Nazwa L2 (nagłówek) | Braki tłumaczeń (język aplikacji) |")
        lines.append("| --- | --- | --- |")
        for key, l2 in items:
            missing = []
            for app in APP_LANGS:
                if app == code:
                    continue
                if not (labels.get(app) or {}).get(key):
                    missing.append(app)
            missing_total += len(missing)
            miss = ", ".join(missing) if missing else "—"
            lines.append(f"| `{key}` | {l2} | {miss} |")
        lines.append("")
        lines.append("Pokrycie `ui_labels` per język aplikacji:")
        lines.append("")
        for app in APP_LANGS:
            have = sum(1 for key, _ in items if (labels.get(app) or {}).get(key))
            lines.append(f"- `{app}`: {have}/{len(items)}")
        lines.append("")
    lines.append("## Podsumowanie braków")
    lines.append("")
    lines.append(f"Komórek bez tłumaczenia (poza parą język uczony = język aplikacji): **{missing_total}**.")
    lines.append("")
    lines.append("Źródło prawdy: `backend/app/lsp/*/manifest.yaml` → `ui_labels`.")
    lines.append("Fallback w aplikacji: `TenseUiLabels.kt` (generowane tym skryptem).")
    lines.append("")
    DOCS.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    import yaml

    all_table: dict[str, dict[str, dict[str, str]]] = {}
    audit_rows = []
    for path in sorted(LSP.glob("*/manifest.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        code = data["code"]
        verbs = data.get("verbs") or {}
        items = [(t["key"], t["label_l2"]) for t in (verbs.get("tenses") or [])]
        items += [(t["key"], t["label_l2"]) for t in (verbs.get("non_finite") or [])]
        # de-dupe keys (ja repeats te/ta)
        seen = set()
        uniq = []
        for k, lab in items:
            if k in seen:
                continue
            seen.add(k)
            uniq.append((k, lab))
        items = uniq
        labels = merge_labels(code, items, data)
        raw = path.read_text(encoding="utf-8")
        path.write_text(replace_ui_labels(raw, dump_ui_labels(labels)), encoding="utf-8")
        all_table[code] = labels
        audit_rows.append({"code": code, "items": items, "labels": labels})
    write_kotlin(all_table)
    write_audit(audit_rows)
    print(f"updated {len(audit_rows)} manifests")
    print(f"wrote {DOCS}")
    print(f"wrote {KOTLIN}")


if __name__ == "__main__":
    main()

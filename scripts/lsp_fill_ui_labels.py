#!/usr/bin/env python3
"""Uzupełnia ui_labels LSP (16 języków UI) i regeneruje TenseUiLabels.kt.

Nie nadpisuje już istniejących etykiet w manifestach.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.lsp.constants import SUPPORTED_L2_LANGS  # noqa: E402
from app.lsp.registry import get_manifest  # noqa: E402

UI_LANGS = sorted(SUPPORTED_L2_LANGS)
LSP_ROOT = ROOT / "backend" / "app" / "lsp"
KT_PATH = (
    ROOT
    / "android"
    / "app"
    / "src"
    / "main"
    / "java"
    / "com"
    / "vocabulario"
    / "app"
    / "data"
    / "TenseUiLabels.kt"
)

# Brakujące tłumaczenia: L2 → UI → tense_key → label.
# Istniejące wpisy w YAML mają pierwszeństwo.
EXTRA: dict[str, dict[str, dict[str, str]]] = {}

_SIMPLE = {
    "present": {
        "ar": "المضارع", "de": "Präsens", "en": "Present", "es": "Presente",
        "fr": "Présent", "hi": "वर्तमान", "it": "Presente", "ja": "現在",
        "ko": "현재", "pl": "Czas teraźniejszy", "pt-br": "Presente",
        "pt-pt": "Presente", "ru": "Настоящее", "tr": "Şimdiki zaman",
        "vi": "Hiện tại", "zh": "现在",
    },
    "past": {
        "ar": "الماضي", "de": "Präteritum", "en": "Past", "es": "Pasado",
        "fr": "Passé", "hi": "भूत", "it": "Passato", "ja": "過去",
        "ko": "과거", "pl": "Czas przeszły", "pt-br": "Passado",
        "pt-pt": "Passado", "ru": "Прошедшее", "tr": "Geçmiş zaman",
        "vi": "Quá khứ", "zh": "过去",
    },
    "future": {
        "ar": "المستقبل", "de": "Futur", "en": "Future", "es": "Futuro",
        "fr": "Futur", "hi": "भविष्य", "it": "Futuro", "ja": "未来",
        "ko": "미래", "pl": "Czas przyszły", "pt-br": "Futuro",
        "pt-pt": "Futuro", "ru": "Будущее", "tr": "Gelecek zaman",
        "vi": "Tương lai", "zh": "将来",
    },
    "imperative": {
        "ar": "الأمر", "de": "Imperativ", "en": "Imperative", "es": "Imperativo",
        "fr": "Impératif", "hi": "आज्ञार्थ", "it": "Imperativo", "ja": "命令形",
        "ko": "명령", "pl": "Tryb rozkazujący", "pt-br": "Imperativo",
        "pt-pt": "Imperativo", "ru": "Повелительное", "tr": "Emir kipi",
        "vi": "Mệnh lệnh", "zh": "祈使",
    },
    "infinitive": {
        "ar": "المصدر", "de": "Infinitiv", "en": "Infinitive", "es": "Infinitivo",
        "fr": "Infinitif", "hi": "मूलधातु", "it": "Infinito", "ja": "不定詞",
        "ko": "부정사", "pl": "Bezokolicznik", "pt-br": "Infinitivo",
        "pt-pt": "Infinitivo", "ru": "Инфинитив", "tr": "Mastar",
        "vi": "Nguyên mẫu", "zh": "不定式",
    },
    "base": {
        "ar": "الجذر", "de": "Stamm", "en": "Base form", "es": "Raíz",
        "fr": "Forme de base", "hi": "मूल रूप", "it": "Tema", "ja": "語幹",
        "ko": "어간", "pl": "Forma podstawowa", "pt-br": "Radical",
        "pt-pt": "Radical", "ru": "Основа", "tr": "Gövde",
        "vi": "Gốc", "zh": "原形",
    },
}


def _by_ui(key_map: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """tense_key → {ui: label}  ⇒  ui → {tense_key: label}."""
    out: dict[str, dict[str, str]] = {u: {} for u in UI_LANGS}
    for tense, langs in key_map.items():
        for ui, label in langs.items():
            out.setdefault(ui, {})[tense] = label
    return out


def _simple_pack(*keys: str) -> dict[str, dict[str, str]]:
    return _by_ui({k: _SIMPLE[k] for k in keys})


EXTRA["zh"] = _simple_pack("present", "past", "future", "imperative", "base")
EXTRA["zh"] = {
    **EXTRA["zh"],
}
# overlay aspect terms
_zh_extra = {
    "progressive": {
        "ar": "الاستمرار", "de": "Verlaufsform", "en": "Progressive",
        "es": "Progresivo", "fr": "Progressif", "hi": "सातत्य",
        "it": "Progressivo", "ja": "進行", "ko": "진행", "pl": "Aspekt ciągły",
        "pt-br": "Progressivo", "pt-pt": "Progressivo", "ru": "Длительный вид",
        "tr": "Süreklilik", "vi": "Tiếp diễn", "zh": "进行",
    },
    "perfect": {
        "ar": "التام", "de": "Perfekt", "en": "Perfect", "es": "Perfecto",
        "fr": "Perfectif", "hi": "पूर्ण", "it": "Perfetto", "ja": "完了",
        "ko": "완료", "pl": "Aspekt dokonany", "pt-br": "Perfeito",
        "pt-pt": "Perfeito", "ru": "Совершенный вид", "tr": "Görülen geçmiş",
        "vi": "Hoàn thành", "zh": "完成",
    },
}
for k, langs in _zh_extra.items():
    for ui, lab in langs.items():
        EXTRA["zh"].setdefault(ui, {})[k] = lab

EXTRA["vi"] = _simple_pack("present", "past", "future", "imperative", "infinitive")
EXTRA["ko"] = _simple_pack("present", "past", "future", "imperative", "base")
EXTRA["hi"] = _simple_pack("present", "past", "future", "imperative", "infinitive")

EXTRA["ar"] = _by_ui({
    "perfect": {**_SIMPLE["past"], "en": "Past", "ar": "الماضي", "pl": "Czas przeszły"},
    "imperfect": {**_SIMPLE["present"], "en": "Present", "ar": "المضارع", "pl": "Czas teraźniejszy"},
    "imperative": _SIMPLE["imperative"],
    "masdar": {
        "ar": "المصدر", "de": "Verbalnomen", "en": "Verbal noun", "es": "Nombre verbal",
        "fr": "Nom verbal", "hi": "क्रियावाचक संज्ञा", "it": "Nome verbale",
        "ja": "動名詞", "ko": "동명사", "pl": "Rzeczownik odczasownikowy",
        "pt-br": "Nome verbal", "pt-pt": "Nome verbal", "ru": "Отглагольное имя",
        "tr": "Mastar ismi", "vi": "Danh động từ", "zh": "动名词",
    },
})

EXTRA["tr"] = _by_ui({
    "simdi_zaman": {
        "ar": "المضارع المستمر", "de": "Präsens (jetzt)", "en": "Present continuous",
        "es": "Presente continuo", "fr": "Présent continu", "hi": "वर्तमान सतत",
        "it": "Presente progressivo", "ja": "現在進行", "ko": "현재 진행",
        "pl": "Czas teraźniejszy ciągły", "pt-br": "Presente contínuo",
        "pt-pt": "Presente contínuo", "ru": "Настоящее длительное",
        "tr": "Şimdiki zaman", "vi": "Hiện tại tiếp diễn", "zh": "现在进行",
    },
    "genis_zaman": {
        "ar": "المضارع العام", "de": "Aorist", "en": "Aorist", "es": "Aoristo",
        "fr": "Aoriste", "hi": "सामान्य वर्तमान", "it": "Aoristo",
        "ja": "広時制", "ko": "넓적 시제", "pl": "Czas teraźniejszy ogólny",
        "pt-br": "Aoristo", "pt-pt": "Aoristo", "ru": "Аорист",
        "tr": "Geniş zaman", "vi": "Hiện tại tổng quát", "zh": "一般现在",
    },
    "gecmis_zaman": _SIMPLE["past"] | {"tr": "Geçmiş zaman", "en": "Past"},
    "gelecek_zaman": _SIMPLE["future"] | {"tr": "Gelecek zaman", "en": "Future"},
    "mastar": _SIMPLE["infinitive"] | {"tr": "Mastar", "en": "Infinitive"},
})

EXTRA["ru"] = _by_ui({
    "nastoyashchee": _SIMPLE["present"] | {"ru": "Настоящее", "en": "Present"},
    "proshedshee": _SIMPLE["past"] | {"ru": "Прошедшее", "en": "Past"},
    "budushchee": _SIMPLE["future"] | {"ru": "Будущее", "en": "Future"},
    "povelitelnoe": _SIMPLE["imperative"] | {"ru": "Повелительное", "en": "Imperative"},
    "infinitiv": _SIMPLE["infinitive"] | {"ru": "Инфинитив", "en": "Infinitive"},
    "deeprichastie": {
        "ar": "اسم الفاعل الظرفي", "de": "Adverbialpartizip", "en": "Adverbial participle",
        "es": "Gerundio adverbial", "fr": "Gérondif", "hi": "क्रियान्वेषी कृदंत",
        "it": "Gerundio", "ja": "副動詞", "ko": "부동사",
        "pl": "Imiesłów przysłówkowy", "pt-br": "Gerúndio adverbial",
        "pt-pt": "Gerúndio adverbial", "ru": "Деепричастие",
        "tr": "Zarf-fiil", "vi": "Phân từ trạng ngữ", "zh": "副动词",
    },
})

EXTRA["pl"] = _by_ui({
    "czas_terazniejszy": _SIMPLE["present"] | {"pl": "Czas teraźniejszy", "en": "Present tense"},
    "czas_przeszly": _SIMPLE["past"] | {"pl": "Czas przeszły", "en": "Past tense"},
    "czas_przyszly": _SIMPLE["future"] | {"pl": "Czas przyszły", "en": "Future tense"},
    "tryb_rozkazujacy": _SIMPLE["imperative"] | {"pl": "Tryb rozkazujący", "en": "Imperative"},
    "tryb_przypuszczajacy": {
        "ar": "الشرط", "de": "Konditional", "en": "Conditional", "es": "Condicional",
        "fr": "Conditionnel", "hi": "संभाव्य", "it": "Condizionale", "ja": "仮定法",
        "ko": "가정법", "pl": "Tryb przypuszczający", "pt-br": "Condicional",
        "pt-pt": "Condicional", "ru": "Сослагательное", "tr": "Dilek-şart",
        "vi": "Điều kiện", "zh": "条件式",
    },
    "bezokolicznik": _SIMPLE["infinitive"] | {"pl": "Bezokolicznik", "en": "Infinitive"},
    "imieslow_przeszly": {
        "ar": "اسم المفعول", "de": "Partizip Perfekt", "en": "Past participle",
        "es": "Participio pasado", "fr": "Participe passé", "hi": "भूतकालिक कृदंत",
        "it": "Participio passato", "ja": "過去分詞", "ko": "과거분사",
        "pl": "Imiesłów przeszły", "pt-br": "Particípio passado",
        "pt-pt": "Particípio passado", "ru": "Причастие прошедшего",
        "tr": "Geçmiş zaman ortacı", "vi": "Quá khứ phân từ", "zh": "过去分词",
    },
    "imieslow_przyszly": {
        "ar": "اسم الفاعل المستقبلي", "de": "Partizip Futur", "en": "Future participle",
        "es": "Participio futuro", "fr": "Participe futur", "hi": "भविष्यकालिक कृदंत",
        "it": "Participio futuro", "ja": "未来分詞", "ko": "미래분사",
        "pl": "Imiesłów przyszły", "pt-br": "Particípio futuro",
        "pt-pt": "Particípio futuro", "ru": "Причастие будущего",
        "tr": "Gelecek zaman ortacı", "vi": "Tương lai phân từ", "zh": "将来分词",
    },
})

_GERUND = {
    "ar": "المصدر الحالي", "de": "Gerundium", "en": "Gerund", "es": "Gerundio",
    "fr": "Gérondif", "hi": "क्रियार्थक संज्ञा", "it": "Gerundio", "ja": "動名詞",
    "ko": "동명사", "pl": "Gerundium", "pt-br": "Gerúndio", "pt-pt": "Gerúndio",
    "ru": "Герундий", "tr": "Ulaç", "vi": "Danh động từ", "zh": "动名词",
}
_PARTICIPLE = {
    "ar": "اسم المفعول", "de": "Partizip", "en": "Participle", "es": "Participio",
    "fr": "Participe", "hi": "कृदंत", "it": "Participio", "ja": "分詞",
    "ko": "분사", "pl": "Imiesłów", "pt-br": "Particípio", "pt-pt": "Particípio",
    "ru": "Причастие", "tr": "Ortaç", "vi": "Phân từ", "zh": "分词",
}
_COND = {
    "ar": "الشرط", "de": "Konditional", "en": "Conditional", "es": "Condicional",
    "fr": "Conditionnel", "hi": "संभाव्य", "it": "Condizionale", "ja": "条件法",
    "ko": "조건법", "pl": "Tryb warunkowy", "pt-br": "Condicional",
    "pt-pt": "Condicional", "ru": "Условное", "tr": "Koşul kipi",
    "vi": "Điều kiện", "zh": "条件式",
}
_SUBJ_PRES = {
    "ar": "الشرط الحاضر", "de": "Konjunktiv Präsens", "en": "Present subjunctive",
    "es": "Presente de subjuntivo", "fr": "Subjonctif présent", "hi": "संभाव्य वर्तमान",
    "it": "Congiuntivo presente", "ja": "接続法現在", "ko": "접속법 현재",
    "pl": "Tryb łączący — teraźniejszy", "pt-br": "Subjuntivo presente",
    "pt-pt": "Conjuntivo presente", "ru": "Сослагательное настоящее",
    "tr": "Dilek kipi şimdiki", "vi": "Giả định hiện tại", "zh": "虚拟式现在",
}

EXTRA["pt-br"] = _by_ui({
    "presente": _SIMPLE["present"] | {"pt-br": "Presente", "en": "Present"},
    "preterito_perfeito": {
        "ar": "الماضي التام", "de": "Pretérito perfeito", "en": "Preterite",
        "es": "Pretérito perfecto", "fr": "Passé simple", "hi": "भूत पूर्ण",
        "it": "Passato remoto", "ja": "完了過去", "ko": "완료 과거",
        "pl": "Czas przeszły dokonany", "pt-br": "Pretérito perfeito",
        "pt-pt": "Pretérito perfeito", "ru": "Прошедшее совершенное",
        "tr": "Belirli geçmiş", "vi": "Quá khứ hoàn thành", "zh": "简单过去",
    },
    "preterito_imperfeito": {
        "ar": "الماضي المستمر", "de": "Imperfekt", "en": "Imperfect",
        "es": "Pretérito imperfecto", "fr": "Imparfait", "hi": "अपूर्ण भूत",
        "it": "Imperfetto", "ja": "未完了過去", "ko": "미완료 과거",
        "pl": "Czas przeszły niedokonany", "pt-br": "Pretérito imperfeito",
        "pt-pt": "Pretérito imperfeito", "ru": "Прошедшее несовершенное",
        "tr": "Hikâye geçmiş", "vi": "Quá khứ chưa hoàn thành", "zh": "过去未完成",
    },
    "futuro": _SIMPLE["future"] | {"pt-br": "Futuro", "en": "Future"},
    "condicional": _COND,
    "subjuntivo_presente": _SUBJ_PRES,
    "imperativo": _SIMPLE["imperative"] | {"pt-br": "Imperativo", "en": "Imperative"},
    "gerundio": _GERUND,
    "participio": _PARTICIPLE,
})
EXTRA["pt-pt"] = {
    ui: dict(labs) for ui, labs in EXTRA["pt-br"].items()
}
for ui in UI_LANGS:
    EXTRA["pt-pt"].setdefault(ui, {})["infinitivo_pessoal"] = {
        "ar": "المصدر الشخصي", "de": "Persönlicher Infinitiv", "en": "Personal infinitive",
        "es": "Infinitivo personal", "fr": "Infinitif personnel", "hi": "व्यक्तिगत अनंत",
        "it": "Infinito personale", "ja": "人称不定詞", "ko": "인칭 부정사",
        "pl": "Bezokolicznik osobowy", "pt-br": "Infinitivo pessoal",
        "pt-pt": "Infinitivo pessoal", "ru": "Личный инфинитив",
        "tr": "Kişili mastar", "vi": "Động từ nguyên mẫu ngôi", "zh": "人称不定式",
    }[ui]

EXTRA["it"] = _by_ui({
    "presente": _SIMPLE["present"] | {"it": "Presente", "en": "Present"},
    "passato_prossimo": {
        "ar": "الماضي القريب", "de": "Passato prossimo", "en": "Present perfect",
        "es": "Pretérito perfecto", "fr": "Passé composé", "hi": "निकट भूत",
        "it": "Passato prossimo", "ja": "近過去", "ko": "현재완료",
        "pl": "Czas przeszły złożony", "pt-br": "Pretérito perfeito composto",
        "pt-pt": "Pretérito perfeito composto", "ru": "Ближайшее прошедшее",
        "tr": "Yakın geçmiş", "vi": "Quá khứ gần", "zh": "近过去",
    },
    "imperfetto": {
        "ar": "الماضي المستمر", "de": "Imperfekt", "en": "Imperfect",
        "es": "Imperfecto", "fr": "Imparfait", "hi": "अपूर्ण भूत",
        "it": "Imperfetto", "ja": "半過去", "ko": "미완료 과거",
        "pl": "Czas przeszły niedokonany", "pt-br": "Pretérito imperfeito",
        "pt-pt": "Pretérito imperfeito", "ru": "Имперфект",
        "tr": "Hikâye geçmiş", "vi": "Quá khứ chưa hoàn thành", "zh": "未完成过去",
    },
    "futuro_semplice": {
        **_SIMPLE["future"], "it": "Futuro semplice", "en": "Simple future",
        "pl": "Czas przyszły",
    },
    "condizionale": _COND | {"it": "Condizionale"},
    "congiuntivo_presente": _SUBJ_PRES | {"it": "Congiuntivo presente"},
    "imperativo": _SIMPLE["imperative"] | {"it": "Imperativo", "en": "Imperative"},
    "gerundio": _GERUND,
    "participio": _PARTICIPLE,
})

EXTRA["fr"] = _by_ui({
    "present": _SIMPLE["present"] | {"fr": "Présent", "en": "Present"},
    "passe_compose": {
        "ar": "الماضي المركب", "de": "Passé composé", "en": "Passé composé",
        "es": "Pretérito perfecto", "fr": "Passé composé", "hi": "पूर्ण भूत",
        "it": "Passato prossimo", "ja": "複合過去", "ko": "복합 과거",
        "pl": "Czas przeszły złożony", "pt-br": "Pretérito perfeito composto",
        "pt-pt": "Pretérito perfeito composto", "ru": "Сложное прошедшее",
        "tr": "Bileşik geçmiş", "vi": "Quá khứ kép", "zh": "复合过去",
    },
    "imparfait": {
        "ar": "الماضي المستمر", "de": "Imparfait", "en": "Imperfect",
        "es": "Imperfecto", "fr": "Imparfait", "hi": "अपूर्ण भूत",
        "it": "Imperfetto", "ja": "半過去", "ko": "미완료 과거",
        "pl": "Czas przeszły niedokonany", "pt-br": "Pretérito imperfeito",
        "pt-pt": "Pretérito imperfeito", "ru": "Имперфект",
        "tr": "Hikâye geçmiş", "vi": "Quá khứ chưa hoàn thành", "zh": "未完成过去",
    },
    "futur_simple": {
        **_SIMPLE["future"], "fr": "Futur simple", "en": "Simple future",
        "pl": "Czas przyszły",
    },
    "conditionnel": _COND | {"fr": "Conditionnel"},
    "subjonctif_present": _SUBJ_PRES | {"fr": "Subjonctif présent"},
    "plus_que_parfait": {
        "ar": "الماضي الأسبق", "de": "Plusquamperfekt", "en": "Pluperfect",
        "es": "Pluscuamperfecto", "fr": "Plus-que-parfait", "hi": "पूर्ण भूत पूर्व",
        "it": "Trapassato", "ja": "大過去", "ko": "대과거",
        "pl": "Czas zaprzeszły", "pt-br": "Mais-que-perfeito",
        "pt-pt": "Mais-que-perfeito", "ru": "Предпрошедшее",
        "tr": "Miş’li geçmiş", "vi": "Quá khứ hoàn thành xa", "zh": "过去完成",
    },
    "imperatif": _SIMPLE["imperative"] | {"fr": "Impératif", "en": "Imperative"},
    "infinitif": _SIMPLE["infinitive"] | {"fr": "Infinitif", "en": "Infinitive"},
    "participe_passe": {
        "ar": "اسم المفعول", "de": "Partizip Perfekt", "en": "Past participle",
        "es": "Participio pasado", "fr": "Participe passé", "hi": "भूतकालिक कृदंत",
        "it": "Participio passato", "ja": "過去分詞", "ko": "과거분사",
        "pl": "Imiesłów przeszły", "pt-br": "Particípio passado",
        "pt-pt": "Particípio passado", "ru": "Причастие прошедшего",
        "tr": "Geçmiş zaman ortacı", "vi": "Quá khứ phân từ", "zh": "过去分词",
    },
    "gerondif": _GERUND | {"fr": "Gérondif", "en": "Gerund"},
})

EXTRA["de"] = _by_ui({
    "prasens": _SIMPLE["present"] | {"de": "Präsens", "en": "Present"},
    "perfekt": {
        "ar": "التام", "de": "Perfekt", "en": "Present perfect",
        "es": "Pretérito perfecto", "fr": "Passé composé", "hi": "पूर्ण वर्तमान",
        "it": "Passato prossimo", "ja": "現在完了", "ko": "현재완료",
        "pl": "Czas przeszły złożony", "pt-br": "Pretérito perfeito composto",
        "pt-pt": "Pretérito perfeito composto", "ru": "Перфект",
        "tr": "Perfekt", "vi": "Hiện tại hoàn thành", "zh": "现在完成",
    },
    "prateritum": {
        "ar": "الماضي البسيط", "de": "Präteritum", "en": "Simple past",
        "es": "Pretérito", "fr": "Prétérit", "hi": "सामान्य भूत",
        "it": "Passato remoto", "ja": "単純過去", "ko": "단순 과거",
        "pl": "Czas przeszły prosty", "pt-br": "Pretérito perfeito",
        "pt-pt": "Pretérito perfeito", "ru": "Претерит",
        "tr": "Präteritum", "vi": "Quá khứ đơn", "zh": "一般过去",
    },
    "futur_i": {
        **_SIMPLE["future"], "de": "Futur I", "en": "Future I", "pl": "Czas przyszły",
    },
    "plusquamperfekt": {
        "ar": "الماضي الأسبق", "de": "Plusquamperfekt", "en": "Pluperfect",
        "es": "Pluscuamperfecto", "fr": "Plus-que-parfait", "hi": "पूर्ण भूत पूर्व",
        "it": "Trapassato", "ja": "大過去", "ko": "대과거",
        "pl": "Czas zaprzeszły", "pt-br": "Mais-que-perfeito",
        "pt-pt": "Mais-que-perfeito", "ru": "Предпрошедшее",
        "tr": "Miş’li geçmiş", "vi": "Quá khứ hoàn thành xa", "zh": "过去完成",
    },
    "konjunktiv_ii": {
        "ar": "الشرط", "de": "Konjunktiv II", "en": "Subjunctive II",
        "es": "Subjuntivo II", "fr": "Subjonctif II", "hi": "संभाव्य II",
        "it": "Congiuntivo II", "ja": "接続法 II", "ko": "접속법 II",
        "pl": "Tryb przypuszczający", "pt-br": "Subjuntivo II",
        "pt-pt": "Conjuntivo II", "ru": "Конъюнктив II",
        "tr": "Konjunktiv II", "vi": "Giả định II", "zh": "虚拟式 II",
    },
    "imperativ": _SIMPLE["imperative"] | {"de": "Imperativ", "en": "Imperative"},
    "infinitiv": _SIMPLE["infinitive"] | {"de": "Infinitiv", "en": "Infinitive"},
    "partizip_ii": {
        "ar": "اسم المفعول", "de": "Partizip II", "en": "Past participle",
        "es": "Participio II", "fr": "Participe II", "hi": "कृदंत II",
        "it": "Participio II", "ja": "第二分詞", "ko": "분사 II",
        "pl": "Imiesłów II", "pt-br": "Particípio II",
        "pt-pt": "Particípio II", "ru": "Причастие II",
        "tr": "Partizip II", "vi": "Phân từ II", "zh": "第二分词",
    },
})

EXTRA["es"] = _by_ui({
    "presente": _SIMPLE["present"] | {"es": "Presente", "en": "Present"},
    "preterito_perfecto": {
        "ar": "الماضي التام", "de": "Perfekt", "en": "Present perfect",
        "es": "Pretérito perfecto", "fr": "Passé composé", "hi": "पूर्ण वर्तमान",
        "it": "Passato prossimo", "ja": "現在完了", "ko": "현재완료",
        "pl": "Pretérito perfecto", "pt-br": "Pretérito perfeito composto",
        "pt-pt": "Pretérito perfeito composto", "ru": "Перфект",
        "tr": "Yakın geçmiş", "vi": "Hiện tại hoàn thành", "zh": "现在完成",
    },
    "preterito_indefinido": {
        "ar": "الماضي البسيط", "de": "Indefinido", "en": "Preterite",
        "es": "Pretérito indefinido", "fr": "Passé simple", "hi": "सामान्य भूत",
        "it": "Passato remoto", "ja": "不定過去", "ko": "단순 과거",
        "pl": "Czas przeszły prosty", "pt-br": "Pretérito perfeito",
        "pt-pt": "Pretérito perfeito", "ru": "Прошедшее простое",
        "tr": "Belirli geçmiş", "vi": "Quá khứ đơn", "zh": "简单过去",
    },
    "preterito_imperfecto": {
        "ar": "الماضي المستمر", "de": "Imperfekt", "en": "Imperfect",
        "es": "Pretérito imperfecto", "fr": "Imparfait", "hi": "अपूर्ण भूत",
        "it": "Imperfetto", "ja": "未完了過去", "ko": "미완료 과거",
        "pl": "Czas przeszły niedokonany", "pt-br": "Pretérito imperfeito",
        "pt-pt": "Pretérito imperfeito", "ru": "Имперфект",
        "tr": "Hikâye geçmiş", "vi": "Quá khứ chưa hoàn thành", "zh": "过去未完成",
    },
    "futuro_simple": {
        **_SIMPLE["future"], "es": "Futuro simple", "en": "Simple future",
        "pl": "Czas przyszły",
    },
    "condicional_simple": _COND | {"es": "Condicional", "en": "Conditional"},
    "presente_subjuntivo": _SUBJ_PRES | {"es": "Presente de subjuntivo"},
    "imperfecto_subjuntivo": {
        "ar": "الشرط الماضي", "de": "Konjunktiv Imperfekt", "en": "Imperfect subjunctive",
        "es": "Imperfecto de subjuntivo", "fr": "Subjonctif imparfait",
        "hi": "अपूर्ण संभाव्य", "it": "Congiuntivo imperfetto", "ja": "接続法半過去",
        "ko": "접속법 미완료", "pl": "Subjuntivo — imperfecto",
        "pt-br": "Subjuntivo imperfeito", "pt-pt": "Conjuntivo imperfeito",
        "ru": "Сослагательное имперфект", "tr": "Dilek kipi geçmiş",
        "vi": "Giả định quá khứ", "zh": "虚拟式过去",
    },
    "futuro_subjuntivo": {
        "ar": "الشرط المستقبل", "de": "Konjunktiv Futur", "en": "Future subjunctive",
        "es": "Futuro de subjuntivo", "fr": "Subjonctif futur",
        "hi": "भविष्य संभाव्य", "it": "Congiuntivo futuro", "ja": "接続法未来",
        "ko": "접속법 미래", "pl": "Subjuntivo — czas przyszły",
        "pt-br": "Subjuntivo futuro", "pt-pt": "Conjuntivo futuro",
        "ru": "Сослагательное будущее", "tr": "Dilek kipi gelecek",
        "vi": "Giả định tương lai", "zh": "虚拟式将来",
    },
    "preterito_pluscuamperfecto": {
        "ar": "الماضي الأسبق", "de": "Plusquamperfekt", "en": "Pluperfect",
        "es": "Pretérito pluscuamperfecto", "fr": "Plus-que-parfait",
        "hi": "पूर्ण भूत पूर्व", "it": "Trapassato prossimo", "ja": "大過去",
        "ko": "대과거", "pl": "Plusquamperfectum",
        "pt-br": "Mais-que-perfeito", "pt-pt": "Mais-que-perfeito",
        "ru": "Предпрошедшее", "tr": "Miş’li geçmiş",
        "vi": "Quá khứ hoàn thành xa", "zh": "过去完成",
    },
    "condicional_compuesto": {
        "ar": "الشرط المركب", "de": "Konditional II", "en": "Compound conditional",
        "es": "Condicional compuesto", "fr": "Conditionnel passé",
        "hi": "संभाव्य पूर्ण", "it": "Condizionale composto", "ja": "複合条件法",
        "ko": "복합 조건법", "pl": "Tryb warunkowy złożony",
        "pt-br": "Condicional composto", "pt-pt": "Condicional composto",
        "ru": "Сложное условное", "tr": "Bileşik koşul",
        "vi": "Điều kiện kép", "zh": "复合条件式",
    },
    "futuro_perfecto": {
        "ar": "المستقبل التام", "de": "Futur II", "en": "Future perfect",
        "es": "Futuro perfecto", "fr": "Futur antérieur", "hi": "पूर्ण भविष्य",
        "it": "Futuro anteriore", "ja": "未来完了", "ko": "미래완료",
        "pl": "Czas przyszły dokonany", "pt-br": "Futuro perfeito",
        "pt-pt": "Futuro perfeito", "ru": "Будущее совершенное",
        "tr": "Gelecek zamanın hikâyesi", "vi": "Tương lai hoàn thành", "zh": "将来完成",
    },
    "imperativo_afirmativo": {
        **_SIMPLE["imperative"], "es": "Imperativo afirmativo",
        "en": "Affirmative imperative", "pl": "Tryb rozkazujący (twierdzący)",
    },
    "imperativo_negativo": {
        **_SIMPLE["imperative"], "es": "Imperativo negativo",
        "en": "Negative imperative", "pl": "Tryb rozkazujący (przeczący)",
        "de": "Verneinter Imperativ", "fr": "Impératif négatif",
        "it": "Imperativo negativo", "pt-br": "Imperativo negativo",
        "pt-pt": "Imperativo negativo", "ru": "Отрицательное повелительное",
        "zh": "否定祈使",
    },
    "gerundio": _GERUND,
    "participio": _PARTICIPLE,
})

EXTRA["ja"] = _by_ui({
    "jisho": {
        "ar": "صيغة المعجم", "de": "Grundform", "en": "Dictionary form",
        "es": "Forma de diccionario", "fr": "Forme dictionnaire", "hi": "शब्दकोष रूप",
        "it": "Forma del dizionario", "ja": "辞書形", "ko": "사전형",
        "pl": "Forma słownikowa", "pt-br": "Forma de dicionário",
        "pt-pt": "Forma de dicionário", "ru": "Словарная форма",
        "tr": "Sözlük biçimi", "vi": "Dạng từ điển", "zh": "辞书形",
    },
    "masu": {
        "ar": "صيغة المهذب", "de": "Höflichkeitsform", "en": "Polite form",
        "es": "Forma cortés", "fr": "Forme polie", "hi": "विनम्र रूप",
        "it": "Forma cortese", "ja": "ます形", "ko": "ます형",
        "pl": "Forma grzecznościowa", "pt-br": "Forma educada",
        "pt-pt": "Forma educada", "ru": "Вежливая форма",
        "tr": "Nazik biçim", "vi": "Dạng lịch sự", "zh": "ます形",
    },
    "te": {
        "ar": "صيغة て", "de": "Te-Form", "en": "Te-form", "es": "Forma て",
        "fr": "Forme て", "hi": "て रूप", "it": "Forma て", "ja": "て形",
        "ko": "て형", "pl": "Forma て", "pt-br": "Forma て", "pt-pt": "Forma て",
        "ru": "Форма て", "tr": "て biçimi", "vi": "Dạng て", "zh": "て形",
    },
    "ta": {
        "ar": "صيغة た", "de": "Ta-Form", "en": "Ta-form", "es": "Forma た",
        "fr": "Forme た", "hi": "た रूप", "it": "Forma た", "ja": "た形",
        "ko": "た형", "pl": "Forma た", "pt-br": "Forma た", "pt-pt": "Forma た",
        "ru": "Форма た", "tr": "た biçimi", "vi": "Dạng た", "zh": "た形",
    },
    "nai": {
        "ar": "صيغة النفي", "de": "Negativform", "en": "Negative form",
        "es": "Forma negativa", "fr": "Forme négative", "hi": "नकारात्मक रूप",
        "it": "Forma negativa", "ja": "ない形", "ko": "ない형",
        "pl": "Forma przecząca", "pt-br": "Forma negativa",
        "pt-pt": "Forma negativa", "ru": "Отрицательная форма",
        "tr": "Olumsuz biçim", "vi": "Dạng phủ định", "zh": "ない形",
    },
    "potential": {
        "ar": "صيغة الإمكان", "de": "Potenzialform", "en": "Potential form",
        "es": "Forma potencial", "fr": "Forme potentielle", "hi": "संभाव्य रूप",
        "it": "Forma potenziale", "ja": "可能形", "ko": "가능형",
        "pl": "Forma potencjalna", "pt-br": "Forma potencial",
        "pt-pt": "Forma potencial", "ru": "Потенциальная форма",
        "tr": "Yeterlik biçimi", "vi": "Dạng khả năng", "zh": "可能形",
    },
    "imperative": _SIMPLE["imperative"] | {"ja": "命令形", "en": "Imperative"},
})

PERSON_LABELS = {
    "ar": {
        "ar_13": {
            "1sg": "أنا", "2sg_m": "أنتَ", "2sg_f": "أنتِ", "3sg_m": "هو",
            "3sg_f": "هي", "2du": "أنتما", "3du": "هما", "1pl": "نحن",
            "2pl_m": "أنتم", "2pl_f": "أنتن", "3pl_m": "هم", "3pl_f": "هن",
        },
        "ar_imperative": {
            "2sg_m": "أنتَ", "2sg_f": "أنتِ", "2pl_m": "أنتم", "2pl_f": "أنتن",
        },
    },
    "ja": {
        "ja_6": {
            "watashi": "私", "anata": "あなた", "kare": "彼",
            "watashitachi": "私たち", "anatatachi": "あなたたち", "karera": "彼ら",
        },
    },
    "ko": {
        "ko_6": {
            "jeo": "저", "neo": "너", "geu": "그",
            "uri": "우리", "neohui": "너희", "geudeul": "그들",
        },
        "ko_imperative": {"neo": "너", "uri": "우리"},
    },
    "hi": {
        "hi_6": {
            "main": "मैं", "tu": "तू", "yeh": "यह",
            "hum": "हम", "aap": "आप", "ve": "वे",
        },
        "hi_imperative": {"tu": "तू", "aap": "आप"},
    },
    "vi": {
        "vi_6": {
            "toi": "tôi", "ban": "bạn", "no": "nó",
            "chung_toi": "chúng tôi", "cac_ban": "các bạn", "ho": "họ",
        },
        "vi_imperative": {"ban": "bạn", "cac_ban": "các bạn"},
    },
}


def yaml_quote(value: str) -> str:
    if value == "" or any(c in value for c in ":#{}[]&*!|>'\"%@`") or value[:1] in "-?":
        return json.dumps(value, ensure_ascii=False)
    return value


def dump_ui_labels(merged: dict[str, dict[str, str]], tense_order: list[str]) -> str:
    lines = ["ui_labels:"]
    for ui in UI_LANGS:
        labs = merged.get(ui, {})
        lines.append(f"  {ui}:")
        for key in tense_order:
            if key in labs:
                lines.append(f"    {key}: {yaml_quote(labs[key])}")
        extra_keys = [k for k in labs if k not in tense_order]
        for key in extra_keys:
            lines.append(f"    {key}: {yaml_quote(labs[key])}")
    return "\n".join(lines) + "\n"


def merge_labels(code: str, keys: list[str]) -> dict[str, dict[str, str]]:
    m = get_manifest(code)
    extra = EXTRA.get(code, {})
    out: dict[str, dict[str, str]] = {}
    for ui in UI_LANGS:
        row: dict[str, str] = {}
        existing = m.ui_labels.get(ui, {})
        add = extra.get(ui, {})
        for key in keys:
            if key in existing:
                row[key] = existing[key]
            elif key in add:
                row[key] = add[key]
            else:
                # last resort: L2 original
                row[key] = m.label_for_tense(key, app_lang=code)
        out[ui] = row
    return out


def replace_ui_labels_block(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if "\nui_labels:" not in text:
        text = text.rstrip() + "\n\n" + block
    else:
        text = text[: text.index("\nui_labels:")] + "\n" + block
    path.write_text(text, encoding="utf-8")


def fill_person_labels(code: str, text: str) -> str:
    grids = PERSON_LABELS.get(code)
    if not grids:
        return text
    for grid, labels in grids.items():
        pattern = rf"({re.escape(grid)}:\n(?:.*\n)*?      labels: )" + r"\{\}"
        inner = ", ".join(f'{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}' for k, v in labels.items())
        text, n = re.subn(pattern, rf"\1{{ {inner} }}", text, count=1)
        if n == 0:
            print(f"  warn: no empty labels for {code}/{grid}")
    return text


def kt_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")


def generate_kotlin(all_labels: dict[str, dict[str, dict[str, str]]]) -> str:
    chunks = ['    private val TABLE: Map<String, Map<String, Map<String, String>>> = mapOf(']
    for l2 in sorted(all_labels):
        chunks.append(f'        "{l2}" to mapOf(')
        for ui in UI_LANGS:
            labs = all_labels[l2].get(ui, {})
            inner = ",\n".join(
                f'                "{k}" to "{kt_escape(v)}"' for k, v in labs.items()
            )
            chunks.append(f'            "{ui}" to mapOf(\n{inner},\n            ),')
        chunks.append("        ),")
    chunks.append("    )")
    return "\n".join(chunks)


def patch_kotlin(table_src: str) -> None:
    text = KT_PATH.read_text(encoding="utf-8")
    start = text.index("    private val TABLE:")
    end = text.rindex("    )")
    # last `    )` of TABLE — find matching from start
    # TABLE ends with `    )\n}` of object
    rest = text[start:]
    # object closes with `\n}\n` after TABLE's `    )`
    m = re.search(r"\n    \)\n\}\s*\Z", text[start:], re.S)
    if not m:
        raise SystemExit("cannot find TABLE end in TenseUiLabels.kt")
    new = text[:start] + table_src + "\n}\n"
    KT_PATH.write_text(new, encoding="utf-8")


def main() -> int:
    all_labels: dict[str, dict[str, dict[str, str]]] = {}
    missing_report: list[str] = []
    for code in sorted(SUPPORTED_L2_LANGS):
        m = get_manifest(code)
        keys = m.tense_keys() + m.non_finite_keys()
        # unique, preserve order
        seen: set[str] = set()
        ordered = []
        for k in keys:
            if k not in seen:
                seen.add(k)
                ordered.append(k)
        merged = merge_labels(code, ordered)
        all_labels[code] = merged
        path = LSP_ROOT / code / "manifest.yaml"
        block = dump_ui_labels(merged, ordered)
        replace_ui_labels_block(path, block)
        filled = fill_person_labels(code, path.read_text(encoding="utf-8"))
        path.write_text(filled, encoding="utf-8")
        for ui in UI_LANGS:
            gap = [k for k in ordered if k not in merged[ui]]
            if gap:
                missing_report.append(f"{code}/{ui}: {gap}")
        print(f"{code}: ui_labels {len(UI_LANGS)} langs × {len(ordered)} keys")

    patch_kotlin(generate_kotlin(all_labels))
    print(f"wrote {KT_PATH.relative_to(ROOT)}")
    if missing_report:
        print("STILL MISSING:")
        for line in missing_report:
            print(" ", line)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

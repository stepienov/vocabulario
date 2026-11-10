"""First-lookup prompt: fast, no invented words. Compare two models."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from app.services.llm import LLMService

SYSTEM = """Jesteś słownikiem. Zwracasz wyłącznie JSON.

Dostajesz język 1, język 2 i hasło.
Wielkość liter ignoruj. Pozostałych znaków nie zmieniaj i nie poprawiaj.
Zwróć hasło tylko wtedy, gdy jest prawdziwym samodzielnym słowem w języku 1 albo w języku 2.
Sprawdź oba języki. Różne znaczenia daj osobno, ale jednego znaczenia nie rozpisuj na synonimy.
Nie wymyślaj słów. Nie zwracaj odmiany, literówki ani podobnego słowa.
Nie zwracaj innego słowa tylko dlatego, że jedna jego forma wygląda jak hasło. Przymiotnik to nie rzeczownik.
word pisz tylko w języku 2. translation pisz tylko w języku 1. To mają być dwa różne słowa.
pos to część mowy słowa word.
Rzeczownik w języku 2 zaczyna się od rodzajnika (el/la, le/la/l', der/die/das).
Gdy hasła nie ma: {"pairs":[]}
W przeciwnym razie: {"pairs":[{"word":"...","pos":"...","translation":"..."}]}"""

USER = """Język 1: {language_1}
Język 2: {language_2}
Hasło: {query}"""

MODELS = ("gpt-6-sol", "gpt-6-luna")
EFFORT = "low"
TIER = "priority"
FAIL_RETRIES = 5


@dataclass(frozen=True)
class Case:
    language_1: str
    language_2: str
    query: str
    # At least one of these pairs is enough. Empty = must return nothing,
    # unless soft_empty (ser. may come back as the real word).
    any_of: frozenset[tuple[str, str]]
    forbid_word: frozenset[str] = frozenset()
    soft_empty: bool = False


CASES = [
    Case("polski", "hiszpański", "ser", frozenset({("queso", "ser"), ("ser", "byc")})),
    Case(
        "polski",
        "hiszpański",
        "droga",
        frozenset({("camino", "droga"), ("carretera", "droga"), ("droga", "narkotyk")}),
        forbid_word=frozenset({"caro", "cara", "querida"}),
    ),
    Case(
        "polski",
        "hiszpański",
        "para",
        frozenset({("pareja", "para"), ("par", "para"), ("vapor", "para"), ("para", "dla")}),
        forbid_word=frozenset({"dinero"}),
    ),
    Case(
        "francuski",
        "angielski",
        "chat",
        frozenset({("cat", "chat"), ("chat", "discussion"), ("chat", "conversation"), ("chat", "bavarder")}),
    ),
    Case("hiszpański", "angielski", "red", frozenset({("network", "red"), ("net", "red"), ("red", "rojo")})),
    Case("niemiecki", "angielski", "Gift", frozenset({("poison", "gift"), ("gift", "geschenk")})),
    Case("polski", "hiszpański", "serr", frozenset()),
    Case("polski", "hiszpański", "ser3", frozenset()),
    Case("polski", "hiszpański", "ser.", frozenset({("queso", "ser"), ("ser", "byc")}), soft_empty=True),
    Case("polski", "hiszpański", "sre", frozenset()),
]


def fold(value: str) -> str:
    text = (value or "").casefold().strip()
    for src, dst in {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o",
        "ś": "s", "ź": "z", "ż": "z", "ä": "a", "ö": "o", "ü": "u", "ß": "ss",
    }.items():
        text = text.replace(src, dst)
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()


def word_key(word: str) -> str:
    parts = fold(word).split()
    articles = {"el", "la", "los", "las", "le", "les", "un", "una", "une", "der", "die", "das", "the", "a", "an", "to"}
    if len(parts) >= 2 and parts[0] in articles:
        return parts[1]
    return parts[0] if parts else ""


def tokens(text: str) -> set[str]:
    raw = fold(text).replace(";", " ").replace(",", " ").replace("/", " ")
    return {p for p in raw.split() if p}


def query_key(case: Case) -> str:
    text = case.query.casefold()
    if case.soft_empty:
        text = "".join(ch for ch in text if ch.isalpha())
    return fold(text)


def judge(case: Case, rows: list[dict]) -> list[str]:
    problems: list[str] = []
    qk = query_key(case)

    if not case.any_of and not case.soft_empty:
        if rows:
            problems.append(f"nie-slowo-a-zwrocil-{len(rows)}")
        return problems

    linked = False
    for row in rows:
        wk = word_key(str(row.get("word") or ""))
        ts = tokens(str(row.get("translation") or ""))
        if not wk or not ts or not fold(str(row.get("pos") or "")):
            problems.append(f"niepelny:{row}")
            continue
        if wk in case.forbid_word:
            problems.append(f"zly-wyraz:{wk}")
        if wk == qk and ts <= {qk, "das", "der", "die", "el", "la", "le", "the"}:
            problems.append(f"kopia-hasla:{row.get('word')}|{row.get('translation')}")
        elif wk == qk or qk in ts:
            linked = True
        else:
            problems.append(f"nie-pasuje-do-hasla:{row.get('word')}|{row.get('translation')}")

    if case.soft_empty and not rows:
        return problems

    if rows and not linked:
        problems.append("zadna-para-nie-jest-tym-haslem")

    if case.any_of and rows:
        ok = any(
            any(word_key(str(r.get("word") or "")) == w and t in tokens(str(r.get("translation") or "")) for r in rows)
            for w, t in case.any_of
        )
        if not ok and not case.soft_empty:
            problems.append("brak-choc-jednego-prawdziwego-znaczenia")
    if case.soft_empty and rows and not linked:
        problems.append("ser-kropka-zwrocil-cos-innego")
    return problems


async def call(llm: LLMService, model: str, case: Case) -> dict[str, Any]:
    user = USER.format(language_1=case.language_1, language_2=case.language_2, query=case.query)
    t0 = time.perf_counter()
    try:
        resp = await llm.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_completion_tokens=500,
            reasoning_effort=EFFORT,
            service_tier=TIER,
        )
        ms = round((time.perf_counter() - t0) * 1000)
        data = json.loads(resp.choices[0].message.content or "{}")
        rows = [r for r in (data.get("pairs") or []) if isinstance(r, dict)] if isinstance(data, dict) else []
        problems = judge(case, rows)
        return {"ok": not problems, "model": model, "query": case.query, "ms": ms, "problems": problems, "pairs": rows}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "model": model,
            "query": case.query,
            "ms": round((time.perf_counter() - t0) * 1000),
            "problems": [f"err:{exc}"],
            "pairs": [],
        }


async def main() -> None:
    llm = LLMService()
    first = await asyncio.gather(*(call(llm, model, case) for model in MODELS for case in CASES))
    for row in first:
        print(json.dumps({**row, "phase": "first"}, ensure_ascii=False))

    by_model: dict[str, list[dict]] = {}
    for row in first:
        by_model.setdefault(row["model"], []).append(row)

    def score(rows: list[dict]) -> tuple[int, int]:
        return sum(1 for r in rows if r["ok"]), round(sum(r["ms"] for r in rows) / len(rows))

    ranking = sorted(by_model.items(), key=lambda item: (-score(item[1])[0], score(item[1])[1]))
    winner = ranking[0][0]
    failed_cases = [case for case in CASES if not next(r["ok"] for r in by_model[winner] if r["query"] == case.query)]
    retries: list[dict] = []
    if failed_cases:
        retries = list(
            await asyncio.gather(
                *(call(llm, winner, case) for case in failed_cases for _ in range(FAIL_RETRIES))
            )
        )
        for row in retries:
            print(json.dumps({**row, "phase": "retry"}, ensure_ascii=False))

    summary = []
    for model, rows in ranking:
        passed, avg = score(rows)
        extra = [r for r in retries if r["model"] == model]
        summary.append(
            {
                "model": model,
                "first_passed": passed,
                "first_total": len(rows),
                "avg_ms": avg,
                "retry_passed": sum(1 for r in extra if r["ok"]),
                "retry_total": len(extra),
            }
        )
    print(json.dumps({"winner": winner, "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

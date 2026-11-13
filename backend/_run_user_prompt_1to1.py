"""Run the user's screenshot prompt 1:1 on the same cases."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass

from app.services.llm import LLMService


SYSTEM = """Jesteś precyzyjnym asystentem językowym. Twoim zadaniem jest tworzenie list dwujęzycznych par słów dla podanego hasła.

Zasady:
- Dostajesz dwa języki (język_1 i język_2) oraz hasło.
- Zwracasz wyłącznie pary, w których hasło istnieje jako słowo w co najmniej jednym z tych języków.
- Dla każdej pary podajesz słowo, jego język, część mowy (POS) oraz tłumaczenie w drugim języku wraz z jego językiem i POS.
- Jeśli hasło ma kilka znaczeń lub części mowy, uwzględnij wszystkie istotne.
- Odpowiadaj wyłącznie poprawnym JSON-em. Żadnego dodatkowego tekstu, komentarzy ani markdown."""


USER = """Języki: {language_1}, {language_2}
Hasło: {query}

Zwróć listę par w formacie JSON:

[
  {{
    "word": "słowo",
    "language": "nazwa języka",
    "pos": "część mowy (np. noun, verb, adjective)",
    "translation": "tłumaczenie",
    "translation_language": "nazwa drugiego języka",
    "translation_pos": "część mowy tłumaczenia"
  }}
]

Uwzględnij tylko słowa, które istnieją jako hasło w jednym lub drugim języku."""


@dataclass(frozen=True)
class Case:
    language_1: str
    language_2: str
    query: str
    # Required: query appears as word OR translation in a row covering this sense pair.
    # For L1 match: word~query(L1), translation~l2_sense
    # For L2 match: word~query(L2), translation~l1_sense
    # We check presence of both language hits loosely via folded tokens.
    must_cover: frozenset[str]
    # tokens that must appear somewhere among word/translation for a hit
    expect_empty: bool = False
    repeats: int = 1


CASES = [
    Case("polski", "hiszpański", "ser", frozenset({"queso", "byc", "istota", "byt"}), repeats=2),
    Case("polski", "hiszpański", "droga", frozenset({"camino", "narkotyk", "droga"}), repeats=2),
    Case("polski", "hiszpański", "para", frozenset({"par", "dla", "para"}), repeats=1),
    Case("francuski", "angielski", "chat", frozenset({"cat", "chat"}), repeats=1),
    Case("hiszpański", "angielski", "red", frozenset({"network", "red", "rojo"}), repeats=1),
    Case("niemiecki", "angielski", "Gift", frozenset({"poison", "gift", "geschenk"}), repeats=2),
    Case("polski", "hiszpański", "serr", frozenset(), expect_empty=True, repeats=2),
    Case("polski", "hiszpański", "ser3", frozenset(), expect_empty=True, repeats=1),
    Case("polski", "hiszpański", "ser.", frozenset(), expect_empty=True, repeats=1),
    Case("polski", "hiszpański", "sre", frozenset(), expect_empty=True, repeats=1),
]


def fold(value: str) -> str:
    text = (value or "").casefold().strip()
    replacements = {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "ä": "a",
        "ö": "o",
        "ü": "u",
        "ß": "ss",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()


def tokens(*values: str) -> set[str]:
    out: set[str] = set()
    for value in values:
        raw = fold(value).replace(";", " ").replace(",", " ").replace("/", " ").replace("(", " ").replace(")", " ")
        out.update(part for part in raw.split() if part)
    return out


def extract_rows(content: str) -> list[dict]:
    data = json.loads(content)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        for key in ("pairs", "words", "results", "data", "items"):
            if isinstance(data.get(key), list):
                rows = data[key]
                break
        else:
            # single-object wrapper with fields
            if "word" in data:
                rows = [data]
            else:
                rows = []
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def judge(case: Case, rows: list[dict]) -> list[str]:
    problems: list[str] = []
    if case.expect_empty:
        if rows:
            problems.append(f"expected-empty-got-{len(rows)}")
        return problems

    bag = set()
    query_seen = False
    for row in rows:
        word = str(row.get("word") or "")
        translation = str(row.get("translation") or "")
        bag |= tokens(word, translation)
        if fold(case.query) in tokens(word) or fold(case.query) == fold(word):
            query_seen = True
        # also accept query as translation side if model flipped
        if fold(case.query) in tokens(translation) or fold(case.query) == fold(translation):
            query_seen = True
        required = {"word", "language", "pos", "translation", "translation_language", "translation_pos"}
        missing_fields = sorted(required - set(row.keys()))
        if missing_fields:
            problems.append(f"missing-fields:{','.join(missing_fields)}")

    if not query_seen:
        problems.append("query-not-present-in-any-row")

    missing = [token for token in case.must_cover if token not in bag]
    # soft OR for istota/byt
    if "istota" in missing and "byt" in bag:
        missing = [t for t in missing if t != "istota"]
    if "byt" in missing and "istota" in bag:
        missing = [t for t in missing if t != "byt"]
    if missing:
        problems.append("missing-tokens:" + ",".join(missing))
    return problems


async def call(llm: LLMService, case: Case) -> tuple[list[dict], int, str, str | None]:
    user = USER.format(language_1=case.language_1, language_2=case.language_2, query=case.query)
    started = time.perf_counter()
    # Try json_object first (OpenAI constraint). If model wraps array, fine.
    # Also try without response_format fallback on parse fail? Keep one path.
    response = await llm.client.chat.completions.create(
        model="gpt-6-luna",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=900,
        reasoning_effort="low",
        service_tier="priority",
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    content = response.choices[0].message.content or "[]"
    parse_error = None
    try:
        rows = extract_rows(content)
    except Exception as exc:  # noqa: BLE001
        rows = []
        parse_error = str(exc)
    return rows, elapsed_ms, content, parse_error


async def main() -> None:
    llm = LLMService()
    passed = 0
    total = 0
    times: list[int] = []
    for case in CASES:
        for round_idx in range(case.repeats):
            total += 1
            rows, elapsed_ms, raw, parse_error = await call(llm, case)
            times.append(elapsed_ms)
            problems = judge(case, rows)
            if parse_error:
                problems.append(f"parse-error:{parse_error}")
            ok = not problems
            passed += int(ok)
            print(
                json.dumps(
                    {
                        "ok": ok,
                        "round": round_idx + 1,
                        "pair": f"{case.language_1}>{case.language_2}",
                        "query": case.query,
                        "elapsed_ms": elapsed_ms,
                        "problems": problems,
                        "rows": rows,
                        "raw_preview": raw[:400],
                    },
                    ensure_ascii=False,
                )
            )
    print(
        json.dumps(
            {
                "passed": passed,
                "total": total,
                "avg_ms": round(sum(times) / len(times)) if times else 0,
                "min_ms": min(times) if times else 0,
                "max_ms": max(times) if times else 0,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())

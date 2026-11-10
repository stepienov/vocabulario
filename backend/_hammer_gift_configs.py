"""Hammer Gift (+ ser.) with same prompt across models/params."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from app.services.llm import LLMService

SYSTEM = """Jesteś precyzyjnym asystentem językowym. Twoim zadaniem jest tworzenie list dwujęzycznych par słów dla podanego hasła.

Zasady:
- Dostajesz dwa języki (język_1 i język_2) oraz hasło.
- Porównuj hasło znak w znak. Nie poprawiaj, nie normalizuj i nie usuwaj żadnych znaków.
- Nie uwzględniaj odmian, literówek ani podobnych słów.
- Sprawdź oba języki osobno i zawsze do końca.
- Zwracasz wyłącznie pary, w których hasło istnieje jako samodzielne hasło słownikowe w języku 1 albo w języku 2.
- Jeśli hasło ma kilka znaczeń lub części mowy, uwzględnij wszystkie istotne.
- W każdej parze:
  - word zawsze w języku 2
  - translation zawsze w języku 1
  - pos to część mowy słowa word
  - language to dokładna nazwa języka 2
  - translation_language to dokładna nazwa języka 1
- Jeśli hasło jest w języku 1: translation = to hasło, word = jego zwykłe tłumaczenie na język 2.
- Jeśli hasło jest w języku 2: word = to hasło w formie słownikowej, translation = tłumaczenie na język 1.
- Rzeczownik w języku 2 dostaje wymagany rodzajnik w word (el/la, le/la/l', der/die/das itd.).
- Odpowiadaj wyłącznie poprawnym JSON-em. Żadnego dodatkowego tekstu, komentarzy ani markdown.
- Zawsze zwracaj jeden obiekt z kluczem pairs.

JSON:
{"pairs":[{"word":"...","language":"...","pos":"...","translation":"...","translation_language":"..."}]}

Jeśli identyczne hasło nie istnieje w żadnym języku:
{"pairs":[]}"""

USER = """Języki: {language_1}, {language_2}
Hasło: {query}

Zwróć wyłącznie JSON:
{{"pairs":[{{"word":"...","language":"...","pos":"...","translation":"...","translation_language":"..."}}]}}"""


@dataclass(frozen=True)
class QueryCase:
    name: str
    language_1: str
    language_2: str
    query: str
    want_tokens: frozenset[str]
    expect_empty: bool = False


CASES = [
    QueryCase(
        "Gift_DE-EN",
        "niemiecki",
        "angielski",
        "Gift",
        frozenset({"poison", "gift", "geschenk"}),
    ),
    QueryCase(
        "gift_lower_DE-EN",
        "niemiecki",
        "angielski",
        "gift",
        frozenset({"gift", "geschenk"}),
    ),
    QueryCase(
        "ser_dot",
        "polski",
        "hiszpański",
        "ser.",
        frozenset(),
        expect_empty=True,
    ),
]


@dataclass(frozen=True)
class Config:
    label: str
    model: str
    reasoning_effort: str | None = None
    service_tier: str | None = "priority"
    max_completion_tokens: int = 800
    temperature: float | None = None
    repeats: int = 2


CONFIGS = [
    Config("luna/low/prio", "gpt-6-luna", "low", "priority", 800, None, 3),
    Config("luna/none/prio", "gpt-6-luna", "none", "priority", 800, None, 2),
    Config("luna/medium/prio", "gpt-6-luna", "medium", "priority", 1200, None, 2),
    Config("luna/low/default", "gpt-6-luna", "low", None, 800, None, 2),
    Config("5.6-luna/low/prio", "gpt-5.6-luna", "low", "priority", 800, None, 2),
    Config("5.6-luna/none/prio", "gpt-5.6-luna", "none", "priority", 600, None, 2),
    Config("5.6-terra/low/prio", "gpt-5.6-terra", "low", "priority", 800, None, 2),
    Config("5.6-terra/none/prio", "gpt-5.6-terra", "none", "priority", 600, None, 2),
    Config("5.6-sol/low/prio", "gpt-5.6-sol", "low", "priority", 800, None, 2),
    Config("6-sol/low/prio", "gpt-6-sol", "low", "priority", 800, None, 2),
    Config("6-astra/low/prio", "gpt-6-astra", "low", "priority", 800, None, 2),
    Config("6.1-terra/low/prio", "gpt-6.1-terra", "low", "priority", 800, None, 2),
    Config("5.4-mini/low/prio", "gpt-5.4-mini", "low", "priority", 800, None, 2),
    Config("5.4-nano/low/prio", "gpt-5.4-nano", "low", "priority", 800, None, 2),
    Config("4.1-mini/temp0/prio", "gpt-4.1-mini", None, "priority", 800, 0.0, 2),
    Config("4.1/temp0/prio", "gpt-4.1", None, "priority", 800, 0.0, 2),
]


def fold(value: str) -> str:
    text = (value or "").casefold().strip()
    for src, dst in {
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
    }.items():
        text = text.replace(src, dst)
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()


def bag_of_tokens(rows: list[dict]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for key in ("word", "translation"):
            raw = fold(str(row.get(key) or "")).replace(",", " ").replace(";", " ").replace("/", " ")
            out.update(part for part in raw.split() if part)
            # strip articles
            parts = [p for p in raw.split() if p]
            if len(parts) >= 2 and parts[0] in {"el", "la", "das", "der", "die", "the", "a", "an", "to"}:
                out.add(parts[1])
    return out


def extract_rows(content: str) -> list[dict]:
    data = json.loads(content)
    if isinstance(data, dict) and isinstance(data.get("pairs"), list):
        return [r for r in data["pairs"] if isinstance(r, dict)]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


def judge(case: QueryCase, rows: list[dict]) -> list[str]:
    if case.expect_empty:
        return [f"expected-empty-got-{len(rows)}"] if rows else []
    bag = bag_of_tokens(rows)
    missing = [t for t in case.want_tokens if t not in bag]
    return [f"missing:{','.join(missing)}"] if missing else []


async def one_call(
    llm: LLMService,
    cfg: Config,
    case: QueryCase,
) -> dict[str, Any]:
    user = USER.format(
        language_1=case.language_1,
        language_2=case.language_2,
        query=case.query,
    )
    kwargs: dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": cfg.max_completion_tokens,
    }
    if cfg.reasoning_effort is not None:
        kwargs["reasoning_effort"] = cfg.reasoning_effort
    if cfg.service_tier is not None:
        kwargs["service_tier"] = cfg.service_tier
    if cfg.temperature is not None:
        kwargs["temperature"] = cfg.temperature

    started = time.perf_counter()
    try:
        response = await llm.client.chat.completions.create(**kwargs)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        content = response.choices[0].message.content or "{}"
        rows = extract_rows(content)
        problems = judge(case, rows)
        return {
            "ok": not problems,
            "config": cfg.label,
            "case": case.name,
            "query": case.query,
            "elapsed_ms": elapsed_ms,
            "problems": problems,
            "pairs": rows,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "config": cfg.label,
            "case": case.name,
            "query": case.query,
            "elapsed_ms": elapsed_ms,
            "problems": [f"error:{type(exc).__name__}:{exc}"],
            "pairs": [],
        }


async def main() -> None:
    llm = LLMService()
    summary: dict[str, dict[str, int]] = {}
    for cfg in CONFIGS:
        for case in CASES:
            key = f"{cfg.label}|{case.name}"
            summary[key] = {"pass": 0, "fail": 0, "ms_sum": 0}
            for round_idx in range(cfg.repeats):
                result = await one_call(llm, cfg, case)
                summary[key]["pass" if result["ok"] else "fail"] += 1
                summary[key]["ms_sum"] += int(result["elapsed_ms"])
                print(
                    json.dumps(
                        {
                            "ok": result["ok"],
                            "round": round_idx + 1,
                            "config": result["config"],
                            "case": result["case"],
                            "elapsed_ms": result["elapsed_ms"],
                            "problems": result["problems"],
                            "pairs": result["pairs"],
                        },
                        ensure_ascii=False,
                    )
                )

    rollup = []
    for key, stats in summary.items():
        total = stats["pass"] + stats["fail"]
        rollup.append(
            {
                "key": key,
                "passed": stats["pass"],
                "total": total,
                "avg_ms": round(stats["ms_sum"] / total) if total else 0,
            }
        )
    print(json.dumps({"rollup": rollup}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

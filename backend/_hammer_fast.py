"""Fast parallel hammer: Gift + ser. across few configs."""
from __future__ import annotations

import asyncio
import json
import time
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

CASES = [
    ("Gift", "niemiecki", "angielski", {"poison", "gift", "geschenk"}, False),
    ("gift", "niemiecki", "angielski", {"gift", "geschenk"}, False),
    ("ser.", "polski", "hiszpański", set(), True),
]

CONFIGS = [
    ("6luna/low", "gpt-6-luna", "low", "priority", None),
    ("6luna/none", "gpt-6-luna", "none", "priority", None),
    ("6luna/med", "gpt-6-luna", "medium", "priority", None),
    ("56luna/low", "gpt-5.6-luna", "low", "priority", None),
    ("56terra/none", "gpt-5.6-terra", "none", "priority", None),
    ("56sol/low", "gpt-5.6-sol", "low", "priority", None),
    ("6sol/low", "gpt-6-sol", "low", "priority", None),
    ("6astra/low", "gpt-6-astra", "low", "priority", None),
    ("61terra/low", "gpt-6.1-terra", "low", "priority", None),
    ("54mini/low", "gpt-5.4-mini", "low", "priority", None),
    ("4.1mini/0", "gpt-4.1-mini", None, "priority", 0.0),
    ("4.1/0", "gpt-4.1", None, "priority", 0.0),
]


def fold(v: str) -> str:
    t = (v or "").casefold()
    for a, b in {"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}.items():
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalnum() or ch.isspace())


def tokens(rows: list[dict]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for key in ("word", "translation"):
            parts = fold(str(row.get(key) or "")).replace(",", " ").split()
            out.update(parts)
            if len(parts) >= 2 and parts[0] in {"el", "la", "das", "der", "die", "the", "a", "an", "to"}:
                out.add(parts[1])
    return out


async def call(llm: LLMService, cfg: tuple, case: tuple) -> dict[str, Any]:
    label, model, effort, tier, temp = cfg
    query, l1, l2, want, empty = case
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": USER.format(language_1=l1, language_2=l2, query=query),
            },
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 700,
    }
    if effort is not None:
        kwargs["reasoning_effort"] = effort
    if tier is not None:
        kwargs["service_tier"] = tier
    if temp is not None:
        kwargs["temperature"] = temp
    t0 = time.perf_counter()
    try:
        resp = await llm.client.chat.completions.create(**kwargs)
        ms = round((time.perf_counter() - t0) * 1000)
        data = json.loads(resp.choices[0].message.content or "{}")
        rows = data.get("pairs") if isinstance(data, dict) else []
        if not isinstance(rows, list):
            rows = []
        bag = tokens(rows)
        if empty:
            problems = [f"got-{len(rows)}"] if rows else []
        else:
            missing = sorted(want - bag)
            problems = [f"missing:{','.join(missing)}"] if missing else []
        return {
            "ok": not problems,
            "cfg": label,
            "q": query,
            "ms": ms,
            "problems": problems,
            "n": len(rows),
            "pairs": rows,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "cfg": label,
            "q": query,
            "ms": round((time.perf_counter() - t0) * 1000),
            "problems": [f"err:{exc}"],
            "n": 0,
            "pairs": [],
        }


async def main() -> None:
    llm = LLMService()
    jobs = [(cfg, case) for cfg in CONFIGS for case in CASES for _ in range(2)]
    results = await asyncio.gather(*(call(llm, cfg, case) for cfg, case in jobs))
    for r in results:
        print(json.dumps(r, ensure_ascii=False))

    roll: dict[str, list[int]] = {}
    for r in results:
        key = f"{r['cfg']}|{r['q']}"
        roll.setdefault(key, [0, 0, 0])  # pass, total, ms
        roll[key][1] += 1
        roll[key][0] += int(r["ok"])
        roll[key][2] += int(r["ms"])
    print(
        json.dumps(
            {
                "rollup": [
                    {
                        "key": k,
                        "passed": v[0],
                        "total": v[1],
                        "avg_ms": round(v[2] / v[1]),
                    }
                    for k, v in roll.items()
                ]
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())

"""Same prompt, less thinking, shorter output cap."""
import asyncio
import json
import time
from typing import Any

from app.services.llm import LLMService
from _run_exact_tiles import SYSTEM, USER, Case, judge

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
    Case("niemiecki", "angielski", "Gift", frozenset({("poison", "gift"), ("gift", "geschenk")})),
    Case("polski", "hiszpański", "serr", frozenset()),
    Case("polski", "hiszpański", "ser.", frozenset({("queso", "ser"), ("ser", "byc")}), soft_empty=True),
]

CONFIGS = [
    ("6sol/none/250", "gpt-6-sol", "none", 250),
    ("6luna/none/250", "gpt-6-luna", "none", 250),
    ("56luna/none/250", "gpt-5.6-luna", "none", 250),
    ("6sol/low/250", "gpt-6-sol", "low", 250),
    ("4.1/0/250", "gpt-4.1", None, 250),
]


async def one(llm: LLMService, cfg: tuple, case: Case) -> dict[str, Any]:
    label, model, effort, limit = cfg
    user = USER.format(language_1=case.language_1, language_2=case.language_2, query=case.query)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": limit,
        "service_tier": "priority",
    }
    if effort is not None:
        kwargs["reasoning_effort"] = effort
    else:
        kwargs["temperature"] = 0
    t0 = time.perf_counter()
    try:
        resp = await llm.client.chat.completions.create(**kwargs)
        ms = round((time.perf_counter() - t0) * 1000)
        data = json.loads(resp.choices[0].message.content or "{}")
        rows = [r for r in (data.get("pairs") or []) if isinstance(r, dict)] if isinstance(data, dict) else []
        problems = judge(case, rows)
        return {"ok": not problems, "cfg": label, "q": case.query, "ms": ms, "problems": problems, "n": len(rows), "pairs": rows}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "cfg": label, "q": case.query, "ms": round((time.perf_counter() - t0) * 1000), "problems": [f"err:{exc}"], "n": 0, "pairs": []}


async def main() -> None:
    llm = LLMService()
    rows = await asyncio.gather(*(one(llm, cfg, case) for cfg in CONFIGS for case in CASES))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    roll: dict[str, list[int]] = {}
    for row in rows:
        slot = roll.setdefault(row["cfg"], [0, 0, 0])
        slot[1] += 1
        slot[0] += int(row["ok"])
        slot[2] += int(row["ms"])
    print(json.dumps({
        "summary": [
            {"cfg": k, "passed": v[0], "total": v[1], "avg_ms": round(v[2] / v[1])}
            for k, v in roll.items()
        ]
    }))


if __name__ == "__main__":
    asyncio.run(main())

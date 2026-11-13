import asyncio
import json
import time

from app.services.llm import LLMService
from _run_exact_tiles import SYSTEM, USER, judge, Case

CASE = Case(
    "polski",
    "hiszpański",
    "droga",
    frozenset({("camino", "droga"), ("carretera", "droga"), ("droga", "narkotyk")}),
    forbid_word=frozenset({"caro", "cara", "querida"}),
)


async def main() -> None:
    llm = LLMService()
    user = USER.format(language_1="polski", language_2="hiszpański", query="droga")
    for i in range(1, 6):
        t0 = time.perf_counter()
        resp = await llm.client.chat.completions.create(
            model="gpt-6-sol",
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_completion_tokens=500,
            reasoning_effort="low",
            service_tier="priority",
        )
        ms = round((time.perf_counter() - t0) * 1000)
        data = json.loads(resp.choices[0].message.content or "{}")
        rows = [r for r in (data.get("pairs") or []) if isinstance(r, dict)]
        print(json.dumps({"round": i, "ms": ms, "ok": not judge(CASE, rows), "problems": judge(CASE, rows), "pairs": rows}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import time

from app.services.llm import LLMService
from _run_exact_tiles import SYSTEM, USER


async def main() -> None:
    llm = LLMService()
    user = USER.format(language_1="polski", language_2="hiszpański", query="para")
    for i in range(1, 6):
        t0 = time.perf_counter()
        resp = await llm.client.chat.completions.create(
            model="gpt-5.6-luna",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=800,
            reasoning_effort="low",
            service_tier="priority",
        )
        ms = round((time.perf_counter() - t0) * 1000)
        data = json.loads(resp.choices[0].message.content or "{}")
        pairs = data.get("pairs") if isinstance(data, dict) else []
        if not isinstance(pairs, list):
            pairs = []
        words = [str(p.get("word") or "") for p in pairs if isinstance(p, dict)]
        has_el_par = any(
            w.casefold().strip() in {"par", "el par"}
            or w.casefold().removeprefix("el ").strip() == "par"
            for w in words
        )
        print(
            json.dumps(
                {"round": i, "ms": ms, "has_el_par": has_el_par, "pairs": pairs},
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

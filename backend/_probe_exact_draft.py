"""Probe exact-only lookup_draft (light model) for ser / serr / drogie32."""
import asyncio
import json
import time

from app.services.llm import LLMService


QUERIES = ["ser", "serr", "drogie32", "el ser"]


async def main() -> None:
    llm = LLMService()
    for q in QUERIES:
        t0 = time.perf_counter()
        rows = await llm.lookup_draft(q, "pl", "es")
        ms = int((time.perf_counter() - t0) * 1000)
        print(f"==== {q!r} {ms}ms n={len(rows)}")
        for row in rows:
            print(" ", json.dumps(row, ensure_ascii=False))
        print()


if __name__ == "__main__":
    asyncio.run(main())

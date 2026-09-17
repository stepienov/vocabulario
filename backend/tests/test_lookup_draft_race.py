"""First-paint lookup: wiki + light model race within a short budget."""

import asyncio
import time

from app.services.lexical import collect_first_lookup_hits


def _run(coro):
    return asyncio.run(coro)


def test_dict_hits_return_without_waiting_for_slow_ai():
    async def dict_src():
        await asyncio.sleep(0.04)
        return [{"lemma": "casa"}]

    async def ai_src():
        await asyncio.sleep(2)
        return [{"lemma": "house"}]

    async def _run_case():
        started = time.perf_counter()
        hits = await collect_first_lookup_hits(
            {
                "dict": asyncio.create_task(dict_src()),
                "ai": asyncio.create_task(ai_src()),
            },
            budget_s=1.0,
        )
        return time.perf_counter() - started, hits

    elapsed, hits = _run(_run_case())
    assert hits["dict"][0]["lemma"] == "casa"
    assert hits["ai"] == []
    assert elapsed < 0.5


def test_empty_dict_waits_for_ai():
    async def dict_src():
        await asyncio.sleep(0.02)
        return []

    async def ai_src():
        await asyncio.sleep(0.08)
        return [{"lemma": "libro"}]

    async def _run_case():
        return await collect_first_lookup_hits(
            {
                "dict": asyncio.create_task(dict_src()),
                "ai": asyncio.create_task(ai_src()),
            },
            budget_s=1.0,
        )

    hits = _run(_run_case())
    assert hits["dict"] == []
    assert hits["ai"][0]["lemma"] == "libro"


def test_waits_for_dict_after_early_ai():
    async def dict_src():
        await asyncio.sleep(0.12)
        return [{"lemma": "casa"}]

    async def ai_src():
        await asyncio.sleep(0.02)
        return [{"lemma": "house"}]

    async def _run_case():
        return await collect_first_lookup_hits(
            {
                "dict": asyncio.create_task(dict_src()),
                "ai": asyncio.create_task(ai_src()),
            },
            budget_s=1.0,
        )

    hits = _run(_run_case())
    assert hits["dict"][0]["lemma"] == "casa"
    assert hits["ai"][0]["lemma"] == "house"


def test_timeout_cancels_hanging_sources():
    async def hang():
        await asyncio.sleep(10)
        return [{"lemma": "late"}]

    async def _run_case():
        started = time.perf_counter()
        hits = await collect_first_lookup_hits(
            {
                "dict": asyncio.create_task(hang()),
                "ai": asyncio.create_task(hang()),
            },
            budget_s=0.12,
        )
        return time.perf_counter() - started, hits

    elapsed, hits = _run(_run_case())
    assert hits["dict"] == []
    assert hits["ai"] == []
    assert elapsed < 0.6


def test_failed_dict_still_returns_ai():
    async def dict_src():
        raise RuntimeError("wiki down")

    async def ai_src():
        await asyncio.sleep(0.02)
        return [{"lemma": "casa"}]

    async def _run_case():
        return await collect_first_lookup_hits(
            {
                "dict": asyncio.create_task(dict_src()),
                "ai": asyncio.create_task(ai_src()),
            },
            budget_s=1.0,
        )

    hits = _run(_run_case())
    assert hits["dict"] == []
    assert hits["ai"][0]["lemma"] == "casa"


def test_lookup_draft_mock_returns_candidates():
    from app.services.llm import LLMService

    llm = LLMService()
    llm.mock = True

    async def _run_case():
        return await llm.lookup_draft("ksiazka", "pl", "es", "A2")

    cands = _run(_run_case())
    assert cands
    assert cands[0]["lemma"] == "ksiazka"

"""Lookup expand musi przeżyć anulowanie handlera HTTP."""

import asyncio
from uuid import uuid4

from app.services.lexical import LookupOutcome
from app.services import lookup_jobs


def test_waiter_cancel_does_not_stop_expand(monkeypatch):
    started = asyncio.Event()
    finished = asyncio.Event()
    outcome = LookupOutcome(candidates=[{"lemma": "casa"}], source="ai", ai_complete=True)

    async def fake_run(user_id, profile_id, text):
        started.set()
        await asyncio.sleep(0.05)
        finished.set()
        return outcome

    monkeypatch.setattr(lookup_jobs, "_run_expand", fake_run)
    lookup_jobs._inflight.clear()

    async def _run() -> None:
        user_id = uuid4()
        profile_id = uuid4()
        task = lookup_jobs.ensure_expand_task(user_id, profile_id, "casa")

        async def waiter():
            await asyncio.shield(task)

        pending = asyncio.create_task(waiter())
        await started.wait()
        pending.cancel()
        try:
            await pending
        except asyncio.CancelledError:
            pass
        await asyncio.wait_for(finished.wait(), timeout=1)
        assert task.done()
        assert await task == outcome

    asyncio.run(_run())


def test_ensure_expand_task_reuses_inflight(monkeypatch):
    calls = {"n": 0}
    gate = asyncio.Event()

    async def fake_run(user_id, profile_id, text):
        calls["n"] += 1
        await gate.wait()
        return LookupOutcome([], "db", True)

    monkeypatch.setattr(lookup_jobs, "_run_expand", fake_run)
    lookup_jobs._inflight.clear()

    async def _run() -> None:
        user_id = uuid4()
        profile_id = uuid4()
        a = lookup_jobs.ensure_expand_task(user_id, profile_id, "hola")
        await asyncio.sleep(0)
        b = lookup_jobs.ensure_expand_task(user_id, profile_id, "HOLA")
        assert a is b
        assert calls["n"] == 1
        gate.set()
        await a

    asyncio.run(_run())

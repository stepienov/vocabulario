"""Lookup expand musi przeżyć anulowanie handlera HTTP."""

import asyncio
from uuid import uuid4

from app.services.lexical import LookupOutcome
from app.services import lookup_jobs


def test_waiter_cancel_does_not_stop_expand(monkeypatch):
    started = asyncio.Event()
    finished = asyncio.Event()
    outcome = LookupOutcome(candidates=[{"lemma": "casa"}], source="ai", ai_complete=True)

    async def fake_run(user_id, profile_id, text, more=False):
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

    async def fake_run(user_id, profile_id, text, more=False):
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


def test_more_uses_its_own_inflight_task(monkeypatch):
    gate = asyncio.Event()

    async def fake_run(user_id, profile_id, text, more=False):
        await gate.wait()
        return LookupOutcome([], "db", True)

    monkeypatch.setattr(lookup_jobs, "_run_expand", fake_run)
    lookup_jobs._inflight.clear()

    async def _run() -> None:
        user_id = uuid4()
        profile_id = uuid4()
        plain = lookup_jobs.ensure_expand_task(user_id, profile_id, "pies", more=False)
        extra = lookup_jobs.ensure_expand_task(user_id, profile_id, "pies", more=True)
        again = lookup_jobs.ensure_expand_task(user_id, profile_id, "PIES", more=True)
        assert plain is not extra
        assert extra is again
        gate.set()
        await plain
        await extra

    asyncio.run(_run())


def test_lookup_expand_sends_a_short_prompt_without_temperature():
    from types import SimpleNamespace

    from app.services.llm import LLMService

    seen: dict = {}

    async def create(**kwargs):
        seen.update(kwargs)
        message = SimpleNamespace(content='{"candidates":[]}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None, id=None)

    llm = LLMService()
    llm.mock = False
    llm.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    result = asyncio.run(
        llm.lookup_expand(
            "pies",
            "pl",
            "es",
            [{"lemma": "el perro", "pos": "noun", "gloss": "pies"}],
        )
    )
    assert result == []
    assert seen["model"] == "gpt-6-sol"
    assert seen["reasoning_effort"] == "low"
    assert seen["max_completion_tokens"] == 1200
    assert seen["service_tier"] == "priority"
    assert "temperature" not in seen
    assert "Bilingual dictionary lookup" in seen["messages"][0]["content"]
    assert "Already stored" in seen["messages"][1]["content"]
    assert "el perro" in seen["messages"][1]["content"]
    asyncio.run(llm.lookup_expand("Haus", "de", "en"))
    assert "el perro" not in seen["messages"][1]["content"]


import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.models import LookupQueryCache
from app.services.lexical import LexicalService
from app.services.llm import LLMService
from app.services.lookup_candidates import normalize_lookup_query
from tests.pg_factories import auth_headers, create_card, create_profile, create_user


async def _ready(pg, *, complete: bool, candidates: list[dict]):
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        row = LookupQueryCache(
            lang_pair="pl>es",
            input_norm=normalize_lookup_query("pies"),
            candidates=candidates,
            ai_complete=complete,
            hit_count=2,
        )
        session.add(row)
        await session.commit()
        return user.id, profile.id, row.id


@pytest.mark.pg
async def test_complete_row_skips_the_model_until_more(pg, monkeypatch):
    calls = {"n": 0}

    async def fake(self, text, native, learning, already=None):
        calls["n"] += 1
        seen = already
        return [{"lemma": "el pie", "pos": "noun", "gloss": "stopa"}] if seen is not None else []

    monkeypatch.setattr(LLMService, "lookup_expand", fake)
    user_id, profile_id, row_id = await _ready(
        pg,
        complete=True,
        candidates=[{"lemma": "el perro", "pos": "noun", "gloss": "pies"}],
    )
    async with pg() as session:
        outcome = await LexicalService(session).lookup_expand(user_id, profile_id, "pies")
    assert calls["n"] == 0
    assert outcome.added == 0
    assert outcome.ai_complete is True

    async def more(self, text, native, learning, already=None):
        calls["n"] += 1
        calls["already"] = already
        return [{"lemma": "el pie", "pos": "noun", "gloss": "stopa"}]

    monkeypatch.setattr(LLMService, "lookup_expand", more)
    async with pg() as session:
        outcome = await LexicalService(session).lookup_expand(
            user_id, profile_id, "pies", more=True
        )
        await session.commit()
    assert calls["n"] == 1
    assert calls["already"][0]["lemma"] == "el perro"
    assert outcome.added == 1
    assert outcome.source == "ai"
    async with pg() as session:
        stored = await session.get(LookupQueryCache, row_id)
    lemmas = {item["lemma"] for item in stored.candidates}
    assert lemmas == {"el perro", "el pie"}
    assert stored.ai_complete is True


@pytest.mark.pg
async def test_expand_does_not_store_a_repeated_candidate(pg, monkeypatch):
    async def fake(self, text, native, learning, already=None):
        return [{"lemma": "el perro", "pos": "noun", "gloss": "pies"}]

    monkeypatch.setattr(LLMService, "lookup_expand", fake)
    user_id, profile_id, row_id = await _ready(
        pg,
        complete=False,
        candidates=[{"lemma": "el perro", "pos": "noun", "gloss": "pies"}],
    )
    async with pg() as session:
        outcome = await LexicalService(session).lookup_expand(user_id, profile_id, "pies")
        await session.commit()
    assert outcome.added == 0
    async with pg() as session:
        stored = await session.get(LookupQueryCache, row_id)
    assert [item["lemma"] for item in stored.candidates] == ["el perro"]


@pytest.mark.pg
async def test_more_keeps_a_word_written_while_the_model_runs(pg, monkeypatch):
    user_id, profile_id, row_id = await _ready(
        pg,
        complete=False,
        candidates=[{"lemma": "el perro", "pos": "noun", "gloss": "pies"}],
    )

    async def fake(self, text, native, learning, already=None):
        async with pg() as other:
            row = await other.get(LookupQueryCache, row_id)
            row.candidates = list(row.candidates or []) + [
                {"lemma": "el pie", "pos": "noun", "gloss": "stopa"}
            ]
            row.ai_complete = True
            flag_modified(row, "candidates")
            await other.commit()
        return [{"lemma": "la pata", "pos": "noun", "gloss": "łapa"}]

    monkeypatch.setattr(LLMService, "lookup_expand", fake)
    async with pg() as session:
        outcome = await LexicalService(session).lookup_expand(
            user_id, profile_id, "pies", more=True
        )
        await session.commit()
    assert {"el perro", "el pie", "la pata"} <= {item["lemma"] for item in outcome.candidates}


@pytest.mark.pg
async def test_expand_does_not_hold_a_pooled_connection(pg, monkeypatch):
    from app.db import session as db_session

    user_id, profile_id, _row_id = await _ready(pg, complete=False, candidates=[])
    seen: dict[str, int] = {}

    async def fake(self, text, native, learning, already=None):
        seen["checkedout"] = db_session.engine.pool.checkedout()
        return [{"lemma": "el perro", "pos": "noun", "gloss": "pies"}]

    monkeypatch.setattr(LLMService, "lookup_expand", fake)
    before = db_session.engine.pool.checkedout()
    async with pg() as session:
        outcome = await LexicalService(session).lookup_expand(user_id, profile_id, "pies")
        await session.commit()
    assert seen["checkedout"] == before
    assert outcome.added == 1


@pytest.mark.pg
async def test_expand_annotates_only_without_local_membership(pg, pg_client, monkeypatch):
    async def fake(self, text, native, learning, already=None):
        raise AssertionError("model")

    monkeypatch.setattr(LLMService, "lookup_expand", fake)
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        card = await create_card(session, profile, "el prado", "noun")
        session.add(
            LookupQueryCache(
                lang_pair="pl>es",
                input_norm=normalize_lookup_query("prado"),
                candidates=[{"lemma": "el prado", "pos": "noun", "gloss": "łąka"}],
                ai_complete=True,
                hit_count=1,
            )
        )
        await session.commit()
        headers = auth_headers(user)
        profile_id = str(profile.id)
        card_id = str(card.id)

    payload = {"text": "prado", "profile_id": profile_id}
    plain = await pg_client.post("/api/v1/lookup/expand", headers=headers, json=payload)
    local = await pg_client.post(
        "/api/v1/lookup/expand",
        headers=headers,
        json={**payload, "local_membership": True},
    )
    assert plain.status_code == 200
    assert local.status_code == 200
    assert plain.json()["added"] == 0
    assert local.json()["added"] == 0
    plain_match = plain.json()["candidates"][0]
    local_match = local.json()["candidates"][0]
    assert plain_match["learning_card_id"] == card_id
    assert local_match["learning_card_id"] is None
    assert local_match["in_learning"] is False

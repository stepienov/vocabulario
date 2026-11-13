"""Pierwsze słowo: leksykon, a przy braku trafienia jeden szkic luny."""

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import LexicalEntry, LookupQueryCache
from app.services.llm import LLMService
from tests.pg_factories import auth_headers, create_profile, create_user


def _run(coro):
    return asyncio.run(coro)


def test_lookup_draft_sends_a_short_prompt_without_temperature():
    seen: dict = {}

    async def create(**kwargs):
        seen.update(kwargs)
        message = SimpleNamespace(
            content='{"candidates":[{"lemma":"ev","pos":"noun","gloss":"casa"}]}'
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None, id=None)

    llm = LLMService()
    llm.mock = False
    llm.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    result = _run(llm.lookup_draft("casa", "pt", "tr"))
    assert result[0]["lemma"] == "ev"
    assert result[0]["gloss"] == "casa"
    assert seen["model"] == "gpt-6-sol"
    assert seen["reasoning_effort"] == "none"
    assert seen["max_completion_tokens"] == 1200
    assert seen["service_tier"] == "priority"
    assert "temperature" not in seen
    assert "Bilingual dictionary lookup" in seen["messages"][0]["content"]
    assert 'User query: "casa"' in seen["messages"][1]["content"]


def test_lookup_draft_mock_returns_candidates():
    llm = LLMService()
    llm.mock = True
    cands = _run(llm.lookup_draft("ksiazka", "pl", "es"))
    assert cands
    assert cands[0]["lemma"] == "ksiazka"


async def _caller(pg):
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        await session.commit()
        return auth_headers(user), str(profile.id)


async def _cache_rows(pg):
    async with pg() as session:
        return (
            await session.execute(select(LookupQueryCache))
        ).scalars().all()


@pytest.mark.pg
async def test_lexicon_hit_is_merged_with_one_draft(pg, pg_client, monkeypatch):
    called = {"draft": 0, "dict": 0}

    async def draft(self, text, native, learning):
        called["draft"] += 1
        return []

    async def dictionary(*args, **kwargs):
        called["dict"] += 1
        return []

    monkeypatch.setattr(LLMService, "lookup_draft", draft)
    monkeypatch.setattr(
        "app.services.dictionary_lookup.lookup_dictionary_candidates", dictionary
    )
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        session.add(
            LexicalEntry(
                lang_pair="pl>es",
                lemma_l2="el castillo",
                lemma_l1_primary="zamek",
                pos="noun",
                content={},
                source="db",
            )
        )
        await session.commit()
        headers = auth_headers(user)
        profile_id = str(profile.id)

    response = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={"text": "zamek", "profile_id": profile_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "db"
    assert body["ai_complete"] is False
    assert any(item["lemma"] == "el castillo" for item in body["candidates"])
    assert called == {"draft": 1, "dict": 0}
    rows = await _cache_rows(pg)
    assert len(rows) == 1
    assert rows[0].ai_complete is False


@pytest.mark.pg
async def test_draft_hit_is_stored_without_ai_complete(pg, pg_client, monkeypatch):
    async def draft(self, text, native, learning):
        return [{"lemma": "el castillo", "pos": "noun", "gloss": "zamek"}]

    monkeypatch.setattr(LLMService, "lookup_draft", draft)
    headers, profile_id = await _caller(pg)
    response = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={"text": "zamek", "profile_id": profile_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ai"
    assert body["ai_complete"] is False
    assert body["candidates"][0]["lemma"] == "el castillo"
    rows = await _cache_rows(pg)
    assert len(rows) == 1
    assert rows[0].candidates[0]["lemma"] == "el castillo"
    assert rows[0].ai_complete is False


@pytest.mark.pg
async def test_empty_draft_does_not_create_a_cache_row(pg, pg_client, monkeypatch):
    async def draft(self, text, native, learning):
        return []

    monkeypatch.setattr(LLMService, "lookup_draft", draft)
    headers, profile_id = await _caller(pg)
    response = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={"text": "zamek", "profile_id": profile_id},
    )
    assert response.status_code == 200
    assert response.json()["candidates"] == []
    assert await _cache_rows(pg) == []


@pytest.mark.pg
async def test_draft_exception_returns_an_empty_200(pg, pg_client, monkeypatch):
    async def draft(self, text, native, learning):
        raise RuntimeError("luna down")

    monkeypatch.setattr(LLMService, "lookup_draft", draft)
    headers, profile_id = await _caller(pg)
    response = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={"text": "zamek", "profile_id": profile_id},
    )
    assert response.status_code == 200
    assert response.json()["candidates"] == []
    assert await _cache_rows(pg) == []


@pytest.mark.pg
async def test_two_drafts_merge_into_one_cache_row(pg, pg_client, monkeypatch):
    both_inside = asyncio.Event()
    arrived = 0
    lock = asyncio.Lock()

    async def draft(self, text, native, learning):
        nonlocal arrived
        async with lock:
            arrived += 1
            mine = arrived
            if mine == 2:
                both_inside.set()
        await both_inside.wait()
        lemma = "el castillo" if mine == 1 else "la cerradura"
        return [{"lemma": lemma, "pos": "noun", "gloss": "zamek"}]

    monkeypatch.setattr(LLMService, "lookup_draft", draft)
    headers, profile_id = await _caller(pg)
    payload = {"text": "zamek", "profile_id": profile_id}
    first, second = await asyncio.gather(
        pg_client.post("/api/v1/lookup/cached", headers=headers, json=payload),
        pg_client.post("/api/v1/lookup/cached", headers=headers, json=payload),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    rows = await _cache_rows(pg)
    assert len(rows) == 1
    lemmas = {item["lemma"] for item in rows[0].candidates}
    assert lemmas == {"el castillo", "la cerradura"}


@pytest.mark.pg
async def test_draft_does_not_hold_a_pooled_connection(pg, pg_client, monkeypatch):
    from app.db import session as db_session

    started = asyncio.Event()
    release = asyncio.Event()
    seen: dict[str, int] = {}

    async def draft(self, text, native, learning):
        seen["checkedout"] = db_session.engine.pool.checkedout()
        started.set()
        await release.wait()
        return [{"lemma": "el castillo", "pos": "noun", "gloss": "zamek"}]

    monkeypatch.setattr(LLMService, "lookup_draft", draft)
    headers, profile_id = await _caller(pg)
    before = db_session.engine.pool.checkedout()
    request = asyncio.create_task(
        pg_client.post(
            "/api/v1/lookup/cached",
            headers=headers,
            json={"text": "zamek", "profile_id": profile_id},
        )
    )
    await asyncio.wait_for(started.wait(), timeout=5)
    assert seen["checkedout"] == before
    release.set()
    response = await request
    assert response.status_code == 200

"""Szybka gałąź lookup/cached: jeden SELECT, bez pól nauki."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.models import LookupEvent, LookupQueryCache
from app.services.background import drain_background
from app.services.lexical import LexicalService
from app.services.lookup_candidates import normalize_lookup_query
from tests.pg_factories import auth_headers, create_card, create_profile, create_user

pytestmark = pytest.mark.pg

_CANDIDATES = [
    {"lemma": "el prado", "pos": "noun", "gloss": "łąka"},
    {"lemma": "prado", "pos": "noun", "gloss": "łąka"},
]


async def _ready_row(session, profile):
    row = LookupQueryCache(
        lang_pair=f"{profile.app_lang}>{profile.learning_lang}",
        input_norm=normalize_lookup_query("prado"),
        candidates=list(_CANDIDATES),
        ai_complete=True,
        hit_count=4,
    )
    session.add(row)
    await session.commit()
    return row


async def test_fast_path_skips_learning_fields_and_uses_one_select(pg, pg_client):
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        await create_card(session, profile, "el prado", "noun")
        await _ready_row(session, profile)
        headers = auth_headers(user)
        profile_id = profile.id

    from app.db import session as db_session

    selects: list[str] = []

    def _before(conn, cursor, statement, parameters, context, executemany):
        sql = statement.lstrip().lower()
        if sql.startswith("select") and "language_profiles" in sql:
            selects.append(statement)

    event.listen(db_session.engine.sync_engine, "before_cursor_execute", _before)
    try:
        response = await pg_client.post(
            "/api/v1/lookup/cached",
            headers=headers,
            json={
                "text": "prado",
                "profile_id": str(profile_id),
                "local_membership": True,
            },
        )
    finally:
        event.remove(db_session.engine.sync_engine, "before_cursor_execute", _before)

    assert response.status_code == 200
    body = response.json()
    assert body["ai_complete"] is True
    assert body["source"] == "db"
    assert body["candidates"]
    assert selects and len(selects) == 1
    for candidate in body["candidates"]:
        assert candidate["learning_card_id"] is None
        assert candidate["list_id"] is None
        assert candidate["list_name"] is None
        assert candidate["in_learning"] is False


async def test_default_membership_still_annotates_the_card(pg, pg_client):
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        card = await create_card(session, profile, "el prado", "noun")
        await _ready_row(session, profile)
        headers = auth_headers(user)
        profile_id = profile.id
        card_id = card.id

    response = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={"text": "prado", "profile_id": str(profile_id)},
    )
    assert response.status_code == 200
    match = next(
        item for item in response.json()["candidates"] if item["lemma"] == "el prado"
    )
    assert match["learning_card_id"] == str(card_id)
    assert match["list_name"]


async def test_fast_and_annotated_paths_rank_the_same_way(pg):
    from app.models import User

    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        await _ready_row(session, profile)
        user_id = user.id
        profile_id = profile.id
        fast = await LexicalService(session).lookup_cached_fast(user_id, profile_id, "prado")
    async with pg() as session:
        user = await session.get(User, user_id)
        slow = await LexicalService(session).lookup_cached(
            user, profile_id, "prado", annotate=False
        )
    assert fast is not None
    assert [item["lemma"] for item in fast.candidates] == [
        item["lemma"] for item in slow.candidates
    ]


async def test_background_history_bumps_hit_count_once(pg, pg_client):
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        row = await _ready_row(session, profile)
        headers = auth_headers(user)
        profile_id = profile.id
        row_id = row.id

    response = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={
            "text": "prado",
            "profile_id": str(profile_id),
            "local_membership": True,
        },
    )
    assert response.status_code == 200
    await drain_background(2)
    async with pg() as session:
        stored = await session.get(LookupQueryCache, row_id)
        events = (
            await session.execute(
                select(LookupEvent).where(LookupEvent.profile_id == profile_id)
            )
        ).scalars().all()
    assert stored is not None
    assert stored.hit_count == 5
    assert len(events) == 1
    assert events[0].source == "db"
    assert events[0].ai_complete is True
    assert events[0].request_id is not None


async def test_two_cached_lookups_bump_hit_count_by_two(pg, pg_client):
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        row = await _ready_row(session, profile)
        headers = auth_headers(user)
        profile_id = str(profile.id)
        row_id = row.id

    payload = {"text": "prado", "profile_id": profile_id, "local_membership": True}
    first, second = await asyncio.gather(
        pg_client.post("/api/v1/lookup/cached", headers=headers, json=payload),
        pg_client.post("/api/v1/lookup/cached", headers=headers, json=payload),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    await drain_background(2)
    async with pg() as session:
        stored = await session.get(LookupQueryCache, row_id)
    assert stored is not None
    assert stored.hit_count == 6


async def test_missing_user_is_404_on_fast_path_and_401_otherwise(pg, pg_client):
    from app.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token(uuid4())}"}
    profile_id = str(uuid4())
    fast = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={"text": "prado", "profile_id": profile_id, "local_membership": True},
    )
    slow = await pg_client.post(
        "/api/v1/lookup/cached",
        headers=headers,
        json={"text": "prado", "profile_id": profile_id},
    )
    assert fast.status_code == 404
    assert slow.status_code == 401
    assert slow.json()["detail"]["code"] == "user_not_found"


async def test_cached_lookup_without_token_is_401(pg_client):
    response = await pg_client.post(
        "/api/v1/lookup/cached",
        json={"text": "prado", "profile_id": str(uuid4())},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"


async def test_lookup_cached_fast_miss_and_foreign_profile(pg):
    async with pg() as session:
        owner = await create_user(session)
        other = await create_user(session)
        profile = await create_profile(session, owner, "pl", "es")
        await session.commit()
        owner_id = owner.id
        other_id = other.id
        profile_id = profile.id
        service = LexicalService(session)
        assert await service.lookup_cached_fast(owner_id, profile_id, "nikt") is None
        with pytest.raises(ValueError, match="Profile not found"):
            await service.lookup_cached_fast(other_id, profile_id, "nikt")

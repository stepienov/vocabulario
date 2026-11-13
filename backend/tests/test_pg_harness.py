import asyncio

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.db.base import Base
from app.db import session as db_session
from app.models import LearningCard, LookupQueryCache, SrsState
from tests.pg_factories import auth_headers, create_card, create_profile, create_user

pytestmark = pytest.mark.pg


async def test_inserted_card_is_visible_in_the_same_test(pg):
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        card = await create_card(session, profile, "prado", "noun")
        await session.commit()
        found = await session.get(LearningCard, card.id)
        state = (
            await session.execute(select(SrsState).where(SrsState.card_id == card.id))
        ).scalar_one()
    assert found is not None
    assert found.lemma_l2 == "prado"
    assert state.scope == "main"
    assert state.status == "new"


async def test_truncate_removes_the_card_before_the_next_test(pg):
    """Samodzielny: wstawia wiersz, robi TRUNCATE jak fixture, sprawdza pustkę."""
    async with pg() as session:
        user = await create_user(session)
        profile = await create_profile(session, user, "pl", "es")
        card = await create_card(session, profile, "prado-trunc", "noun")
        await session.commit()
        card_id = card.id
        assert await session.get(LearningCard, card_id) is not None

    names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with db_session.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))

    async with pg() as session:
        found = await session.get(LearningCard, card_id)
        count = await session.scalar(select(func.count()).select_from(LearningCard))
    assert found is None
    assert count == 0


async def test_me_with_auth_headers(pg, pg_client):
    async with pg() as session:
        user = await create_user(session, email="pg-me@test.com")
        await session.commit()
        headers = auth_headers(user)
    response = await pg_client.get("/api/v1/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "pg-me@test.com"


async def test_concurrent_insert_on_conflict_keeps_one_row(pg):
    values = {
        "lang_pair": "pl>es",
        "input_norm": "casa",
        "candidates": [],
        "ai_complete": False,
    }
    statement = insert(LookupQueryCache).values(**values).on_conflict_do_nothing(
        index_elements=["lang_pair", "input_norm"]
    )

    async def insert_once() -> None:
        async with pg() as session:
            await session.execute(statement)
            await session.commit()

    await asyncio.gather(insert_once(), insert_once())
    async with pg() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(LookupQueryCache)
            .where(LookupQueryCache.input_norm == "casa")
        )
    assert count == 1

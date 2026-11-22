"""Idempotency of offline card moves."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import AppliedSyncMove, LearningCard
from tests.pg_factories import auth_headers, create_card, create_list, create_profile, create_user

pytestmark = pytest.mark.pg


async def test_sync_push_move_idempotent(pg, pg_client):
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        card = await create_card(db, profile, "casa", "noun", status="ready", content={"k": 1})
        target = await create_list(db, profile, "Target")
        other = await create_list(db, profile, "Other")
        await db.commit()
        headers = await auth_headers(db, user)

    move = {
        "client_id": str(uuid4()),
        "card_id": str(card.id),
        "target_list_id": str(target.id),
        "moved_at": "2026-01-02T00:00:00Z",
    }
    first = await pg_client.post("/api/v1/sync/push", json={"moves": [move]}, headers=headers)
    repeat = await pg_client.post("/api/v1/sync/push", json={"moves": [move]}, headers=headers)
    changed = await pg_client.post(
        "/api/v1/sync/push",
        json={"moves": [{**move, "target_list_id": str(other.id)}]},
        headers=headers,
    )
    assert first.status_code == repeat.status_code == changed.status_code == 200
    assert first.json()["move_results"][0]["outcome"] == "applied"
    assert repeat.json()["move_results"][0]["outcome"] == "duplicate"
    assert changed.json()["move_results"][0]["outcome"] == "conflict"
    assert changed.json()["move_results"][0]["reason"] == "operation_id_conflict"

    async with pg() as db:
        saved = await db.get(LearningCard, card.id)
        count = await db.scalar(
            select(func.count()).select_from(AppliedSyncMove).where(
                AppliedSyncMove.client_id == move["client_id"]
            )
        )
    assert saved.deck_id == target.id
    assert count == 1

"""Pull z kursorem snapshotu, ACK push, undo i receipts list (E-001/F-003/T-003)."""

import asyncio
import base64
import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text

from app.core.security import now_utc
from app.models import LearningCard, ReviewLog, SrsState, WordList
from app.services.sync_pull import purge_sync_tombstones
from tests.pg_factories import auth_headers, create_card, create_list, create_profile, create_user

pytestmark = pytest.mark.pg


async def _setup(pg):
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        card = await create_card(db, profile, "casa", "noun", status="ready", content={"k": 1})
        await db.commit()
        return user, profile, card, await auth_headers(db, user)


async def _pull(client, headers, profile, cursor=None):
    return await client.post(
        "/api/v1/sync/pull", json={"profile_id": str(profile.id), "cursor": cursor}, headers=headers
    )


def _review(card_id, client_id=None, grade="good", at="2026-01-01T10:00:00Z"):
    return {
        "client_id": str(client_id or uuid4()), "card_id": str(card_id), "grade": grade,
        "mode": "flip", "direction": "l2_l1", "correct": True, "reviewed_at": at,
    }


async def test_full_pull_then_empty_delta_and_srs_only_change(pg, pg_client):
    _, profile, card, headers = await _setup(pg)
    first = (await _pull(pg_client, headers, profile)).json()
    assert [c["id"] for c in first["cards"]] == [str(card.id)]
    assert datetime.fromisoformat(first["cards"][0]["created_at"]) == card.created_at
    assert first["cursor"]

    again = (await _pull(pg_client, headers, profile, first["cursor"])).json()
    assert again["cards"] == [] and again["deleted_card_ids"] == []

    async with pg() as db:
        state = (await db.execute(select(SrsState).where(SrsState.card_id == card.id))).scalar_one()
        state.interval_days = 9
        await db.commit()
    delta = (await _pull(pg_client, headers, profile, again["cursor"])).json()
    assert [c["id"] for c in delta["cards"]] == [str(card.id)]
    assert delta["cards"][0]["srs"]["interval_days"] == 9
    assert delta["cards"][0]["created_at"] == first["cards"][0]["created_at"]


async def test_open_transaction_with_older_xid_shows_up_after_commit(pg, pg_client):
    user, profile, _, headers = await _setup(pg)
    slow = pg()
    db = await slow.__aenter__()
    late = await create_card(db, profile, "perro", "noun", status="ready", content={"k": 1})
    first = (await _pull(pg_client, headers, profile)).json()
    assert str(late.id) not in [c["id"] for c in first["cards"]]
    await db.commit()
    await slow.__aexit__(None, None, None)

    delta = (await _pull(pg_client, headers, profile, first["cursor"])).json()
    assert [c["id"] for c in delta["cards"]] == [str(late.id)]


async def test_soft_and_physical_deletes_reach_the_right_profile(pg, pg_client):
    user, profile, card, headers = await _setup(pg)
    async with pg() as db:
        other = await create_profile(db, user, "pl", "en")
        victim = await create_card(db, profile, "gato", "noun", status="ready", content={"k": 1})
        await db.commit()
    first = (await _pull(pg_client, headers, profile)).json()
    async with pg() as db:
        row = await db.get(LearningCard, card.id)
        row.deleted_at = now_utc()
        await db.execute(delete(LearningCard).where(LearningCard.id == victim.id))
        await db.commit()
    delta = (await _pull(pg_client, headers, profile, first["cursor"])).json()
    assert set(delta["deleted_card_ids"]) == {str(card.id), str(victim.id)}
    other_pull = (await _pull(pg_client, headers, other)).json()
    assert other_pull["deleted_card_ids"] == []


async def test_savepoint_rollback_creates_no_phantom_change(pg, pg_client):
    _, profile, card, headers = await _setup(pg)
    first = (await _pull(pg_client, headers, profile)).json()
    async with pg() as db:
        nested = await db.begin_nested()
        await db.execute(text("UPDATE learning_cards SET gloss_primary = 'x' WHERE id = :i"), {"i": card.id})
        await nested.rollback()
        await db.commit()
    assert (await _pull(pg_client, headers, profile, first["cursor"])).json()["cards"] == []


def _forge(first_cursor, **changes):
    data = json.loads(base64.urlsafe_b64decode(first_cursor + "=" * (-len(first_cursor) % 4)))
    data.update(changes)
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


async def test_bad_cursors_get_422_and_unknown_profile_404(pg, pg_client):
    user, profile, _, headers = await _setup(pg)
    cursor = (await _pull(pg_client, headers, profile)).json()["cursor"]
    for bad in (
        "not base64!",
        "A" * 9000,
        _forge(cursor, s="1:2:3,3"),
        _forge(cursor, s="5:2:"),
        _forge(cursor, s="1:2; DROP TABLE users:"),
        _forge(cursor, p=str(uuid4())),
        _forge(cursor, s="1:999999999999:"),
        _forge(cursor, v=2),
    ):
        response = await _pull(pg_client, headers, profile, bad)
        assert response.status_code == 422, bad
        assert response.json()["detail"]["code"] == "invalid_sync_cursor"
    assert (await _pull(pg_client, headers, type("P", (), {"id": uuid4()}))).status_code == 404


async def test_other_epoch_and_purged_tombstone_horizon_expire_cursor(pg, pg_client):
    user, profile, card, headers = await _setup(pg)
    first = (await _pull(pg_client, headers, profile)).json()
    async with pg() as db:
        await db.execute(text("UPDATE sync_epoch SET epoch = gen_random_uuid()"))
        await db.commit()
    expired = await _pull(pg_client, headers, profile, first["cursor"])
    assert (expired.status_code, expired.json()["detail"]["code"]) == (410, "sync_cursor_expired")

    fresh = (await _pull(pg_client, headers, profile)).json()
    async with pg() as db:
        victim = await create_card(db, profile, "gato", "noun", status="ready", content={"k": 1})
        await db.commit()
        await db.execute(delete(LearningCard).where(LearningCard.id == victim.id))
        await db.commit()
    assert (await _pull(pg_client, headers, profile, fresh["cursor"])).status_code == 200
    assert await purge_sync_tombstones(now=now_utc() + timedelta(days=31)) == 1
    gone = await _pull(pg_client, headers, profile, fresh["cursor"])
    assert (gone.status_code, gone.json()["detail"]["code"]) == (410, "sync_cursor_expired")
    assert (await _pull(pg_client, headers, profile)).status_code == 200


async def test_push_acks_every_operation_and_retry_is_duplicate(pg, pg_client):
    user, profile, card, headers = await _setup(pg)
    missing = uuid4()
    one, two = _review(card.id), _review(missing)
    body = {"reviews": [one, two]}
    first = (await pg_client.post("/api/v1/sync/push", json=body, headers=headers)).json()
    by_id = {r["client_id"]: r for r in first["review_results"]}
    assert by_id[one["client_id"]]["outcome"] == "applied"
    assert (by_id[two["client_id"]]["outcome"], by_id[two["client_id"]]["reason"]) == (
        "not_found", "card_unavailable",
    )
    retry = (await pg_client.post("/api/v1/sync/push", json={"reviews": [one]}, headers=headers)).json()
    assert retry["review_results"][0]["outcome"] == "duplicate"
    changed = dict(one, grade="again")
    clash = (await pg_client.post("/api/v1/sync/push", json={"reviews": [changed]}, headers=headers)).json()
    assert (clash["review_results"][0]["outcome"], clash["review_results"][0]["reason"]) == (
        "conflict", "operation_id_conflict",
    )
    async with pg() as db:
        logs = (await db.execute(select(ReviewLog).where(ReviewLog.card_id == card.id))).scalars().all()
        assert len(logs) == 1


async def test_concurrent_identical_pushes_have_one_effect(pg, pg_client):
    _, _, card, headers = await _setup(pg)
    body = {"reviews": [_review(card.id)]}
    responses = await asyncio.gather(
        *[pg_client.post("/api/v1/sync/push", json=body, headers=headers) for _ in range(4)]
    )
    assert {r.status_code for r in responses} == {200}
    outcomes = sorted(r.json()["review_results"][0]["outcome"] for r in responses)
    assert outcomes == ["applied", "duplicate", "duplicate", "duplicate"]


async def test_move_outcomes(pg, pg_client):
    user, profile, card, headers = await _setup(pg)
    async with pg() as db:
        target = await create_list(db, profile, "Viaje")
        dead = await create_list(db, profile, "Viejo")
        dead.deleted_at = now_utc()
        await db.commit()

    def move(list_id, at, card_id=card.id):
        return {"client_id": str(uuid4()), "card_id": str(card_id), "moved_at": at,
                "target_list_id": str(list_id)}

    ok, stale = move(target.id, "2026-01-02T00:00:00Z"), move(target.id, "2026-01-01T00:00:00Z")
    gone, ghost = move(dead.id, "2026-01-03T00:00:00Z"), move(target.id, "2026-01-03T00:00:00Z", uuid4())
    await pg_client.post("/api/v1/sync/push", json={"moves": [ok]}, headers=headers)
    result = (await pg_client.post(
        "/api/v1/sync/push", json={"moves": [stale, gone, ghost]}, headers=headers
    )).json()
    by_id = {r["client_id"]: r for r in result["move_results"]}
    assert by_id[stale["client_id"]]["outcome"] == "superseded"
    assert by_id[gone["client_id"]]["reason"] == "target_unavailable"
    assert by_id[ghost["client_id"]]["reason"] == "card_unavailable"


async def test_undo_retry_never_overwrites_and_delayed_review_is_superseded(pg, pg_client):
    _, _, card, headers = await _setup(pg)
    first = _review(card.id)
    await pg_client.post("/api/v1/sync/push", json={"reviews": [first]}, headers=headers)
    async with pg() as db:
        state = (await db.execute(select(SrsState).where(SrsState.card_id == card.id))).scalar_one()
        before = {"card_id": str(card.id), "status": "new", "interval_days": 0}
        revision = state.review_revision
    undo = {"client_id": first["client_id"], "previous_srs": before}
    assert (await pg_client.post("/api/v1/srs/undo", json=undo, headers=headers)).status_code == 200

    nxt = _review(card.id, at="2026-01-02T10:00:00Z")
    await pg_client.post("/api/v1/sync/push", json={"reviews": [nxt]}, headers=headers)
    retried = await pg_client.post("/api/v1/srs/undo", json=undo, headers=headers)
    assert retried.status_code == 200
    assert retried.json()["srs"]["status"] != "new"

    delayed = _review(card.id, client_id=uuid4())
    cancel = {"client_id": delayed["client_id"], "previous_srs": before}
    assert (await pg_client.post("/api/v1/srs/undo", json=cancel, headers=headers)).status_code == 200
    ack = (await pg_client.post("/api/v1/sync/push", json={"reviews": [delayed]}, headers=headers)).json()
    assert (ack["review_results"][0]["outcome"], ack["review_results"][0]["reason"]) == (
        "superseded", "undo_already_applied",
    )
    assert revision > 0


async def test_undo_after_newer_review_is_conflict(pg, pg_client):
    _, _, card, headers = await _setup(pg)
    first, second = _review(card.id), _review(card.id, at="2026-01-02T10:00:00Z")
    await pg_client.post("/api/v1/sync/push", json={"reviews": [first, second]}, headers=headers)
    undo = {"client_id": first["client_id"], "previous_srs": {"card_id": str(card.id), "status": "new"}}
    response = await pg_client.post("/api/v1/srs/undo", json=undo, headers=headers)
    assert (response.status_code, response.json()["detail"]["code"]) == (409, "undo_conflict")
    async with pg() as db:
        state = (await db.execute(select(SrsState).where(SrsState.card_id == card.id))).scalar_one()
        assert state.status != "new"


async def test_list_create_receipt_is_idempotent_and_never_resurrects(pg, pg_client):
    user, profile, _, headers = await _setup(pg)
    op = str(uuid4())
    body = {"name": "Viaje", "profile_id": str(profile.id), "client_op_id": op}
    one = await pg_client.post("/api/v1/lists", json=body, headers=headers)
    two = await pg_client.post("/api/v1/lists", json=body, headers=headers)
    assert (one.status_code, two.status_code) == (201, 201)
    assert one.json()["id"] == two.json()["id"]
    other = await pg_client.post("/api/v1/lists", json=dict(body, name="Otra"), headers=headers)
    assert (other.status_code, other.json()["detail"]["code"]) == (409, "operation_id_conflict")

    await pg_client.delete(f"/api/v1/lists/{one.json()['id']}?profile_id={profile.id}", headers=headers)
    gone = await pg_client.post("/api/v1/lists", json=body, headers=headers)
    assert (gone.status_code, gone.json()["detail"]["code"]) == (410, "list_already_deleted")
    async with pg() as db:
        live = (await db.execute(select(WordList).where(WordList.name == "Viaje", WordList.deleted_at.is_(None)))).all()
        assert live == []

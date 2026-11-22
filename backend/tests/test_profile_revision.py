"""Rewizje profilu i idempotentna edycja (E-001/F-003/T-004)."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import LanguageProfile
from tests.pg_factories import auth_headers, create_profile, create_user

pytestmark = pytest.mark.pg


async def _setup(pg):
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        await db.commit()
        return user, profile, await auth_headers(db, user)


async def _put(client, headers, profile, **body):
    return await client.put(f"/api/v1/profiles/{profile.id}", json=body, headers=headers)


async def test_new_contract_bumps_revision_and_repeats_idempotently(pg, pg_client):
    _, profile, headers = await _setup(pg)
    op = str(uuid4())
    first = await _put(pg_client, headers, profile, cefr_level="B1", expected_revision=1, client_op_id=op)
    assert first.status_code == 200
    assert first.json()["revision"] == 2 and first.json()["cefr_level"] == "B1"

    again = await _put(pg_client, headers, profile, cefr_level="B1", expected_revision=1, client_op_id=op)
    assert again.status_code == 200 and again.json()["revision"] == 2

    different = await _put(pg_client, headers, profile, cefr_level="C1", expected_revision=1, client_op_id=op)
    assert different.status_code == 409
    assert different.json()["detail"]["code"] == "operation_id_conflict"


async def test_stale_revision_conflicts_without_writing(pg, pg_client):
    _, profile, headers = await _setup(pg)
    ok = await _put(pg_client, headers, profile, cefr_level="B1", expected_revision=1, client_op_id=str(uuid4()))
    assert ok.status_code == 200
    stale = await _put(pg_client, headers, profile, cefr_level="C2", expected_revision=1, client_op_id=str(uuid4()))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "profile_conflict"
    async with pg() as db:
        row = (await db.execute(select(LanguageProfile).where(LanguageProfile.id == profile.id))).scalar_one()
        assert row.cefr_level == "B1" and row.revision == 2


async def test_retry_after_other_device_changed_the_profile_is_a_conflict(pg, pg_client):
    _, profile, headers = await _setup(pg)
    op = str(uuid4())
    await _put(pg_client, headers, profile, cefr_level="B1", expected_revision=1, client_op_id=op)
    await _put(pg_client, headers, profile, cefr_level="B2", expected_revision=2, client_op_id=str(uuid4()))
    retry = await _put(pg_client, headers, profile, cefr_level="B1", expected_revision=1, client_op_id=op)
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "profile_conflict"


async def test_legacy_update_bumps_revision_and_clears_marker(pg, pg_client):
    _, profile, headers = await _setup(pg)
    op = str(uuid4())
    await _put(pg_client, headers, profile, cefr_level="B1", expected_revision=1, client_op_id=op)
    legacy = await _put(pg_client, headers, profile, cefr_level="B2")
    assert legacy.status_code == 200 and legacy.json()["revision"] == 3
    retry = await _put(pg_client, headers, profile, cefr_level="B1", expected_revision=1, client_op_id=op)
    assert retry.status_code == 409


async def test_legacy_update_refused_after_protocol_switch(pg, pg_client, monkeypatch):
    from app.core.config import get_settings

    _, profile, headers = await _setup(pg)
    monkeypatch.setattr(get_settings(), "profile_update_requires_revision", True)
    refused = await _put(pg_client, headers, profile, cefr_level="B1")
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "expected_revision_required"


async def test_activation_does_not_touch_revision_and_other_owner_is_404(pg, pg_client):
    user, profile, headers = await _setup(pg)
    activated = await pg_client.put(f"/api/v1/profiles/{profile.id}/activate", headers=headers)
    assert activated.status_code == 200 and activated.json()["revision"] == 1
    async with pg() as db:
        stranger = await create_user(db)
        other_headers = await auth_headers(db, stranger)
        await db.commit()
    foreign = await _put(pg_client, other_headers, profile, cefr_level="B1", expected_revision=1)
    assert foreign.status_code == 404
    assert foreign.json()["detail"]["code"] == "profile_not_found"

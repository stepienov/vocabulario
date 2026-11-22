"""Content reports: idempotency, ownership, retention, limits (E-001/F-007/T-002)."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.security import now_utc
from app.models import ContentReport, ContentReportReceipt, LearningCard
from app.services import content_reports
from tests.pg_factories import auth_headers, create_card, create_profile, create_user

pytestmark = pytest.mark.pg

URL = "/api/v1/content-reports"


def _body(profile_id, **over) -> dict:
    return {
        "client_report_id": str(uuid4()),
        "profile_id": str(profile_id),
        "target_kind": "lookup",
        "field": "meaning",
        "reason": "incorrect",
        "excerpt": "gato = dog",
        **over,
    }


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def _setup(pg):
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        card = await create_card(db, profile, "gato", "noun", status="learnable")
        headers = await auth_headers(db, user)
        await db.commit()
        return user, profile, card, headers


async def test_report_is_idempotent_and_conflicts_on_other_content(pg, pg_client):
    _, profile, _, headers = await _setup(pg)
    body = _body(profile.id)
    first = await pg_client.post(URL, json=body, headers=headers)
    assert first.status_code == 201, first.text
    again = await pg_client.post(URL, json=body, headers=headers)
    assert again.status_code == 200
    assert again.json()["report_id"] == first.json()["report_id"]
    changed = await pg_client.post(URL, json={**body, "excerpt": "other"}, headers=headers)
    assert (changed.status_code, _code(changed)) == (409, "report_request_conflict")
    async with pg() as db:
        assert len((await db.execute(select(ContentReport))).scalars().all()) == 1


async def test_report_does_not_touch_card_state_and_validates_without_echo(pg, pg_client):
    _, profile, card, headers = await _setup(pg)
    body = _body(profile.id, target_kind="card", target_id=str(card.id), field="example")
    assert (await pg_client.post(URL, json=body, headers=headers)).status_code == 201
    async with pg() as db:
        stored = (await db.execute(select(LearningCard).where(LearningCard.id == card.id))).scalar_one()
        assert stored.enrichment_status == "learnable"
    secret = "x" * 4001
    bad = await pg_client.post(URL, json=_body(profile.id, excerpt=secret), headers=headers)
    assert bad.status_code == 422
    assert secret not in bad.text


async def test_foreign_or_missing_targets_are_404_and_owner_only_view(pg, pg_client):
    _, profile, card, headers = await _setup(pg)
    _, other_profile, other_card, other_headers = await _setup(pg)
    foreign_profile = await pg_client.post(URL, json=_body(other_profile.id), headers=headers)
    assert foreign_profile.status_code == 404
    foreign_card = await pg_client.post(
        URL, json=_body(profile.id, target_kind="card", target_id=str(other_card.id)), headers=headers
    )
    assert foreign_card.status_code == 404
    created = await pg_client.post(URL, json=_body(profile.id), headers=headers)
    report_id = created.json()["report_id"]
    assert (await pg_client.get(f"{URL}/{report_id}", headers=headers)).status_code == 200
    assert (await pg_client.get(f"{URL}/{report_id}", headers=other_headers)).status_code == 404


async def test_retry_survives_card_deletion_and_resolved_report_expires_to_receipt(pg, pg_client):
    _, profile, card, headers = await _setup(pg)
    body = _body(profile.id, target_kind="card", target_id=str(card.id))
    created = await pg_client.post(URL, json=body, headers=headers)
    report_id = created.json()["report_id"]
    async with pg() as db:
        stored = (await db.execute(select(LearningCard).where(LearningCard.id == card.id))).scalar_one()
        stored.deleted_at = now_utc()
        await db.commit()
    assert (await pg_client.post(URL, json=body, headers=headers)).status_code == 200

    async with pg() as db:
        assert await content_reports.take_report(db, UUID(report_id), "op")
        assert await content_reports.resolve_report(db, UUID(report_id), "op", "fixed", "internal")
        await db.commit()
    shown = (await pg_client.get(f"{URL}/{report_id}", headers=headers)).json()
    assert shown["status"] == "resolved"
    assert "internal" not in str(shown)

    assert await content_reports.purge_resolved_reports(now=now_utc() + timedelta(days=31)) == 1
    async with pg() as db:
        assert (await db.execute(select(ContentReport))).scalars().all() == []
        receipt = (await db.execute(select(ContentReportReceipt))).scalar_one()
        assert receipt.expired_at is not None
    again = await pg_client.post(URL, json=body, headers=headers)
    assert again.status_code == 200
    assert again.json()["status"] == "expired"
    assert again.json()["report_id"] == report_id
    gone = await pg_client.post(URL, json={**body, "excerpt": "different"}, headers=headers)
    assert gone.status_code == 409


async def test_report_rate_limit_is_per_user(pg, pg_client):
    _, profile, _, headers = await _setup(pg)
    codes = [
        (await pg_client.post(URL, json=_body(profile.id), headers=headers)).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [201] * 10
    assert codes[10] == 429


async def test_operator_panel_renders_text_as_text_and_moves_report(pg, pg_client, monkeypatch):
    from app.admin_ui.auth import COOKIE_NAME, _encode
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cret")
    _, profile, _, headers = await _setup(pg)
    payload = "<script>alert(1)</script>"
    created = await pg_client.post(URL, json=_body(profile.id, excerpt=payload), headers=headers)
    report_id = created.json()["report_id"]
    pg_client.cookies.set(COOKIE_NAME, _encode("admin"), path="/admin")
    page = await pg_client.get("/admin/reports")
    assert page.status_code == 200
    assert payload not in page.text and "&lt;script&gt;" in page.text
    taken = await pg_client.post(f"/admin/reports/{report_id}/take", follow_redirects=False)
    assert taken.status_code == 303
    resolved = await pg_client.post(
        f"/admin/reports/{report_id}/resolve", data={"code": "fixed"}, follow_redirects=False
    )
    assert resolved.status_code == 303
    shown = await pg_client.get(f"{URL}/{report_id}", headers=headers)
    assert shown.json()["status"] == "resolved"


async def test_operator_ordering_puts_privacy_first(pg):
    _, profile, _, _ = await _setup(pg)
    async with pg() as db:
        user = await create_user(db)
        for reason, age in (("incorrect", 3), ("privacy", 1)):
            db.add(
                ContentReport(
                    user_id=user.id,
                    client_report_id=uuid4(),
                    fingerprint="f" * 64,
                    profile_id=profile.id,
                    target_kind="lookup",
                    field="other",
                    reason=reason,
                    excerpt="x",
                    received_at=now_utc() - timedelta(days=age),
                )
            )
        await db.commit()
        rows, total = await content_reports.list_reports(db, status=None, page=1)
    assert total == 2
    assert [r.reason for r in rows] == ["privacy", "incorrect"]
    start = now_utc().replace(hour=9) - timedelta(days=now_utc().weekday())  # Monday
    assert content_reports.working_days_between(start, start + timedelta(days=7)) == 5

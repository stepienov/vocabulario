"""Terms acceptance, manifest and the gate for old accounts (E-001/F-007/T-003)."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import User
from app.services import legal_docs
from tests.google_fakes import google_login, install_fake_google
from tests.pg_factories import auth_headers, create_user

pytestmark = pytest.mark.pg

PASSWORD = "correct horse battery"


def _legal(**over) -> dict:
    return {
        "terms_version": legal_docs.TERMS_VERSION,
        "locale": "pl",
        "adult_confirmed": True,
        **over,
    }


def _register_body(**extra) -> dict:
    return {"email": f"legal-{uuid4()}@test.com", "password": PASSWORD, **extra}


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def test_manifest_is_public_cached_and_honest_about_locale(pg_client):
    first = await pg_client.get("/api/v1/legal/current", params={"locale": "es"})
    body = first.json()
    assert first.status_code == 200
    assert body["locale"] == "es"
    assert {d["kind"] for d in body["documents"]} == {"terms", "privacy"}
    assert all(len(d["sha256"]) == 64 for d in body["documents"])
    again = await pg_client.get(
        "/api/v1/legal/current",
        params={"locale": "es"},
        headers={"If-None-Match": first.headers["etag"]},
    )
    assert again.status_code == 304
    other = await pg_client.get("/api/v1/legal/current", params={"locale": "ja"})
    assert other.json()["locale"] == "en"
    assert other.json()["requested_locale"] == "ja"


async def test_manifest_carries_support_address_and_revalidates_on_change(pg_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "support_email", "")
    empty = await pg_client.get("/api/v1/legal/current")
    assert empty.json()["support_email"] is None
    monkeypatch.setattr(get_settings(), "support_email", "help@example.com")
    filled = await pg_client.get("/api/v1/legal/current")
    assert filled.json()["support_email"] == "help@example.com"
    assert filled.headers["etag"] != empty.headers["etag"]


async def test_register_records_proof_and_me_reports_it(pg, pg_client):
    response = await pg_client.post(
        "/api/v1/auth/register", json=_register_body(legal_acceptance=_legal())
    )
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    status = (await pg_client.get("/api/v1/me", headers=headers)).json()["legal_status"]
    assert status["accepted_terms_version"] == legal_docs.TERMS_VERSION
    assert status["adult_confirmed"] is True
    async with pg() as db:
        user = (await db.execute(select(User).where(User.id == response.json()["user_id"]))).scalar_one()
        assert (user.terms_locale, user.adult_statement_version) == (
            "pl",
            legal_docs.ADULT_STATEMENT_VERSION,
        )
        assert user.terms_accepted_at is not None


async def test_register_rejects_stale_version_and_unconfirmed_age_without_creating_user(
    pg, pg_client
):
    stale = _register_body(legal_acceptance=_legal(terms_version="1999-01-01"))
    refused = await pg_client.post("/api/v1/auth/register", json=stale)
    assert (refused.status_code, _code(refused)) == (409, "legal_version_changed")
    assert refused.json()["detail"]["legal"]["terms_version"] == legal_docs.TERMS_VERSION
    minor = _register_body(legal_acceptance=_legal(adult_confirmed=False))
    refused = await pg_client.post("/api/v1/auth/register", json=minor)
    assert (refused.status_code, _code(refused)) == (422, "adult_confirmation_required")
    async with pg() as db:
        found = await db.execute(
            select(User.id).where(User.email.in_([stale["email"], minor["email"]]))
        )
        assert found.first() is None


async def test_enforced_registration_needs_acceptance(pg_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "legal_acceptance_enforced", True)
    missing = await pg_client.post("/api/v1/auth/register", json=_register_body())
    assert (missing.status_code, _code(missing)) == (422, "legal_acceptance_missing")
    ok = await pg_client.post(
        "/api/v1/auth/register", json=_register_body(legal_acceptance=_legal())
    )
    assert ok.status_code == 200


async def test_acceptance_endpoint_is_idempotent_and_keeps_first_time(pg, pg_client):
    async with pg() as db:
        user = await create_user(db)
        headers = await auth_headers(db, user)
    first = await pg_client.post("/api/v1/me/legal-acceptance", json=_legal(), headers=headers)
    assert first.status_code == 200
    assert first.json()["acceptance_required"] is False
    async with pg() as db:
        stamp = (await db.execute(select(User.terms_accepted_at).where(User.id == user.id))).scalar_one()
    again = await pg_client.post(
        "/api/v1/me/legal-acceptance", json=_legal(locale="es"), headers=headers
    )
    assert again.status_code == 200
    async with pg() as db:
        row = (await db.execute(select(User).where(User.id == user.id))).scalar_one()
        assert (row.terms_accepted_at, row.terms_locale) == (stamp, "pl")
    stale = await pg_client.post(
        "/api/v1/me/legal-acceptance", json=_legal(terms_version="old"), headers=headers
    )
    assert (stale.status_code, _code(stale)) == (409, "legal_version_changed")


async def test_old_account_is_gated_only_when_enforced(pg, pg_client, monkeypatch):
    async with pg() as db:
        user = await create_user(db)
        headers = await auth_headers(db, user)
    assert (await pg_client.get("/api/v1/profiles", headers=headers)).status_code == 200
    monkeypatch.setattr(get_settings(), "legal_acceptance_enforced", True)
    blocked = await pg_client.get("/api/v1/profiles", headers=headers)
    assert (blocked.status_code, _code(blocked)) == (403, "terms_acceptance_required")
    me = await pg_client.get("/api/v1/me", headers=headers)
    assert me.json()["legal_status"]["acceptance_required"] is True
    accepted = await pg_client.post("/api/v1/me/legal-acceptance", json=_legal(), headers=headers)
    assert accepted.status_code == 200
    assert (await pg_client.get("/api/v1/profiles", headers=headers)).status_code == 200


async def test_new_google_account_needs_acceptance_but_existing_login_does_not(
    pg_client, monkeypatch
):
    install_fake_google(monkeypatch)
    monkeypatch.setattr(get_settings(), "legal_acceptance_enforced", True)
    sub = str(uuid4())
    email = f"g-{uuid4()}@gmail.com"
    kwargs = {"email": email, "email_verified": True}
    refused = await google_login(pg_client, sub, **kwargs)
    assert (refused.status_code, _code(refused)) == (422, "legal_acceptance_missing")
    created = await google_login(pg_client, sub, legal_acceptance=_legal(), **kwargs)
    assert created.status_code == 200, created.text
    again = await google_login(pg_client, sub, **kwargs)
    assert again.status_code == 200

"""E-001/F-005/T-001: Google sign-in with a server nonce, safe linking and Google proofs."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import GoogleChallenge, User
from app.services.auth_cleanup import purge_auth_records
from tests.google_fakes import (
    google_login,
    google_token,
    install_fake_google,
    login_challenge,
)
from tests.test_account_recovery import PASSWORD, _bearer, _code, _outbox, _register, _user
from tests.test_email_change import _google_only, _proof, _verified

pytestmark = pytest.mark.pg

AUTH = "/api/v1/auth"


@pytest.fixture(autouse=True)
def _google(monkeypatch):
    install_fake_google(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "account_deletion_enabled", True)
    monkeypatch.setattr(settings, "account_erasure_key", "k" * 48)
    monkeypatch.setattr(settings, "account_erasure_key_version", 1)


def _email(prefix: str = "g", domain: str = "gmail.com") -> str:
    return f"{prefix}-{uuid4().hex[:10]}@{domain}"


async def _challenge(client, path: str, headers: dict, **body) -> dict:
    response = await client.post(f"{AUTH}{path}", json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


async def _link(client, tokens, proof: str, sub: str, email: str | None, **claims):
    headers = _bearer(tokens)
    challenge = await _challenge(
        client, "/google/link/challenge", headers, recent_auth_token=proof
    )
    return await client.post(
        f"{AUTH}/google/link",
        json={
            "challenge_id": challenge["challenge_id"],
            "id_token": google_token(challenge["nonce"], sub, email, **claims),
            "recent_auth_token": proof,
        },
        headers=headers,
    )


async def test_login_challenge_is_one_use_bound_to_its_nonce_and_expires(pg, pg_client):
    sub, email = str(uuid4()), _email()
    challenge = await login_challenge(pg_client)
    body = {"challenge_id": challenge["challenge_id"]}

    wrong = await pg_client.post(
        f"{AUTH}/google",
        json={**body, "id_token": google_token("x" * 43, sub, email, email_verified=True)},
    )
    assert (wrong.status_code, _code(wrong)) == (401, "invalid_google_token")

    token = google_token(challenge["nonce"], sub, email, email_verified=True)
    ok = await pg_client.post(f"{AUTH}/google", json={**body, "id_token": token})
    assert ok.status_code == 200, ok.text
    again = await pg_client.post(f"{AUTH}/google", json={**body, "id_token": token})
    assert (again.status_code, _code(again)) == (409, "auth_challenge_used")

    stale = await login_challenge(pg_client)
    async with pg() as db:
        row = await db.get(GoogleChallenge, UUID(stale["challenge_id"]))
        row.expires_at = now_utc() - timedelta(seconds=1)
        await db.commit()
    late = await pg_client.post(
        f"{AUTH}/google",
        json={
            "challenge_id": stale["challenge_id"],
            "id_token": google_token(stale["nonce"], sub, email),
        },
    )
    assert (late.status_code, _code(late)) == (410, "auth_challenge_expired")
    unknown = await pg_client.post(
        f"{AUTH}/google", json={"challenge_id": str(uuid4()), "id_token": token}
    )
    assert (unknown.status_code, _code(unknown)) == (400, "auth_challenge_invalid")


async def test_me_shows_google_snapshot_without_the_subject(pg, pg_client):
    sub, email = str(uuid4()), _email()
    tokens = (await google_login(pg_client, sub, email, email_verified=True)).json()
    me = (await pg_client.get("/api/v1/me", headers=_bearer(tokens))).json()
    assert me["login_methods"] == ["google"] and me["google_email"] == email
    assert me["google_email_observed_at"] and sub not in str(me)


async def test_parallel_first_logins_make_one_account(pg, pg_client):
    sub, email = str(uuid4()), _email()
    results = await asyncio.gather(
        *(google_login(pg_client, sub, email, email_verified=True) for _ in range(4))
    )
    assert [r.status_code for r in results] == [200] * 4
    assert len({r.json()["user_id"] for r in results}) == 1
    async with pg() as db:
        count = await db.scalar(select(func.count()).select_from(User).where(User.google_id == sub))
    assert count == 1


async def test_parallel_new_subjects_with_one_address_conflict(pg, pg_client):
    email = _email()
    results = await asyncio.gather(
        *(google_login(pg_client, str(uuid4()), email, email_verified=True) for _ in range(2))
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert {_code(r) for r in results if r.status_code == 409} == {"google_sign_in_conflict"}


async def test_link_adds_method_keeps_address_and_renews_only_this_session(pg, pg_client):
    email, first = await _verified(pg, pg_client)
    second = (
        await pg_client.post(f"{AUTH}/login", json={"email": email, "password": PASSWORD})
    ).json()
    before = await _user(pg, email)
    sub, other_address = str(uuid4()), _email("other", "outlook.com")

    done = await _link(
        pg_client, first, await _proof(pg_client, first, action="link_google"), sub, other_address,
        email_verified=True,
    )
    assert done.status_code == 200, done.text
    fresh = done.json()

    stored = await _user(pg, email)
    assert (stored.google_id, stored.email, stored.email_revision) == (
        sub,
        email,
        before.email_revision,
    )
    assert stored.google_email == other_address
    assert stored.credentials_revision == before.credentials_revision + 1
    me = (await pg_client.get("/api/v1/me", headers=_bearer(fresh))).json()
    assert me["login_methods"] == ["password", "google"]
    for stale in (first, second):
        gone = await pg_client.get("/api/v1/me", headers=_bearer(stale))
        assert gone.status_code == 401
    [notice] = await _outbox(pg, "google_linked")
    assert notice.user_id == stored.id

    again = await _proof(pg_client, fresh, action="link_google")
    refused = await pg_client.post(
        f"{AUTH}/google/link/challenge",
        json={"recent_auth_token": again},
        headers=_bearer(fresh),
    )
    assert (refused.status_code, _code(refused)) == (409, "google_method_already_present")


async def test_link_refuses_a_subject_that_belongs_to_another_account(pg, pg_client):
    taken = str(uuid4())
    await google_login(pg_client, taken, _email(), email_verified=True)
    _, tokens = await _verified(pg, pg_client)
    blocked = await _link(
        pg_client, tokens, await _proof(pg_client, tokens, action="link_google"), taken, _email()
    )
    assert (blocked.status_code, _code(blocked)) == (409, "google_link_unavailable")
    me = (await pg_client.get("/api/v1/me", headers=_bearer(tokens))).json()
    assert me["login_methods"] == ["password"]


async def test_link_needs_a_proven_app_address_or_matching_google_address(pg, pg_client):
    unverified_email = _email("unv")
    tokens = await _register(pg_client, unverified_email)
    proof = await _proof(pg_client, tokens, action="link_google")
    blocked = await _link(pg_client, tokens, proof, str(uuid4()), _email("o", "outlook.com"))
    assert (blocked.status_code, _code(blocked)) == (403, "email_verification_required")
    assert (await _user(pg, unverified_email)).google_id is None

    proof = await _proof(pg_client, tokens, action="link_google")
    ok = await _link(
        pg_client, tokens, proof, str(uuid4()), unverified_email, email_verified=True
    )
    assert ok.status_code == 200, ok.text
    assert (await _user(pg, unverified_email)).email_verified_at is not None


async def test_link_challenge_belongs_to_one_proof_and_one_session(pg, pg_client):
    _, tokens = await _verified(pg, pg_client)
    headers = _bearer(tokens)
    proof = await _proof(pg_client, tokens, action="link_google")
    other_proof = await _proof(pg_client, tokens, action="link_google")
    challenge = await _challenge(
        pg_client, "/google/link/challenge", headers, recent_auth_token=proof
    )
    body = {
        "challenge_id": challenge["challenge_id"],
        "id_token": google_token(challenge["nonce"], str(uuid4()), _email(), email_verified=True),
    }
    swapped = await pg_client.post(
        f"{AUTH}/google/link", json={**body, "recent_auth_token": other_proof}, headers=headers
    )
    assert (swapped.status_code, _code(swapped)) == (400, "auth_challenge_invalid")

    _, stranger = await _verified(pg, pg_client)
    foreign = await pg_client.post(
        f"{AUTH}/google/link", json={**body, "recent_auth_token": proof}, headers=_bearer(stranger)
    )
    assert (foreign.status_code, _code(foreign)) == (400, "auth_challenge_invalid")
    fine = await pg_client.post(
        f"{AUTH}/google/link", json={**body, "recent_auth_token": proof}, headers=headers
    )
    assert fine.status_code == 200, fine.text


async def test_google_proof_for_add_password_needs_the_linked_subject(pg, pg_client):
    user, issued = await _google_only(pg)
    headers = {"Authorization": f"Bearer {issued.access_token}"}
    challenge = await _challenge(
        pg_client, "/recent-auth/google/challenge", headers, action="add_password"
    )
    body = {"challenge_id": challenge["challenge_id"], "action": "add_password"}
    stranger = await pg_client.post(
        f"{AUTH}/recent-auth/google",
        json={**body, "id_token": google_token(challenge["nonce"], str(uuid4()), _email())},
        headers=headers,
    )
    assert (stranger.status_code, _code(stranger)) == (403, "google_account_mismatch")

    proof = await pg_client.post(
        f"{AUTH}/recent-auth/google",
        json={**body, "id_token": google_token(challenge["nonce"], user.google_id, user.email)},
        headers=headers,
    )
    assert proof.status_code == 200, proof.text
    added = await pg_client.post(
        f"{AUTH}/password/add",
        json={
            "new_password": "a much longer new passphrase",
            "recent_auth_token": proof.json()["recent_auth_token"],
        },
        headers=headers,
    )
    assert added.status_code == 200, added.text


async def test_google_proof_rules_for_accounts_with_and_without_google(pg, pg_client):
    _, tokens = await _verified(pg, pg_client)
    none = await pg_client.post(
        f"{AUTH}/recent-auth/google/challenge",
        json={"action": "change_email"},
        headers=_bearer(tokens),
    )
    assert (none.status_code, _code(none)) == (403, "google_not_linked")

    done = await _link(
        pg_client, tokens, await _proof(pg_client, tokens, action="link_google"),
        str(uuid4()), _email(), email_verified=True,
    )
    fresh = done.json()
    has_password = await pg_client.post(
        f"{AUTH}/recent-auth/google/challenge",
        json={"action": "add_password"},
        headers=_bearer(fresh),
    )
    assert (has_password.status_code, _code(has_password)) == (409, "password_already_set")
    wrong_use = await pg_client.post(
        f"{AUTH}/google/link",
        json={
            "challenge_id": str(uuid4()),
            "id_token": "x",
            "recent_auth_token": "y",
        },
        headers=_bearer(fresh),
    )
    assert (wrong_use.status_code, _code(wrong_use)) == (400, "auth_challenge_invalid")


async def test_deletion_proof_by_google_uses_the_subject_and_its_own_action(pg, pg_client):
    user, _ = await _google_only(pg)
    api = "/api/v1/account-deletion"

    async def challenge(action: str) -> dict:
        response = await pg_client.post(f"{api}/google/challenge", json={"action": action})
        assert response.status_code == 200, response.text
        return response.json()

    first = await challenge("request")
    unknown = await pg_client.post(
        f"{api}/proof/google",
        json={
            "challenge_id": first["challenge_id"],
            "action": "request",
            "id_token": google_token(first["nonce"], str(uuid4()), _email()),
        },
    )
    assert (unknown.status_code, _code(unknown)) == (401, "invalid_google_token")

    wrong_action = await pg_client.post(
        f"{api}/proof/google",
        json={
            "challenge_id": first["challenge_id"],
            "action": "cancel",
            "id_token": google_token(first["nonce"], user.google_id, user.email),
        },
    )
    assert (wrong_action.status_code, _code(wrong_action)) == (400, "auth_challenge_invalid")

    proof = await pg_client.post(
        f"{api}/proof/google",
        json={
            "challenge_id": first["challenge_id"],
            "action": "request",
            "id_token": google_token(first["nonce"], user.google_id, user.email),
        },
    )
    assert proof.status_code == 200, proof.text
    assert proof.json()["method"] == "google" and proof.json()["user_id"] == str(user.id)
    used = await pg_client.post(
        f"{api}/proof/google",
        json={
            "challenge_id": first["challenge_id"],
            "action": "request",
            "id_token": google_token(first["nonce"], user.google_id, user.email),
        },
    )
    assert (used.status_code, _code(used)) == (409, "auth_challenge_used")


async def test_deletion_challenge_does_not_sign_in(pg, pg_client):
    user, _ = await _google_only(pg)
    response = await pg_client.post(
        "/api/v1/account-deletion/google/challenge", json={"action": "request"}
    )
    challenge = response.json()
    login = await pg_client.post(
        f"{AUTH}/google",
        json={
            "challenge_id": challenge["challenge_id"],
            "id_token": google_token(challenge["nonce"], user.google_id, user.email),
        },
    )
    assert (login.status_code, _code(login)) == (400, "auth_challenge_invalid")


async def test_cleanup_removes_old_challenges(pg, pg_client):
    challenge = await login_challenge(pg_client)
    counts = await purge_auth_records(now=now_utc() + timedelta(days=3))
    assert counts["google_challenges"] >= 1
    async with pg() as db:
        assert await db.get(GoogleChallenge, UUID(challenge["challenge_id"])) is None

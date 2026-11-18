"""E-001/F-004/T-004 (zmiana adresu e-mail) i T-005 (dodanie hasła do konta Google)."""

import asyncio
import re
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import now_utc
from app.models import AccountEmailChange, AuthSession, RecentAuthProof, User
from app.services import email_change as ec
from app.services.auth_sessions import AccessContext, create_session
from app.services.mail_outbox import _decrypt
from app.services.recent_auth import issue_recent_auth
from tests.test_account_recovery import (
    NEW_PASSWORD,
    PASSWORD,
    _bearer,
    _code,
    _login,
    _outbox,
    _register,
    _user,
)

pytestmark = pytest.mark.pg

_LINK = re.compile(r"/account/change-email\?lang=[A-Za-z-]+#token=([A-Za-z0-9_-]+)")


def _token(row) -> str:
    match = _LINK.search(_decrypt(row).text)
    assert match
    return match.group(1)


async def _verified(pg, client, prefix: str = "chg") -> tuple[str, dict]:
    email = f"{prefix}-{uuid4()}@test.com"
    tokens = await _register(client, email)
    async with pg() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.email_verified_at = now_utc()
        await db.commit()
    return email, tokens


async def _proof(client, tokens, password: str = PASSWORD, action: str = "change_email") -> str:
    response = await client.post(
        "/api/v1/auth/recent-auth/password",
        json={"password": password, "action": action},
        headers=_bearer(tokens),
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["recent_auth_token"]


async def _request(client, tokens, new_email: str, proof: str, request_id=None):
    return await client.post(
        "/api/v1/auth/email-change/request",
        json={
            "new_email": new_email,
            "recent_auth_token": proof,
            "request_id": str(request_id or uuid4()),
        },
        headers=_bearer(tokens),
    )


async def _confirm(client, token: str):
    return await client.post("/api/v1/auth/email-change/confirm", json={"token": token})


async def _current(client, tokens) -> dict | None:
    response = await client.get("/api/v1/auth/email-change", headers=_bearer(tokens))
    assert response.status_code == 200, response.text
    return response.json()["change"]


async def test_change_switches_address_and_ends_every_session(pg, pg_client):
    old, first = await _verified(pg, pg_client)
    second = (await _login(pg_client, old, PASSWORD)).json()
    new = f"new-{uuid4()}@test.com"
    before = await _user(pg, old)

    created = await _request(pg_client, first, f"  {new.upper()} ", await _proof(pg_client, first))
    assert created.status_code == 202, created.text
    body = created.json()
    assert (body["mode"], body["status"], body["new_email"]) == ("change", "pending", new)
    assert body["delivery_status"] == "queued" and body["resend_available_at"]
    assert (await _user(pg, old)).email == old

    [mail] = await _outbox(pg, "change_email")
    assert _decrypt(mail).to == new
    [started] = await _outbox(pg, "email_change_started")
    assert _decrypt(started).to == old and new not in _decrypt(started).text

    done = await _confirm(pg_client, _token(mail))
    assert done.status_code == 200, done.text
    assert done.json() == {"status": "email_changed", "requires_login": True}
    for tokens in (first, second):
        me = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
        assert (me.status_code, _code(me)) == (401, "session_revoked")

    after = await _user(pg, new)
    assert after.id == before.id and after.email_revision == before.email_revision + 1
    assert after.email_verified_at is not None
    assert (await _login(pg_client, old, PASSWORD)).status_code == 401
    relogin = await _login(pg_client, new, PASSWORD)
    assert relogin.status_code == 200
    [notice] = await _outbox(pg, "email_change_done")
    assert _decrypt(notice).to == old
    again = await _confirm(pg_client, _token(mail))
    assert (again.status_code, _code(again)) == (409, "action_token_used")
    state = await _current(pg_client, relogin.json())
    assert state["status"] == "confirmed"


async def test_correction_of_unverified_address_notifies_nobody_old(pg, pg_client):
    old = f"typo-{uuid4()}@test.com"
    tokens = await _register(pg_client, old)
    new = f"fixed-{uuid4()}@test.com"
    created = await _request(pg_client, tokens, new, await _proof(pg_client, tokens))
    assert created.status_code == 202 and created.json()["mode"] == "correction"
    assert await _outbox(pg, "email_change_started") == []
    [mail] = await _outbox(pg, "change_email")
    assert (await _confirm(pg_client, _token(mail))).status_code == 200
    assert await _outbox(pg, "email_change_done") == []
    assert (await _user(pg, new)).email_verified_at is not None


async def test_request_validation_and_proof_rules(pg, pg_client):
    email, tokens = await _verified(pg, pg_client)
    other = f"taken-{uuid4()}@test.com"
    await _register(pg_client, other)

    wrong = await pg_client.post(
        "/api/v1/auth/recent-auth/password",
        json={"password": "nope nope nope nope", "action": "change_email"},
        headers=_bearer(tokens),
    )
    assert (wrong.status_code, _code(wrong)) == (403, "current_password_invalid")
    bad_action = await pg_client.post(
        "/api/v1/auth/recent-auth/password",
        json={"password": PASSWORD, "action": "add_password"},
        headers=_bearer(tokens),
    )
    assert bad_action.status_code == 422

    proof = await _proof(pg_client, tokens)
    same = await _request(pg_client, tokens, email.upper(), proof)
    assert (same.status_code, _code(same)) == (409, "email_unchanged")
    taken = await _request(pg_client, tokens, other, proof)
    assert (taken.status_code, _code(taken)) == (409, "email_unavailable")
    invalid = await _request(pg_client, tokens, "not-an-email", proof)
    assert invalid.status_code == 422 and "input" not in invalid.text
    # None of the failures spent the proof.
    ok = await _request(pg_client, tokens, f"free-{uuid4()}@test.com", proof)
    assert ok.status_code == 202, ok.text

    # The request limiter (3/h per user) also counts refused attempts.
    _, tokens = await _verified(pg, pg_client)
    proof = await _proof(pg_client, tokens)
    assert (await _request(pg_client, tokens, f"free-{uuid4()}@test.com", proof)).status_code == 202
    reused = await _request(pg_client, tokens, f"free-{uuid4()}@test.com", proof)
    assert (reused.status_code, _code(reused)) == (409, "recent_auth_used")
    missing = await _request(pg_client, tokens, f"free-{uuid4()}@test.com", "garbage")
    assert (missing.status_code, _code(missing)) == (403, "recent_auth_required")


async def test_proof_is_bound_to_session_and_expires(pg, pg_client):
    email, first = await _verified(pg, pg_client)
    second = (await _login(pg_client, email, PASSWORD)).json()
    proof = await _proof(pg_client, first)
    other_session = await _request(pg_client, second, f"x-{uuid4()}@test.com", proof)
    assert (other_session.status_code, _code(other_session)) == (403, "recent_auth_required")

    async with pg() as db:
        for row in (await db.execute(select(RecentAuthProof))).scalars():
            row.expires_at = now_utc() - timedelta(seconds=1)
        await db.commit()
    late = await _request(pg_client, first, f"x-{uuid4()}@test.com", proof)
    assert (late.status_code, _code(late)) == (403, "recent_auth_required")


async def test_exact_retry_is_idempotent_and_changed_input_conflicts(pg, pg_client):
    _, tokens = await _verified(pg, pg_client)
    proof = await _proof(pg_client, tokens)
    request_id = uuid4()
    new = f"idem-{uuid4()}@test.com"
    first = await _request(pg_client, tokens, new, proof, request_id)
    retry = await _request(pg_client, tokens, new, proof, request_id)
    assert first.status_code == retry.status_code == 202
    assert first.json()["change_id"] == retry.json()["change_id"]
    assert len(await _outbox(pg, "change_email")) == 1
    changed = await _request(pg_client, tokens, f"other-{uuid4()}@test.com", proof, request_id)
    assert (changed.status_code, _code(changed)) == (409, "request_id_conflict")


async def test_new_request_replaces_pending_and_kills_its_link(pg, pg_client):
    _, tokens = await _verified(pg, pg_client)
    first = await _request(
        pg_client, tokens, f"a-{uuid4()}@test.com", await _proof(pg_client, tokens)
    )
    second = await _request(
        pg_client, tokens, f"b-{uuid4()}@test.com", await _proof(pg_client, tokens)
    )
    assert first.status_code == second.status_code == 202
    first_mail, second_mail = await _outbox(pg, "change_email")
    dead = await _confirm(pg_client, _token(first_mail))
    assert (dead.status_code, _code(dead)) == (400, "action_token_invalid")
    assert (await _current(pg_client, tokens))["change_id"] == second.json()["change_id"]
    async with pg() as db:
        states = (
            await db.execute(select(AccountEmailChange.state).order_by(AccountEmailChange.created_at))
        ).scalars().all()
    assert states == ["replaced", "pending"]
    assert (await _confirm(pg_client, _token(second_mail))).status_code == 200


async def test_cancel_resend_and_foreign_ids(pg, pg_client, monkeypatch):
    _, tokens = await _verified(pg, pg_client)
    _, stranger = await _verified(pg, pg_client, "stranger")
    created = await _request(
        pg_client, tokens, f"c-{uuid4()}@test.com", await _proof(pg_client, tokens)
    )
    change_id = created.json()["change_id"]

    limited = await pg_client.post(
        f"/api/v1/auth/email-change/{change_id}/resend", headers=_bearer(tokens)
    )
    assert (limited.status_code, _code(limited)) == (429, "mail_rate_limited")
    start = now_utc()
    monkeypatch.setattr(ec, "now_utc", lambda: start + timedelta(seconds=61))
    resent = await pg_client.post(
        f"/api/v1/auth/email-change/{change_id}/resend", headers=_bearer(tokens)
    )
    assert resent.status_code == 202, resent.text
    first_mail, second_mail = await _outbox(pg, "change_email")
    assert _token(first_mail) != _token(second_mail)

    foreign = await pg_client.post(
        f"/api/v1/auth/email-change/{change_id}/cancel", headers=_bearer(stranger)
    )
    assert (foreign.status_code, _code(foreign)) == (404, "email_change_not_found")
    cancelled = await pg_client.post(
        f"/api/v1/auth/email-change/{change_id}/cancel", headers=_bearer(tokens)
    )
    assert cancelled.json() == {"status": "cancelled"}
    again = await pg_client.post(
        f"/api/v1/auth/email-change/{change_id}/cancel", headers=_bearer(tokens)
    )
    assert again.json() == {"status": "cancelled"}
    for mail in (first_mail, second_mail):
        dead = await _confirm(pg_client, _token(mail))
        assert (dead.status_code, _code(dead)) == (400, "action_token_invalid")
    gone = await pg_client.post(
        f"/api/v1/auth/email-change/{change_id}/resend", headers=_bearer(tokens)
    )
    assert (gone.status_code, _code(gone)) == (409, "email_change_inactive")
    assert (await _current(pg_client, tokens))["status"] == "cancelled"


async def test_cancel_after_confirmation_is_refused(pg, pg_client):
    _, tokens = await _verified(pg, pg_client)
    new = f"done-{uuid4()}@test.com"
    created = await _request(pg_client, tokens, new, await _proof(pg_client, tokens))
    [mail] = await _outbox(pg, "change_email")
    new_tokens = None
    assert (await _confirm(pg_client, _token(mail))).status_code == 200
    new_tokens = (await _login(pg_client, new, PASSWORD)).json()
    cancel = await pg_client.post(
        f"/api/v1/auth/email-change/{created.json()['change_id']}/cancel",
        headers=_bearer(new_tokens),
    )
    assert (cancel.status_code, _code(cancel)) == (409, "email_change_completed")


async def test_password_change_and_expiry_kill_pending_change(pg, pg_client):
    email, tokens = await _verified(pg, pg_client)
    await _request(pg_client, tokens, f"p-{uuid4()}@test.com", await _proof(pg_client, tokens))
    [mail] = await _outbox(pg, "change_email")
    changed = await pg_client.post(
        "/api/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=_bearer(tokens),
    )
    assert changed.status_code == 200, changed.text
    dead = await _confirm(pg_client, _token(mail))
    assert (dead.status_code, _code(dead)) == (400, "action_token_invalid")
    assert (await _current(pg_client, changed.json()))["status"] == "cancelled"
    assert (await _user(pg, email)).email == email

    fresh = await _request(
        pg_client, changed.json(), f"q-{uuid4()}@test.com", await _proof(pg_client, changed.json(), NEW_PASSWORD)
    )
    assert fresh.status_code == 202
    async with pg() as db:
        row = await db.get(AccountEmailChange, fresh.json()["change_id"])
        row.expires_at = now_utc() - timedelta(seconds=1)
        await db.commit()
    assert (await _current(pg_client, changed.json()))["status"] == "expired"
    late = await _confirm(pg_client, _token((await _outbox(pg, "change_email"))[-1]))
    assert (late.status_code, _code(late)) == (410, "action_token_expired")


async def test_target_taken_before_confirm_changes_nothing(pg, pg_client):
    old, tokens = await _verified(pg, pg_client)
    target = f"race-{uuid4()}@test.com"
    await _request(pg_client, tokens, target, await _proof(pg_client, tokens))
    [mail] = await _outbox(pg, "change_email")
    await _register(pg_client, target)
    lost = await _confirm(pg_client, _token(mail))
    assert (lost.status_code, _code(lost)) == (409, "email_unavailable")
    assert (await pg_client.get("/api/v1/me", headers=_bearer(tokens))).status_code == 200
    assert (await _user(pg, old)).email == old


async def test_parallel_confirms_and_competing_targets_have_one_winner(pg, pg_client):
    _, first = await _verified(pg, pg_client)
    _, second = await _verified(pg, pg_client)
    target = f"same-{uuid4()}@test.com"
    for tokens in (first, second):
        created = await _request(pg_client, tokens, target, await _proof(pg_client, tokens))
        assert created.status_code == 202, created.text
    mails = await _outbox(pg, "change_email")
    results = await asyncio.gather(*(_confirm(pg_client, _token(m)) for m in mails))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert [_code(r) for r in results if r.status_code == 409] == ["email_unavailable"]

    _, third = await _verified(pg, pg_client)
    await _request(pg_client, third, f"one-{uuid4()}@test.com", await _proof(pg_client, third))
    link = _token((await _outbox(pg, "change_email"))[-1])
    twice = await asyncio.gather(_confirm(pg_client, link), _confirm(pg_client, link))
    assert sorted(r.status_code for r in twice) == [200, 409]


async def _google_only(pg, *, verified: bool = True):
    async with pg() as db:
        user = User(
            email=f"g-{uuid4()}@test.com",
            google_id=f"sub-{uuid4()}",
            email_verified_at=now_utc() if verified else None,
        )
        db.add(user)
        await db.flush()
        issued = await create_session(db, user.id)
        await db.commit()
    return user, issued


async def _add_proof(pg, user, issued) -> str:
    async with pg() as db:
        locked = await db.get(User, user.id)
        token, _ = await issue_recent_auth(
            db, locked, AccessContext(user.id, issued.session_id, 1), "add_password"
        )
        await db.commit()
    return token


async def _add(client, issued, password: str, proof: str):
    return await client.post(
        "/api/v1/auth/password/add",
        json={"new_password": password, "recent_auth_token": proof},
        headers={"Authorization": f"Bearer {issued.access_token}"},
    )


async def test_add_password_to_google_account(pg, pg_client):
    user, current = await _google_only(pg)
    async with pg() as db:
        other = await create_session(db, user.id)
        await db.commit()
    proof = await _add_proof(pg, user, current)

    weak = await _add(pg_client, current, "short", proof)
    assert (weak.status_code, _code(weak)) == (422, "password_too_short")
    done = await _add(pg_client, current, NEW_PASSWORD, proof)
    assert done.status_code == 200, done.text
    fresh = done.json()

    me = await pg_client.get("/api/v1/me", headers=_bearer(fresh))
    assert me.json()["login_methods"] == ["password", "google"]
    for stale in (current.access_token, other.access_token):
        old = await pg_client.get("/api/v1/me", headers={"Authorization": f"Bearer {stale}"})
        assert old.status_code == 401
    stored = await _user(pg, user.email)
    assert stored.password_hash.startswith("$argon2id$")
    assert stored.google_id == user.google_id
    [notice] = await _outbox(pg, "password_added")
    assert _decrypt(notice).to == user.email
    assert (await _login(pg_client, user.email, NEW_PASSWORD)).status_code == 200

    async with pg() as db:
        again = await _add_proof_row(db, user, fresh["session_id"])
    overwrite = await _add(
        pg_client, _Issued(fresh["access_token"]), NEW_PASSWORD + "!", again
    )
    assert (overwrite.status_code, _code(overwrite)) == (409, "password_already_set")


class _Issued:
    def __init__(self, access_token: str) -> None:
        self.access_token = access_token


async def _add_proof_row(db, user, session_id) -> str:
    row = await db.get(AuthSession, session_id)
    locked = await db.get(User, user.id)
    token, _ = await issue_recent_auth(
        db, locked, AccessContext(user.id, row.id, row.version), "add_password"
    )
    await db.commit()
    return token


async def test_add_password_needs_verified_address_and_a_fresh_proof(pg, pg_client):
    user, issued = await _google_only(pg, verified=False)
    proof = await _add_proof(pg, user, issued)
    blocked = await _add(pg_client, issued, NEW_PASSWORD, proof)
    assert (blocked.status_code, _code(blocked)) == (403, "email_verification_required")

    verified, ok_session = await _google_only(pg)
    missing = await _add(pg_client, ok_session, NEW_PASSWORD, "garbage")
    assert (missing.status_code, _code(missing)) == (403, "recent_auth_required")
    wrong_action = await _proof_for(pg, verified, ok_session, "change_email")
    refused = await _add(pg_client, ok_session, NEW_PASSWORD, wrong_action)
    assert (refused.status_code, _code(refused)) == (403, "recent_auth_required")
    assert (await _user(pg, verified.email)).password_hash is None


async def _proof_for(pg, user, issued, action: str) -> str:
    async with pg() as db:
        locked = await db.get(User, user.id)
        token, _ = await issue_recent_auth(
            db, locked, AccessContext(user.id, issued.session_id, 1), action
        )
        await db.commit()
    return token

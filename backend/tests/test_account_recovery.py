"""Password reset by e-mail and password change (E-001/F-004/T-002, step 2a)."""

import re
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import now_utc
from app.models import AccountActionToken, MailOutbox, User
from app.services import account_recovery as svc
from app.services.mail_outbox import _decrypt
from tests.pg_factories import auth_headers, create_profile, create_user

pytestmark = pytest.mark.pg

PASSWORD = "correct horse battery"
NEW_PASSWORD = "a much longer new passphrase"
_TOKEN = re.compile(r"/account/(?:reset-password|verify-email)#token=([A-Za-z0-9_-]+)")


def _code(response) -> str:
    return response.json()["detail"]["code"]


def _bearer(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _register(client, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _login(client, email: str, password: str):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _outbox(pg, kind: str | None = None) -> list[MailOutbox]:
    async with pg() as db:
        query = select(MailOutbox).order_by(MailOutbox.created_at)
        if kind is not None:
            query = query.where(MailOutbox.kind == kind)
        return list((await db.execute(query)).scalars())


def _token_from(row: MailOutbox) -> str:
    mail = _decrypt(row)
    assert mail is not None
    match = _TOKEN.search(mail.text)
    assert match and match.group(0) in mail.html
    return match.group(1)


async def _user(pg, email: str) -> User:
    async with pg() as db:
        return (await db.execute(select(User).where(User.email == email))).scalar_one()


async def _request_reset(client, email: str, locale: str | None = None):
    body = {"email": email} | ({"locale": locale} if locale else {})
    response = await client.post("/api/v1/auth/password-reset/request", json=body)
    assert response.status_code == 202, response.text
    assert response.json() == {"status": "accepted", "retry_after_seconds": 60}
    return response


async def _confirm(client, token: str, password: str = NEW_PASSWORD):
    return await client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": password}
    )


async def test_reset_sets_argon2_revokes_sessions_and_verifies_address(pg, pg_client):
    email = f"reset-{uuid4()}@test.com"
    first = await _register(pg_client, email)
    second = (await _login(pg_client, email, PASSWORD)).json()
    before = await _user(pg, email)
    assert before.password_hash.startswith("$2")
    assert before.email_verified_at is None

    await _request_reset(pg_client, email.upper(), locale="pl")
    [row] = await _outbox(pg, "reset_password")
    assert row.user_id == before.id and row.action_token_id is not None
    mail = _decrypt(row)
    assert (mail.locale, mail.to) == ("pl", email)
    token = _token_from(row)

    weak = await _confirm(pg_client, token, "short")
    assert (weak.status_code, _code(weak)) == (422, "password_too_short")
    async with pg() as db:
        stored = await db.get(AccountActionToken, row.action_token_id)
        assert stored.consumed_at is None

    done = await _confirm(pg_client, token)
    assert done.status_code == 200, done.text
    assert done.json() == {"status": "password_reset", "requires_login": True}
    for tokens in (first, second):
        me = await pg_client.get("/api/v1/me", headers=_bearer(tokens))
        assert (me.status_code, _code(me)) == (401, "session_revoked")

    after = await _user(pg, email)
    assert after.password_hash.startswith("$argon2id$")
    assert after.credentials_revision == before.credentials_revision + 1
    assert after.email_verified_at is not None
    [notice] = await _outbox(pg, "password_changed")
    assert notice.action_token_id is None and _decrypt(notice).to == email

    old = await _login(pg_client, email, PASSWORD)
    assert (old.status_code, _code(old)) == (401, "wrong_password")
    assert (await _login(pg_client, email, NEW_PASSWORD)).status_code == 200
    reused = await _confirm(pg_client, token, NEW_PASSWORD + "!")
    assert (reused.status_code, _code(reused)) == (409, "action_token_used")


async def test_reset_request_is_neutral_and_rate_limited(pg, pg_client, monkeypatch):
    async with pg() as db:
        google_only = await create_user(db)
        await db.commit()
    await _request_reset(pg_client, f"nobody-{uuid4()}@test.com")
    await _request_reset(pg_client, google_only.email)
    assert await _outbox(pg) == []

    email = f"limit-{uuid4()}@test.com"
    await _register(pg_client, email)
    start = now_utc()
    for offset_s, expected in ((0, 1), (30, 1), (61, 2), (122, 3), (183, 3), (3601, 4)):
        monkeypatch.setattr(svc, "now_utc", lambda o=offset_s: start + timedelta(seconds=o))
        await _request_reset(pg_client, email)
        assert len(await _outbox(pg, "reset_password")) == expected, offset_s


async def test_reset_link_expires_and_dies_after_newer_reset(pg, pg_client):
    email = f"expiry-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    async with pg() as db:
        await create_profile(db, user, "de", "es")
        for age in (timedelta(hours=2), timedelta(minutes=5), timedelta(minutes=3)):
            assert await svc.request_password_reset(db, email, None, now=now_utc() - age)
        await db.commit()
    expired, older, newer = [_token_from(row) for row in await _outbox(pg, "reset_password")]
    assert _decrypt((await _outbox(pg, "reset_password"))[0]).locale == "de"

    gone = await _confirm(pg_client, expired)
    assert (gone.status_code, _code(gone)) == (410, "action_token_expired")
    assert (await _confirm(pg_client, newer)).status_code == 200
    stale = await _confirm(pg_client, older)
    assert (stale.status_code, _code(stale)) == (400, "action_token_invalid")
    junk = await _confirm(pg_client, "not-a-token")
    assert (junk.status_code, _code(junk)) == (400, "action_token_invalid")


async def test_reset_keeps_existing_verification_time(pg, pg_client):
    email = f"verified-{uuid4()}@test.com"
    await _register(pg_client, email)
    verified_at = now_utc() - timedelta(days=3)
    async with pg() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.email_verified_at = verified_at
        await db.commit()
    await _request_reset(pg_client, email)
    [row] = await _outbox(pg, "reset_password")
    assert (await _confirm(pg_client, _token_from(row))).status_code == 200
    assert (await _user(pg, email)).email_verified_at == verified_at


async def test_change_password_keeps_only_current_session(pg, pg_client):
    email = f"change-{uuid4()}@test.com"
    current = await _register(pg_client, email)
    other = (await _login(pg_client, email, PASSWORD)).json()
    user = await _user(pg, email)
    async with pg() as db:
        await create_profile(db, user, "es", "en")
        await db.commit()

    async def change(tokens, current_password, new_password):
        return await pg_client.post(
            "/api/v1/auth/password/change",
            headers=_bearer(tokens),
            json={"current_password": current_password, "new_password": new_password},
        )

    wrong = await change(current, "not the password", NEW_PASSWORD)
    assert (wrong.status_code, _code(wrong)) == (403, "current_password_invalid")
    weak = await change(current, PASSWORD, "short")
    assert (weak.status_code, _code(weak)) == (422, "password_too_short")

    changed = await change(current, PASSWORD, NEW_PASSWORD)
    assert changed.status_code == 200, changed.text
    assert changed.headers["cache-control"] == "no-store"
    renewed = changed.json()
    assert renewed["session_id"] == current["session_id"]
    assert (await pg_client.get("/api/v1/me", headers=_bearer(renewed))).status_code == 200
    assert (await pg_client.get("/api/v1/me", headers=_bearer(current))).status_code == 401
    me = await pg_client.get("/api/v1/me", headers=_bearer(other))
    assert (me.status_code, _code(me)) == (401, "session_revoked")

    [notice] = await _outbox(pg, "password_changed")
    assert _decrypt(notice).locale == "es"
    assert (await _user(pg, email)).password_hash.startswith("$argon2id$")
    assert (await _login(pg_client, email, NEW_PASSWORD)).status_code == 200
    # Argon2 hashes are verified too, so a second change works.
    again = await change(renewed, NEW_PASSWORD, NEW_PASSWORD + " again")
    assert again.status_code == 200, again.text


async def test_change_password_requires_existing_password(pg, pg_client):
    async with pg() as db:
        user = await create_user(db)
        headers = await auth_headers(db, user)
        await db.commit()
    response = await pg_client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={"current_password": "", "new_password": NEW_PASSWORD},
    )
    assert (response.status_code, _code(response)) == (403, "password_not_set")
    assert await _outbox(pg) == []


async def _verify_status(client, tokens) -> dict:
    response = await client.get("/api/v1/auth/email-verification/status", headers=_bearer(tokens))
    assert response.status_code == 200, response.text
    return response.json()


async def test_registration_queues_verification_and_link_verifies(pg, pg_client):
    email = f"verify-{uuid4()}@test.com"
    response = await pg_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "locale": "pt-rBR"},
    )
    assert response.status_code == 200, response.text
    tokens = response.json()
    me = (await pg_client.get("/api/v1/me", headers=_bearer(tokens))).json()
    assert (me["email_verified"], me["login_methods"]) == (False, ["password"])
    assert "password_hash" not in me

    [row] = await _outbox(pg, "verify_email")
    assert (_decrypt(row).locale, _decrypt(row).to) == ("pt-BR", email)
    status = await _verify_status(pg_client, tokens)
    assert status["email_verified"] is False
    assert (status["delivery_status"], status["delivery_delayed"]) == ("queued", False)
    assert status["resend_available_at"] is not None

    limited = await pg_client.post(
        "/api/v1/auth/email-verification/request", headers=_bearer(tokens)
    )
    assert (limited.status_code, _code(limited)) == (429, "mail_rate_limited")
    assert 1 <= int(limited.headers["retry-after"]) <= 60

    token = _token_from(row)
    confirmed = await pg_client.post(
        "/api/v1/auth/email-verification/confirm", json={"token": token}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json() == {"status": "email_verified"}
    me = (await pg_client.get("/api/v1/me", headers=_bearer(tokens))).json()
    assert me["email_verified"] is True
    again = await pg_client.post("/api/v1/auth/email-verification/confirm", json={"token": token})
    assert (again.status_code, _code(again)) == (409, "action_token_used")

    already = await pg_client.post(
        "/api/v1/auth/email-verification/request", headers=_bearer(tokens)
    )
    assert already.status_code == 200
    assert already.json() == {"status": "already_verified"}
    status = await _verify_status(pg_client, tokens)
    assert (status["email_verified"], status["resend_available_at"]) == (True, None)
    assert len(await _outbox(pg, "verify_email")) == 1


async def test_verification_resend_and_delivery_states(pg, pg_client, monkeypatch):
    email = f"resend-{uuid4()}@test.com"
    tokens = await _register(pg_client, email)
    start = now_utc()
    monkeypatch.setattr(svc, "now_utc", lambda: start + timedelta(seconds=61))
    resent = await pg_client.post(
        "/api/v1/auth/email-verification/request", headers=_bearer(tokens)
    )
    assert resent.status_code == 202, resent.text
    assert resent.json() == {"status": "accepted", "retry_after_seconds": 60}
    rows = await _outbox(pg, "verify_email")
    assert len(rows) == 2

    async def latest_state(dispatch: str, delivery: str) -> tuple[str, bool]:
        async with pg() as db:
            row = await db.get(MailOutbox, rows[-1].id)
            row.dispatch_state, row.delivery_state = dispatch, delivery
            await db.commit()
        status = await _verify_status(pg_client, tokens)
        return status["delivery_status"], status["delivery_delayed"]

    assert await latest_state("accepted", "unknown") == ("provider_accepted", False)
    assert await latest_state("accepted", "delayed") == ("provider_accepted", True)
    assert await latest_state("accepted", "delivered") == ("delivered", False)
    assert await latest_state("accepted", "bounced") == ("failed", False)
    assert await latest_state("cancelled", "unknown") == ("failed", False)

    # Both links stay valid: a resend does not break the earlier one.
    first = await pg_client.post(
        "/api/v1/auth/email-verification/confirm", json={"token": _token_from(rows[0])}
    )
    assert first.status_code == 200


async def test_expired_verification_link(pg, pg_client):
    email = f"late-{uuid4()}@test.com"
    await _register(pg_client, email)
    user = await _user(pg, email)
    async with pg() as db:
        locked = await db.get(User, user.id)
        await svc.queue_verification_mail(db, locked, "en", now=now_utc() - timedelta(hours=25))
        await db.commit()
    old = min(await _outbox(pg, "verify_email"), key=lambda r: r.created_at)
    gone = await pg_client.post(
        "/api/v1/auth/email-verification/confirm", json={"token": _token_from(old)}
    )
    assert (gone.status_code, _code(gone)) == (410, "action_token_expired")
    assert (await _user(pg, email)).email_verified_at is None


async def test_mail_unavailable_refuses_before_writing(pg, pg_client, monkeypatch):
    from app.core.config import Settings

    monkeypatch.setattr(Settings, "mail_ready", lambda self: False)
    email = f"nomail-{uuid4()}@test.com"
    response = await pg_client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert (response.status_code, _code(response)) == (503, "mail_temporarily_unavailable")
    reset = await pg_client.post("/api/v1/auth/password-reset/request", json={"email": email})
    assert (reset.status_code, _code(reset)) == (503, "mail_temporarily_unavailable")
    async with pg() as db:
        assert (await db.execute(select(User).where(User.email == email))).first() is None

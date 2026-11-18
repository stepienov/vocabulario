"""E-001/F-004/T-002: Resend delivery events (Svix webhook) on real PostgreSQL."""

import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from svix.webhooks import Webhook

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import MailOutbox, MailProviderEvent, User
from app.services.account_recovery import verification_status
from app.services.action_tokens import VERIFY_EMAIL, issue_action_token
from app.services.mail_events import apply_events
from tests.pg_factories import create_user

pytestmark = pytest.mark.pg

SECRET = "whsec_" + "dGVzdC1zZWNyZXQtZm9yLXN2aXgtdGVzdHM="
URL = "/api/v1/auth/mail-events"


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_webhook_secret", SECRET)


def _signed(event_type, message_id, *, msg_id="msg_1", age=timedelta(0), secret=SECRET):
    body = json.dumps(
        {
            "type": event_type,
            "created_at": now_utc().isoformat(),
            "data": {"email_id": message_id, "to": ["private@example.com"]},
        }
    )
    stamp = now_utc() - age
    signature = Webhook(secret).sign(msg_id, stamp, body)
    headers = {
        "svix-id": msg_id,
        "svix-timestamp": str(int(stamp.timestamp())),
        "svix-signature": signature,
        "content-type": "application/json",
    }
    return body, headers


async def _outbox(pg, *, message_id="re_1", dispatch="accepted", verify=False):
    now = now_utc()
    async with pg() as session:
        user = await create_user(session)
        token_id = None
        if verify:
            issued = await issue_action_token(session, user, VERIFY_EMAIL, now=now)
            token_id = issued.row.id
        row = MailOutbox(
            user_id=user.id,
            kind="verify_email" if verify else "password_changed",
            action_token_id=token_id,
            payload_ciphertext=b"x",
            dispatch_state=dispatch,
            delivery_state="unknown",
            attempts=1,
            next_attempt_at=now,
            provider_message_id=message_id,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        session.add(row)
        await session.commit()
        return row.id, user.id


async def _state(pg, outbox_id):
    async with pg() as session:
        return (
            await session.execute(
                select(MailOutbox.delivery_state).where(MailOutbox.id == outbox_id)
            )
        ).scalar_one()


async def _post(client, event_type, message_id, **kwargs):
    body, headers = _signed(event_type, message_id, **kwargs)
    return await client.post(URL, content=body, headers=headers)


async def test_delivered_event_updates_outbox_and_stores_no_recipient(pg, pg_client):
    outbox_id, _ = await _outbox(pg)
    response = await _post(pg_client, "email.delivered", "re_1")
    assert response.status_code == 204
    assert await _state(pg, outbox_id) == "delivered"
    async with pg() as session:
        columns = [c.name for c in MailProviderEvent.__table__.columns]
        assert "private@example.com" not in str(
            (await session.execute(select(MailProviderEvent))).all()
        )
    assert set(columns) == {
        "svix_id",
        "provider_message_id",
        "event_type",
        "occurred_at",
        "received_at",
    }


async def test_bad_signature_and_old_timestamp_change_nothing(pg, pg_client):
    outbox_id, _ = await _outbox(pg)
    other = "whsec_" + "b3RoZXItc2VjcmV0LW90aGVyLXNlY3JldC0xMjM="
    bad = await _post(pg_client, "email.delivered", "re_1", secret=other)
    old = await _post(pg_client, "email.delivered", "re_1", age=timedelta(minutes=10))
    assert bad.status_code == 400 and old.status_code == 400
    assert bad.json()["detail"]["code"] == "invalid_webhook"
    assert await _state(pg, outbox_id) == "unknown"
    async with pg() as session:
        assert (await session.execute(select(func.count()).select_from(MailProviderEvent))).scalar_one() == 0


async def test_missing_secret_answers_503(pg, pg_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_webhook_secret", "")
    response = await _post(pg_client, "email.delivered", "re_1")
    assert response.status_code == 503


async def test_duplicate_is_204_without_second_effect_and_weaker_event_does_not_win(pg, pg_client):
    outbox_id, _ = await _outbox(pg)
    assert (await _post(pg_client, "email.bounced", "re_1", msg_id="a")).status_code == 204
    assert (await _post(pg_client, "email.bounced", "re_1", msg_id="a")).status_code == 204
    assert (await _post(pg_client, "email.delivered", "re_1", msg_id="b")).status_code == 204
    assert (await _post(pg_client, "email.delivery_delayed", "re_1", msg_id="c")).status_code == 204
    assert await _state(pg, outbox_id) == "bounced"
    async with pg() as session:
        assert (await session.execute(select(func.count()).select_from(MailProviderEvent))).scalar_one() == 3


async def test_event_before_message_id_is_applied_when_id_is_saved(pg, pg_client):
    assert (await _post(pg_client, "email.delivered", "re_late")).status_code == 204
    outbox_id, _ = await _outbox(pg, message_id="re_late")
    await apply_events("re_late")
    assert await _state(pg, outbox_id) == "delivered"


async def test_unknown_and_sent_events_are_recorded_without_effect(pg, pg_client):
    outbox_id, _ = await _outbox(pg)
    assert (await _post(pg_client, "email.sent", "re_1", msg_id="s")).status_code == 204
    assert (await _post(pg_client, "email.opened", "re_1", msg_id="o")).status_code == 204
    assert await _state(pg, outbox_id) == "unknown"


async def test_status_maps_failed_and_delayed(pg, pg_client):
    _, user_id = await _outbox(pg, verify=True)
    await _post(pg_client, "email.delivery_delayed", "re_1", msg_id="d")
    async with pg() as session:
        state = await verification_status(session, await session.get(User, user_id))
    assert (state.delivery_status, state.delivery_delayed) == ("provider_accepted", True)
    await _post(pg_client, "email.suppressed", "re_1", msg_id="e")
    async with pg() as session:
        state = await verification_status(session, await session.get(User, user_id))
    assert state.delivery_status == "failed"

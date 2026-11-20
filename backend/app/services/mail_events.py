"""Provider delivery events for account mail (E-001/F-004/T-002).

The webhook only records what the provider reports. It never confirms an address or a
password. Events are stored first (deduplicated by `svix-id`), then folded into
`mail_outbox.delivery_state`; either order of "event arrives" and "message id saved" ends
in the same state because both sides re-read the stored events after their own commit.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.security import now_utc
from app.db import session as db_session
from app.models import MailOutbox, MailProviderEvent

logger = logging.getLogger(__name__)

# Higher rank wins; a late weaker event never erases a stronger one.
_EVENT_STATE = {
    "email.delivery_delayed": "delayed",
    "email.delivered": "delivered",
    "email.failed": "failed",
    "email.suppressed": "suppressed",
    "email.bounced": "bounced",
    "email.complained": "complained",
}
_RANK = {
    "unknown": 0,
    "delayed": 1,
    "delivered": 2,
    "failed": 3,
    "suppressed": 4,
    "bounced": 5,
    "complained": 6,
}
MAX_BODY_BYTES = 64 * 1024


class WebhookRejected(Exception):
    """Maps to the API error `code` with `status_code`; nothing was stored."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class ProviderEvent:
    svix_id: str
    event_type: str
    provider_message_id: str
    occurred_at: datetime


def verify_and_parse(body: bytes, headers: dict[str, str]) -> ProviderEvent:
    """Check the Svix signature over the raw body (5 min timestamp tolerance), then parse."""
    from svix.webhooks import Webhook, WebhookVerificationError

    secret = get_settings().resend_webhook_secret.strip()
    if not secret:
        raise WebhookRejected(503, "mail_events_unconfigured")
    if len(body) > MAX_BODY_BYTES:
        raise WebhookRejected(400, "invalid_webhook")
    try:
        Webhook(secret).verify(body, headers)
        payload = json.loads(body)
    except (WebhookVerificationError, ValueError):
        raise WebhookRejected(400, "invalid_webhook") from None
    if not isinstance(payload, dict):
        raise WebhookRejected(400, "invalid_webhook")
    data = payload.get("data")
    message_id = data.get("email_id") if isinstance(data, dict) else None
    event_type = payload.get("type")
    svix_id = headers.get("svix-id", "")
    if not (
        isinstance(event_type, str)
        and isinstance(message_id, str)
        and message_id
        and svix_id
    ):
        raise WebhookRejected(400, "invalid_webhook")
    return ProviderEvent(
        svix_id=svix_id[:128],
        event_type=event_type[:48],
        provider_message_id=message_id[:128],
        occurred_at=_parse_time(payload.get("created_at")),
    )


def _parse_time(value: object) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return now_utc()
        if parsed.tzinfo is not None:
            return parsed
    return now_utc()


async def record_event(event: ProviderEvent) -> bool:
    """Persist the event once; False for an exact duplicate."""
    async with db_session.async_session_factory() as db:
        result = await db.execute(
            pg_insert(MailProviderEvent)
            .values(
                svix_id=event.svix_id,
                provider_message_id=event.provider_message_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                received_at=now_utc(),
            )
            .on_conflict_do_nothing(index_elements=["svix_id"])
        )
        await db.commit()
        return bool(result.rowcount)


async def apply_events(provider_message_id: str) -> None:
    """Fold all stored events of one message into its outbox row (idempotent)."""
    async with db_session.async_session_factory() as db:
        row = (
            await db.execute(
                select(MailOutbox)
                .where(MailOutbox.provider_message_id == provider_message_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            return
        types = (
            await db.execute(
                select(MailProviderEvent.event_type).where(
                    MailProviderEvent.provider_message_id == provider_message_id
                )
            )
        ).scalars()
        best = row.delivery_state
        for event_type in types:
            state = _EVENT_STATE.get(event_type)
            if state is not None and _RANK[state] > _RANK[best]:
                best = state
        if best != row.delivery_state:
            await db.execute(
                update(MailOutbox).where(MailOutbox.id == row.id).values(delivery_state=best)
            )
        await db.commit()


async def handle_webhook(body: bytes, headers: dict[str, str]) -> None:
    event = verify_and_parse(body, headers)
    if event.event_type not in _EVENT_STATE and event.event_type != "email.sent":
        logger.info("mail provider event ignored: %s", event.event_type)
    if await record_event(event):
        await apply_events(event.provider_message_id)

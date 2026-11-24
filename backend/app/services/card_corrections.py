"""Read-only access to legacy correction history and escalations."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminEscalation, CardHistoryEvent


async def mark_escalation_done(db: AsyncSession, escalation_id: UUID) -> AdminEscalation | None:
    row = await db.get(AdminEscalation, escalation_id)
    if row is None:
        return None
    row.status = "done"
    row.resolved_at = datetime.now(UTC)
    await db.flush()
    return row


def history_event_response(event: CardHistoryEvent, all_events: list[CardHistoryEvent]) -> dict:
    return {
        "id": event.id,
        "card_id": event.card_id,
        "event_type": event.event_type,
        "actor": event.actor,
        "result_code": event.result_code,
        "summary": event.summary,
        "payload": event.payload,
        "created_at": event.created_at,
        "can_restore": False,
    }

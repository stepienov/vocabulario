"""E-001/F-008/T-004: cykl utrzymania, alerty z deduplikacją i heartbeat."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import ContentReport, MailOutbox, OpsAlert
from app.services import ai_budget, card_jobs, maintenance
from app.services.mail_transport import SendResult
from tests.pg_factories import create_user

pytestmark = pytest.mark.pg


class FakeTransport:
    def __init__(self):
        self.sent = []

    async def send(self, mail, idempotency_key):
        self.sent.append(mail)
        return SendResult("accepted", provider_message_id="m")


@pytest.fixture
def transport(monkeypatch):
    fake = FakeTransport()
    monkeypatch.setattr(maintenance, "get_transport", lambda: fake)
    settings = get_settings()
    monkeypatch.setattr(settings, "operator_alert_email", "ops@example.org")
    monkeypatch.setattr(settings, "mail_from", "Vocabulario <noreply@example.org>")
    return fake


def _status(spent: str, warn="70", hard="100", older="0") -> ai_budget.BudgetStatus:
    return ai_budget.BudgetStatus(
        period="2026-05",
        spent=Decimal(spent),
        reserved=Decimal(0),
        unresolved=Decimal(0),
        warn=Decimal(warn),
        hard=Decimal(hard),
        unresolved_older=Decimal(older),
    )


@pytest.mark.parametrize(
    ("spent", "level"),
    [("10", 0), ("48", 0), ("49", 1), ("63", 2), ("71", 3), ("99.9", 3), ("100", 4)],
)
def test_budget_levels(spent, level):
    assert maintenance.budget_level(_status(spent)) == level


async def test_alert_is_sent_once_reminded_after_six_hours_and_closed_on_recovery(pg, transport):
    start = now_utc()
    assert await maintenance.raise_alert("ai_budget", 1, "warn", start)
    assert not await maintenance.raise_alert("ai_budget", 1, "warn", start + timedelta(hours=5))
    assert await maintenance.raise_alert("ai_budget", 1, "warn", start + timedelta(hours=7))
    assert await maintenance.raise_alert("ai_budget", 2, "worse", start + timedelta(hours=8))
    assert await maintenance.raise_alert("ai_budget", 0, "ok", start + timedelta(hours=9))
    assert not await maintenance.raise_alert("ai_budget", 0, "ok", start + timedelta(hours=10))
    assert len(transport.sent) == 4
    async with pg() as db:
        row = (await db.execute(select(OpsAlert))).scalar_one()
    assert row.active is False and row.environment == get_settings().environment[:16]


async def test_failed_delivery_is_retried_on_the_next_cycle(pg, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "operator_alert_email", "")
    monkeypatch.setattr(settings, "support_email", "")
    now = now_utc()
    assert not await maintenance.raise_alert("mail_stuck", 1, "x", now)
    fake = FakeTransport()
    monkeypatch.setattr(maintenance, "get_transport", lambda: fake)
    monkeypatch.setattr(settings, "support_email", "help@example.org")
    monkeypatch.setattr(settings, "mail_from", "noreply@example.org")
    assert await maintenance.raise_alert("mail_stuck", 1, "x", now + timedelta(minutes=15))
    assert [m.to for m in fake.sent] == ["help@example.org"]


async def test_budget_review_alerts_and_wakes_parked_cards_only_with_room(pg, transport, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_monthly_warn_usd", Decimal("70"))
    monkeypatch.setattr(settings, "ai_monthly_hard_usd", Decimal("100"))
    woken = []

    async def resume(limit=50):
        woken.append(limit)

    monkeypatch.setattr(card_jobs, "resume_waiting_budget", resume)

    async def reached(now=None):
        return _status("100")

    monkeypatch.setattr(ai_budget, "status", reached)
    await maintenance._review_budget(now_utc())
    assert woken == [] and "level 4" in transport.sent[-1].subject

    async def relaxed(now=None):
        return _status("10")

    monkeypatch.setattr(ai_budget, "status", relaxed)
    await maintenance._review_budget(now_utc() + timedelta(minutes=15))
    assert len(woken) == 1
    assert "back to normal" in transport.sent[-1].text


async def test_budget_review_is_idle_without_a_limit(pg, transport, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_monthly_hard_usd", Decimal(0))
    await maintenance._review_budget(now_utc())
    assert transport.sent == []


async def test_stuck_mail_and_overdue_reports_raise_alerts(pg, transport):
    now = now_utc()
    async with pg() as db:
        db.add(
            MailOutbox(
                kind="verify_email",
                payload_ciphertext=b"x",
                dispatch_state="queued",
                next_attempt_at=now,
                created_at=now - timedelta(minutes=30),
                expires_at=now + timedelta(hours=1),
            )
        )
        await db.commit()
    await maintenance._review_mail(now)
    assert [m.subject.split("] ")[1] for m in transport.sent] == ["mail_stuck level 1"]
    assert "@" not in transport.sent[0].text.replace("ops@example.org", "")

    async with pg() as db:
        user = await create_user(db)
        db.add(
            ContentReport(
                user_id=user.id,
                client_report_id=uuid4(),
                fingerprint="f" * 64,
                profile_id=uuid4(),
                target_kind="card",
                field="meaning",
                reason="wrong",
                excerpt="x",
                received_at=now - timedelta(hours=40),
            )
        )
        await db.commit()
    await maintenance._review_reports(now)
    assert [m.subject.split("] ")[1] for m in transport.sent][1:] == ["reports_overdue level 1"]


async def test_cycle_writes_heartbeat_and_survives_a_failing_step(pg, transport, monkeypatch):
    async def broken(now):
        raise RuntimeError("boom")

    monkeypatch.setattr(maintenance, "_review_mail", broken)
    reached = []

    async def probe(now):
        reached.append(now)

    monkeypatch.setattr(maintenance, "_review_reports", probe)
    now = now_utc()
    await maintenance.run_cycle(now)
    assert reached == [now]
    beat = await maintenance.last_heartbeat()
    assert beat is not None and abs((beat - now).total_seconds()) < 1

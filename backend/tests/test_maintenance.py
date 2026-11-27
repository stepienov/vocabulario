"""E-001/F-008/T-004: cykl utrzymania, alerty z deduplikacją i heartbeat."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import now_utc
from app.models import (
    ContentReport,
    ImportJob,
    ImportJobEvent,
    ImportJobItem,
    LearningCard,
    LookupEvent,
    LookupQueryCache,
    MailOutbox,
    OpsAlert,
)
from app.services import ai_budget, card_jobs, data_retention, import_jobs, maintenance
from app.services.mail_transport import SendResult
from tests.pg_factories import create_card, create_list, create_profile, create_user

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


async def test_daily_account_warning_is_aggregate_and_does_not_block(pg, transport, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_monthly_warn_usd", Decimal("70"))
    monkeypatch.setattr(settings, "ai_monthly_hard_usd", Decimal("100"))

    async def relaxed(now=None):
        return _status("10")

    async def daily(threshold, now=None):
        assert threshold == Decimal("2")
        return Decimal("2.50"), 1

    monkeypatch.setattr(ai_budget, "status", relaxed)
    monkeypatch.setattr(ai_budget, "daily_account_cost_status", daily)
    await maintenance._review_budget(now_utc())
    alert = next(mail for mail in transport.sent if "ai_account_daily" in mail.subject)
    assert "1 account(s)" in alert.text and "highest estimated spend is 2.50 USD" in alert.text
    assert "No account is blocked." in alert.text
    assert "user_id" not in alert.text


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
    retention_runs = []

    async def privacy_retention(now):
        retention_runs.append(now)

    monkeypatch.setattr(maintenance, "_privacy_retention", privacy_retention)
    now = now_utc()
    await maintenance.run_cycle(now)
    assert reached == [now]
    assert retention_runs == [now]
    beat = await maintenance.last_heartbeat()
    assert beat is not None and abs((beat - now).total_seconds()) < 1


async def test_retention_removes_old_lookup_events_and_unused_cache_without_deleting_cards(pg):
    now = now_utc()
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        old = LookupEvent(
            user_id=user.id, profile_id=profile.id, query="old", query_norm="old",
            created_at=now - timedelta(days=30, seconds=1),
        )
        boundary = LookupEvent(
            user_id=user.id, profile_id=profile.id, query="new", query_norm="new",
            created_at=now - timedelta(days=30),
        )
        db.add_all([old, boundary])
        await db.flush()
        card = await create_card(db, profile, "casa", "noun")
        card.lookup_event_id = old.id
        stale = LookupQueryCache(
            lang_pair="pl>es", input_norm="stale", candidates=[],
            updated_at=now - timedelta(days=90, seconds=1),
        )
        recent = LookupQueryCache(
            lang_pair="pl>es", input_norm="recent", candidates=[],
            created_at=now - timedelta(days=200), updated_at=now - timedelta(days=90),
        )
        db.add_all([stale, recent])
        await db.commit()
        old_id, boundary_id, card_id = old.id, boundary.id, card.id
        stale_id, recent_id = stale.id, recent.id

    await maintenance._privacy_retention(now)

    async with pg() as db:
        assert await db.get(LookupEvent, old_id) is None
        assert await db.get(LookupEvent, boundary_id) is not None
        assert (await db.get(LearningCard, card_id)).lookup_event_id is None
        assert await db.get(LookupQueryCache, stale_id) is None
        assert await db.get(LookupQueryCache, recent_id) is not None


async def test_retention_scrubs_finished_import_inputs_without_breaking_queue_or_quota(pg):
    now = now_utc()
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        word_list = await create_list(db, profile, "Import")
        old = ImportJob(
            user_id=user.id, profile_id=profile.id, list_id=word_list.id, status="done",
            finished_at=now - timedelta(days=31), source_name="private file",
            current_label="private label", error_message="private error", input_sha256="a" * 64,
            input_meta={"raw_text": "private text", "field_names": ["private field"]},
        )
        recent = ImportJob(
            user_id=user.id, profile_id=profile.id, list_id=word_list.id, status="failed",
            finished_at=now - timedelta(days=30), input_meta={"raw_text": "recent"},
        )
        active = ImportJob(
            user_id=user.id, profile_id=profile.id, list_id=word_list.id, status="review",
            created_at=now - timedelta(days=40), input_meta={"raw_text": "active"},
        )
        legacy = ImportJob(
            user_id=user.id, profile_id=profile.id, list_id=word_list.id, status="cancelled",
            updated_at=now - timedelta(days=31), input_meta={"raw_text": "legacy"},
        )
        db.add_all([old, recent, active, legacy])
        await db.flush()
        card = await create_card(db, profile, "casa", "noun")
        card.import_job_id = old.id
        item = ImportJobItem(
            job_id=old.id, ordinal=0, raw_note=["private text"], input_label="private text",
            reason_detail="private error", last_error="private error", lemma="casa",
            created_card_id=card.id,
        )
        report = ImportJobEvent(job_id=old.id, event="llm_fail", payload={"err": "private text"})
        db.add_all([item, report])
        await db.commit()
        old_id, recent_id, active_id, legacy_id = old.id, recent.id, active.id, legacy.id
        item_id, report_id, card_id, profile_id = item.id, report.id, card.id, profile.id

    async with pg() as db:
        assert await data_retention.purge_expired(db, now) == {
            "lookups": 0, "cache": 0, "imports": 2,
        }
        await db.commit()
    async with pg() as db:
        old = await db.get(ImportJob, old_id)
        item = await db.get(ImportJobItem, item_id)
        assert old.status == "done" and old.input_meta == {"retention_scrubbed": True}
        assert old.source_name == "" and old.current_label is None
        assert old.error_message is None and old.input_sha256 is None
        assert item.raw_note == [] and item.input_label == ""
        assert item.reason_detail is None and item.last_error is None
        assert item.lemma == "casa" and item.created_card_id == card_id
        assert (await db.get(ImportJobEvent, report_id)).payload is None
        assert (await db.get(ImportJob, recent_id)).input_meta["raw_text"] == "recent"
        assert (await db.get(ImportJob, active_id)).input_meta["raw_text"] == "active"
        assert (await db.get(ImportJob, legacy_id)).input_meta == {"retention_scrubbed": True}
        assert await import_jobs.import_queue_head(db, profile_id) == card_id
        assert await import_jobs.daily_import_used(db, profile_id) == 1
        assert (await data_retention.purge_expired(db, now))["imports"] == 0
        await db.commit()


async def test_category_cache_reads_refresh_last_use(pg):
    from app.services.lexical import LexicalService

    now = now_utc()
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        service = LexicalService(db)
        word = LookupQueryCache(
            lang_pair="pl>es", input_norm=service._assoc_key("red"),
            candidates=[{"lemma": "rojo", "pos": "adj", "gloss": "red"}],
            updated_at=now - timedelta(days=91),
        )
        round_one = LookupQueryCache(
            lang_pair="pl>es", input_norm=service._assoc_key("red", 1),
            candidates=[{"lemma": "rojo", "pos": "adj", "gloss": "red"}],
            updated_at=now - timedelta(days=91),
        )
        db.add_all([word, round_one])
        await db.commit()
        word_id, round_id = word.id, round_one.id
        user_id, profile_id = user.id, profile.id
        await service.lookup_category_cached(user, profile_id, "red")
        await db.commit()
        await service.lookup_assoc_round(user_id, profile_id, "red", 1)

    await maintenance._privacy_retention(now)
    async with pg() as db:
        assert (await db.get(LookupQueryCache, word_id)).updated_at >= now
        assert (await db.get(LookupQueryCache, round_id)).updated_at >= now


async def test_cache_cleanup_racing_with_a_read_does_not_fail_lookup(pg, monkeypatch):
    from app.services.lexical import LexicalService

    now = now_utc()
    async with pg() as db:
        user = await create_user(db)
        profile = await create_profile(db, user, "pl", "es")
        db.add(
            LookupQueryCache(
                lang_pair="pl>es", input_norm="prado",
                candidates=[{"lemma": "prado", "pos": "noun", "gloss": "meadow"}],
                updated_at=now - timedelta(days=91),
            )
        )
        await db.commit()
        service = LexicalService(db)
        fetch = service._fetch_query_cache

        async def fetch_before_cleanup(*args, **kwargs):
            row = await fetch(*args, **kwargs)
            async with pg() as cleanup_db:
                await data_retention.purge_expired(cleanup_db, now)
                await cleanup_db.commit()
            return row

        monkeypatch.setattr(service, "_fetch_query_cache", fetch_before_cleanup)
        outcome = await service.lookup_cached(user, profile.id, "prado", annotate=False)
        await db.commit()
        assert outcome.candidates[0]["lemma"] == "prado"

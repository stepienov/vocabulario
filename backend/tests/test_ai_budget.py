import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.models import AiBudgetPeriod, AiBudgetReservation
from app.services import ai_budget
from app.services.card_jobs import WAITING_BUDGET, _apply_enrich_retry
from app.services.llm import LLMService
from app.services.llm_pricing import TokenUsage, estimate_max_cost_usd

MODEL = "gpt-5.6-luna"
CHARS = 1000
MAX_TOKENS = 1000


def _estimate() -> Decimal:
    value = estimate_max_cost_usd(MODEL, CHARS, MAX_TOKENS)
    assert value is not None
    return value


@pytest.fixture
def cap(monkeypatch):
    """Room for exactly three worst-case calls."""
    settings = get_settings()
    hard = _estimate() * 3 + _estimate() / 2
    monkeypatch.setattr(settings, "ai_monthly_hard_usd", hard)
    monkeypatch.setattr(settings, "ai_monthly_warn_usd", hard / 2)
    return hard


async def _period(pg, key=None) -> AiBudgetPeriod:
    async with pg() as db:
        return (
            await db.execute(
                select(AiBudgetPeriod).where(AiBudgetPeriod.period == (key or ai_budget.period_key()))
            )
        ).scalar_one()


def _llm(monkeypatch, behaviour) -> LLMService:
    service = object.__new__(LLMService)
    service.mock = False
    service._anthropic = None
    monkeypatch.setattr(service, "_chat_json_openai", behaviour, raising=False)
    return service


async def _call(service: LLMService):
    return await service._chat_json(
        MODEL, "x" * CHARS, None, max_tokens=MAX_TOKENS, provider="openai", purpose="test"
    )


@pytest.mark.pg
async def test_settle_charges_the_real_cost_and_frees_the_reservation(pg, cap):
    reservation = await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    assert reservation is not None
    assert (await _period(pg)).reserved_usd == reservation.amount
    await ai_budget.settle(reservation, MODEL, TokenUsage(prompt_tokens=100, completion_tokens=50))
    row = await _period(pg)
    assert row.reserved_usd == 0
    assert 0 < row.spent_usd < reservation.amount
    await ai_budget.settle(reservation, MODEL, TokenUsage(prompt_tokens=100, completion_tokens=50))
    assert (await _period(pg)).spent_usd == row.spent_usd


@pytest.mark.pg
async def test_parallel_reservations_never_exceed_the_cap(pg, cap):
    results = await asyncio.gather(
        *(ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS) for _ in range(10)),
        return_exceptions=True,
    )
    granted = [r for r in results if isinstance(r, ai_budget.Reservation)]
    refused = [r for r in results if isinstance(r, ai_budget.AiBudgetExhausted)]
    assert len(granted) == 3 and len(refused) == 7
    assert (await _period(pg)).reserved_usd == _estimate() * 3


@pytest.mark.pg
async def test_a_released_call_frees_budget_but_an_unknown_one_keeps_it(pg, cap):
    first = await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    second = await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    third = await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    with pytest.raises(ai_budget.AiBudgetExhausted):
        await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    await ai_budget.release(first)
    await ai_budget.leave_unresolved(second)
    await ai_budget.settle(third, MODEL, None)  # provider answered but sent no usage
    row = await _period(pg)
    assert row.reserved_usd == 0
    assert row.unresolved_usd == _estimate() * 2
    assert (await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)) is not None
    with pytest.raises(ai_budget.AiBudgetExhausted):
        await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)


@pytest.mark.pg
async def test_months_are_counted_separately(pg, cap):
    june = datetime(2026, 6, 30, 23, 59, tzinfo=UTC)
    july = june + timedelta(minutes=2)
    for _ in range(3):
        assert await ai_budget.reserve(MODEL, "t", CHARS, MAX_TOKENS, now=june)
    with pytest.raises(ai_budget.AiBudgetExhausted):
        await ai_budget.reserve(MODEL, "t", CHARS, MAX_TOKENS, now=june)
    assert await ai_budget.reserve(MODEL, "t", CHARS, MAX_TOKENS, now=july)
    assert (await _period(pg, "2026-07")).reserved_usd == _estimate()


@pytest.mark.pg
async def test_a_reservation_that_never_settled_becomes_unresolved(pg, cap):
    reservation = await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    async with pg() as db:
        await db.execute(
            update(AiBudgetReservation).values(created_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await db.commit()
    assert await ai_budget.sweep_stale() == 1
    row = await _period(pg)
    assert (row.reserved_usd, row.unresolved_usd) == (0, reservation.amount)
    assert await ai_budget.sweep_stale() == 0


@pytest.mark.pg
async def test_operator_can_replace_unresolved_with_the_real_cost(pg, cap):
    reservation = await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    await ai_budget.leave_unresolved(reservation)
    cleared = await ai_budget.resolve_unresolved(ai_budget.period_key(), Decimal("0.0001"))
    row = await _period(pg)
    assert cleared == reservation.amount
    assert (row.unresolved_usd, row.spent_usd) == (0, Decimal("0.0001"))


@pytest.mark.pg
async def test_unpriced_model_stops_the_call(pg, cap):
    with pytest.raises(ai_budget.AiBudgetUnavailable):
        await ai_budget.reserve("not-priced", "test", CHARS, MAX_TOKENS)
    async with pg() as db:
        assert (await db.execute(select(func.count()).select_from(AiBudgetReservation))).scalar_one() == 0


@pytest.mark.pg
async def test_without_a_cap_nothing_is_counted(pg, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_monthly_hard_usd", Decimal(0))
    assert await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS) is None
    async with pg() as db:
        assert (await db.execute(select(func.count()).select_from(AiBudgetPeriod))).scalar_one() == 0


@pytest.mark.pg
async def test_exhausted_cap_makes_no_provider_call(pg, cap, monkeypatch):
    calls = []

    async def provider(*args, **kwargs):
        calls.append(1)
        return {"ok": True}, TokenUsage(prompt_tokens=10, completion_tokens=10)

    service = _llm(monkeypatch, provider)
    for _ in range(3):
        await ai_budget.reserve(MODEL, "test", CHARS, MAX_TOKENS)
    with pytest.raises(ai_budget.AiBudgetExhausted):
        await _call(service)
    assert calls == []


@pytest.mark.pg
async def test_llm_outcomes_map_to_budget_buckets(pg, cap, monkeypatch):
    async def ok(*args, **kwargs):
        return {"ok": True}, TokenUsage(prompt_tokens=100, completion_tokens=50)

    async def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("slow")

    async def rejected(*args, **kwargs):
        error = RuntimeError("bad request")
        error.status_code = 400
        raise error

    async def unusable(*args, **kwargs):
        error = ValueError("not json")
        error.llm_usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        raise error

    await _call(_llm(monkeypatch, ok))
    spent = (await _period(pg)).spent_usd
    assert spent > 0

    with pytest.raises(httpx.ReadTimeout):
        await _call(_llm(monkeypatch, timeout))
    row = await _period(pg)
    assert row.unresolved_usd == _estimate() and row.spent_usd == spent

    with pytest.raises(RuntimeError):
        await _call(_llm(monkeypatch, rejected))
    row = await _period(pg)
    assert row.unresolved_usd == _estimate() and row.reserved_usd == 0

    with pytest.raises(ValueError):
        await _call(_llm(monkeypatch, unusable))
    assert (await _period(pg)).spent_usd == spent * 2


@pytest.mark.pg
async def test_provider_out_of_credit_is_reported_as_budget_stop(pg, cap, monkeypatch):
    async def broke(*args, **kwargs):
        error = RuntimeError("quota")
        error.status_code = 429
        error.code = "insufficient_quota"
        raise error

    with pytest.raises(ai_budget.AiBudgetExhausted) as raised:
        await _call(_llm(monkeypatch, broke))
    assert raised.value.provider_side
    assert (await _period(pg)).reserved_usd == 0


def test_budget_stop_parks_the_card_without_spending_a_retry():
    card = SimpleNamespace(
        id="c1",
        lemma_l2="casa",
        enrichment_status="preparing",
        enrichment_error=None,
        enrichment_retry_at=datetime.now(UTC),
        enrichment_retry_count=0,
        enrichment_auto_retry_used=False,
        enrichment_manual_triggered=True,
        enrichment_side_retries=0,
    )
    _apply_enrich_retry(card, ai_budget.AiBudgetExhausted())
    assert card.enrichment_status == "preparing"
    assert card.enrichment_error == WAITING_BUDGET
    assert card.enrichment_retry_at is None
    assert card.enrichment_auto_retry_used is False
    assert card.enrichment_manual_triggered is True
    assert card.enrichment_retry_count == 0


@pytest.mark.pg
async def test_api_reports_a_budget_stop_as_503(pg_client):
    from app.main import create_app

    app = create_app()

    @app.get("/_budget_probe")
    async def probe():
        raise ai_budget.AiBudgetUnavailable()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_budget_probe")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ai_budget_exhausted"

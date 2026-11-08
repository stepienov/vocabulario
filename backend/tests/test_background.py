import asyncio
import time
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import AppLog, LlmCallPayload, LlmUsage
from app.services import background
from app.services.app_log import clear_request_context, log_event, request_id_var
from app.services.background import drain_background, spawn_background
from app.services.llm import LLMService
from app.services.llm_pricing import TokenUsage
from app.services.llm_usage import record_llm_usage
from tests.pg_factories import auth_headers, create_user


@pytest.fixture(autouse=True)
async def _cancel_background_tasks():
    yield
    for task in list(background._tasks):
        task.cancel()
    if background._tasks:
        await asyncio.wait(list(background._tasks), timeout=1)
    background._skipped = 0


async def test_spawn_stops_at_1000_and_counts_the_skip():
    hold = asyncio.Event()

    async def wait() -> None:
        await hold.wait()

    missing = 1000 - len(background._tasks)
    for _ in range(missing):
        spawn_background(wait, name="fill")
    assert len(background._tasks) == 1000
    background._skipped = 0
    spawn_background(wait, name="overflow")
    assert background._skipped == 1
    assert len(background._tasks) == 1000


async def test_task_exception_does_not_escape():
    async def boom() -> None:
        raise RuntimeError("background boom")

    spawn_background(boom, name="boom")
    await drain_background(1)


async def test_drain_waits_for_short_task_and_returns_on_timeout():
    async def nap() -> None:
        await asyncio.sleep(0.1)

    started = time.perf_counter()
    spawn_background(nap, name="nap")
    await drain_background(1)
    elapsed = time.perf_counter() - started
    assert elapsed >= 0.1
    assert elapsed < 1

    async def long_sleep() -> None:
        await asyncio.sleep(10)

    started = time.perf_counter()
    spawn_background(long_sleep, name="long")
    await drain_background(1)
    assert time.perf_counter() - started < 2


async def test_spawn_keeps_request_id_after_context_is_cleared():
    seen: dict[str, object] = {}

    async def capture() -> None:
        seen["request_id"] = request_id_var.get()

    request_id = uuid4()
    request_id_var.set(request_id)
    spawn_background(capture, name="ctx")
    clear_request_context()
    await drain_background(1)
    assert seen["request_id"] == request_id


async def test_reasoning_effort_is_sent_only_for_reasoning_models(monkeypatch):
    monkeypatch.setattr("app.services.llm.schedule_llm_meter", lambda *args, **kwargs: None)
    captured: list[dict] = []

    class Completions:
        async def create(self, **kwargs):
            captured.append(kwargs)

            class Message:
                content = "{}"

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]
                usage = None
                id = None

            return Response()

    service = LLMService()
    service.mock = False
    service.client = type("Client", (), {})()
    service.client.chat = type("Chat", (), {"completions": Completions()})()

    await service._chat_json("gpt-5.6-terra", "{}", reasoning_effort="none")
    await service._chat_json("gpt-5.6-terra", "{}")
    await service._chat_json("gpt-4o-mini", "{}", reasoning_effort="none")

    assert captured[0]["reasoning_effort"] == "none"
    assert "reasoning_effort" not in captured[1]
    assert "reasoning_effort" not in captured[2]


@pytest.mark.pg
async def test_http_response_returns_before_the_log_write(pg, pg_client, monkeypatch):
    release = asyncio.Event()

    async def blocked(**kwargs):
        await release.wait()
        await log_event(**kwargs)

    monkeypatch.setattr("app.core.app_log_middleware.log_event", blocked)
    async with pg() as session:
        user = await create_user(session, email="bg-me@test.com")
        await session.commit()
        headers = auth_headers(user)
    health = await pg_client.get("/health")
    me = await pg_client.get("/api/v1/me", headers=headers)
    assert health.status_code == 200
    assert me.status_code == 200
    release.set()
    await drain_background(1)
    async with pg() as session:
        row = (
            await session.execute(select(AppLog).where(AppLog.http_path == "/api/v1/me"))
        ).scalar_one()
    assert row.event == "http_request"
    assert row.http_status == 200


@pytest.mark.pg
async def test_record_llm_usage_writes_metric_and_payload_in_one_transaction(pg):
    usage_id = await record_llm_usage(
        provider="mock",
        model="gpt-5.6-terra",
        purpose="lookup_draft",
        usage=TokenUsage(prompt_tokens=3, completion_tokens=4),
        request_json={"purpose": "lookup_draft"},
        response_json={"ok": True},
    )
    assert usage_id is not None
    async with pg() as session:
        usage = await session.get(LlmUsage, usage_id)
        payload = await session.get(LlmCallPayload, usage_id)
    assert usage is not None
    assert payload is not None
    assert payload.request_json["purpose"] == "lookup_draft"
    gap_ms = abs((payload.created_at - usage.created_at).total_seconds() * 1000)
    assert gap_ms < 10


@pytest.mark.pg
async def test_record_llm_usage_keeps_metric_when_payload_constructor_fails(pg, monkeypatch):
    class BadPayload:
        def __init__(self, **kwargs):
            raise RuntimeError("bad payload field")

    monkeypatch.setattr("app.models.LlmCallPayload", BadPayload)
    usage_id = await record_llm_usage(
        provider="mock",
        model="gpt-5.6-terra",
        purpose="lookup_draft",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
        request_json={"purpose": "lookup_draft"},
        response_json={"ok": True},
    )
    assert usage_id is not None
    async with pg() as session:
        usage = await session.get(LlmUsage, usage_id)
        payload = await session.get(LlmCallPayload, usage_id)
    assert usage is not None
    assert payload is None

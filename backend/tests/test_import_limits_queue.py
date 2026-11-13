"""Task 11: limity pozycji, daily, bez verify w analizie (atrapy)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.import_jobs import (
    DAILY_IMPORT_LIMIT,
    MAX_IMPORT_ITEMS,
    ImportDailyLimitError,
    ImportTooManyError,
    _position_count,
)


def test_position_count_plain_notes():
    assert _position_count(kind="plain", notes=[["a"], ["b"]], raw_text=None) == 2


def test_position_count_raw_text_blank_lines():
    raw = "casa\n\nperro\n  \ngato\n"
    assert _position_count(kind="raw_text", notes=[], raw_text=raw) == 3


def test_limits_constants():
    assert MAX_IMPORT_ITEMS == 25
    assert DAILY_IMPORT_LIMIT == 25


@pytest.mark.asyncio
async def test_analyze_import_classify_params(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.services.llm import LLMService

    svc = LLMService()
    svc.mock = False
    svc.lookup_model = "gpt-5.6-terra"
    svc.client = MagicMock()
    captured: list[dict] = []

    async def fake_create(**kwargs):
        captured.append(kwargs)
        content = '{"items":[]}'
        msg = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=None)

    svc.client.chat.completions.create = AsyncMock(side_effect=fake_create)
    await svc.analyze_import_classify(native="pl", learning="es", notes=[["casa"]])
    assert len(captured) == 1
    assert captured[0]["model"] == "gpt-5.6-terra"
    assert captured[0]["reasoning_effort"] == "none"
    assert captured[0]["max_completion_tokens"] == 2500
    assert "temperature" not in captured[0]


def test_import_errors_carry_codes():
    assert str(ImportTooManyError(26)) == "import_too_many"
    assert str(ImportDailyLimitError(25)) == "import_daily_limit"
    assert str(ImportDailyLimitError(20, remaining=5)) == "import_quota_exceeded"
    assert ImportDailyLimitError(20, remaining=5).remaining == 5
    assert ImportTooManyError(26).count == 26

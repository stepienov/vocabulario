"""LLM token parsing, USD estimates, and best-effort usage persistence."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from decimal import Decimal

from app.services.llm_pricing import TokenUsage, estimate_cost_usd, parse_anthropic_usage, parse_openai_usage
from app.services.llm_usage import (
    bind_llm_usage_context,
    clear_llm_usage_context,
    current_llm_usage_context,
    record_llm_usage,
)


def test_parse_openai_usage_reads_cache_and_reasoning():
    response = SimpleNamespace(
        id="chatcmpl-abc",
        usage=SimpleNamespace(
            prompt_tokens=2006,
            completion_tokens=300,
            total_tokens=2306,
            prompt_tokens_details=SimpleNamespace(cached_tokens=1920, cache_write_tokens=40),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=12),
        ),
    )
    usage = parse_openai_usage(response)
    assert usage.prompt_tokens == 2006
    assert usage.completion_tokens == 300
    assert usage.total_tokens == 2306
    assert usage.cached_tokens == 1920
    assert usage.cache_write_tokens == 40
    assert usage.reasoning_tokens == 12
    assert usage.provider_response_id == "chatcmpl-abc"


def test_parse_anthropic_usage_maps_cache_fields():
    response = SimpleNamespace(
        id="msg_123",
        usage=SimpleNamespace(
            input_tokens=800,
            output_tokens=120,
            cache_read_input_tokens=500,
            cache_creation_input_tokens=200,
        ),
    )
    usage = parse_anthropic_usage(response)
    assert usage.prompt_tokens == 800
    assert usage.completion_tokens == 120
    assert usage.cached_tokens == 500
    assert usage.cache_write_tokens == 200
    assert usage.provider_response_id == "msg_123"


def test_estimate_cost_uncached_terra():
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    cost = estimate_cost_usd("gpt-5.6-terra", usage)
    assert cost is not None
    # 1000 * $2 / 1M + 500 * $12 / 1M = 0.008
    assert cost == Decimal("0.00800000")


def test_estimate_cost_cache_hit_luna():
    usage = TokenUsage(
        prompt_tokens=2000,
        completion_tokens=300,
        cached_tokens=1920,
        cache_write_tokens=0,
    )
    cost = estimate_cost_usd("gpt-5.6-luna", usage)
    assert cost is not None
    # uncached 80 * 0.20 + cached 1920 * 0.02 + completion 300 * 1.20  / 1M
    assert cost == Decimal("0.00041440")


def test_estimate_cost_cache_write_terra():
    usage = TokenUsage(
        prompt_tokens=2000,
        completion_tokens=100,
        cached_tokens=0,
        cache_write_tokens=1900,
    )
    cost = estimate_cost_usd("gpt-5.6-terra", usage)
    assert cost is not None
    # write 1900 * 2.50 + uncached 100 * 2 + completion 100 * 12  / 1M = 0.00615
    assert cost == Decimal("0.00615000")


def test_estimate_cost_unknown_model_is_null():
    usage = TokenUsage(prompt_tokens=10, completion_tokens=10)
    assert estimate_cost_usd("mystery-model", usage) is None


def test_bind_keeps_parent_operation_id():
    clear_llm_usage_context()
    parent = uuid4()
    bind_llm_usage_context(
        overwrite_operation=True,
        operation_id=parent,
        operation_kind="lemma_enrich",
        lemma="hablar",
    )
    bind_llm_usage_context(
        operation_id=uuid4(),
        operation_kind="lookup",
        query="hablar",
    )
    ctx = current_llm_usage_context()
    assert ctx.operation_id == parent
    assert ctx.operation_kind == "lemma_enrich"
    assert ctx.query == "hablar"
    assert ctx.lemma == "hablar"
    clear_llm_usage_context()


def test_record_llm_usage_does_not_raise_on_db_error():
    async def _run() -> None:
        with patch("app.models.LlmUsage", side_effect=RuntimeError("db down")):
            await record_llm_usage(
                provider="openai",
                model="gpt-5.6-terra",
                purpose="lookup_expand",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
            )

    asyncio.run(_run())

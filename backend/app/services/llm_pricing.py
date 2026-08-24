"""Token usage parsing + USD estimates from a local price table.

OpenAI Chat Completions returns token counts, not dollars. Cache reads and
cache writes are billed at different input rates (GPT-5.6+).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

logger = logging.getLogger(__name__)

PRICING_VERSION = "2026-07-30"
_MILLION = Decimal("1000000")
_COST_QUANT = Decimal("0.00000001")

# USD per 1M tokens, short context. Source: https://developers.openai.com/api/docs/pricing
# (input, cached_input, cache_write, output)
_MODEL_RATES_USD_PER_M: dict[str, tuple[Decimal, Decimal, Decimal, Decimal]] = {
    "gpt-5.6-terra": (
        Decimal("2.00"),
        Decimal("0.20"),
        Decimal("2.50"),
        Decimal("12.00"),
    ),
    "gpt-5.6-luna": (
        Decimal("0.20"),
        Decimal("0.02"),
        Decimal("0.25"),
        Decimal("1.20"),
    ),
    "gpt-5.6-sol": (
        Decimal("4.00"),
        Decimal("0.40"),
        Decimal("5.00"),
        Decimal("20.00"),
    ),
}


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    provider_response_id: str | None = None


def _int_field(obj: Any, *names: str) -> int:
    for name in names:
        if obj is None:
            return 0
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def _nested(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def parse_openai_usage(response: Any) -> TokenUsage:
    usage = _nested(response, "usage")
    prompt_details = _nested(usage, "prompt_tokens_details")
    completion_details = _nested(usage, "completion_tokens_details")
    prompt = _int_field(usage, "prompt_tokens", "input_tokens")
    completion = _int_field(usage, "completion_tokens", "output_tokens")
    total = _int_field(usage, "total_tokens") or (prompt + completion)
    cached = _int_field(prompt_details, "cached_tokens")
    cache_write = _int_field(prompt_details, "cache_write_tokens")
    reasoning = _int_field(completion_details, "reasoning_tokens")
    response_id = _nested(response, "id")
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        cached_tokens=cached,
        cache_write_tokens=cache_write,
        reasoning_tokens=reasoning,
        provider_response_id=str(response_id) if response_id else None,
    )


def parse_anthropic_usage(response: Any) -> TokenUsage:
    usage = _nested(response, "usage")
    prompt = _int_field(usage, "input_tokens")
    completion = _int_field(usage, "output_tokens")
    cached = _int_field(usage, "cache_read_input_tokens")
    cache_write = _int_field(usage, "cache_creation_input_tokens")
    response_id = _nested(response, "id")
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        cached_tokens=cached,
        cache_write_tokens=cache_write,
        provider_response_id=str(response_id) if response_id else None,
    )


def _rates_for_model(model: str) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    key = (model or "").strip().lower()
    return _MODEL_RATES_USD_PER_M.get(key)


def estimate_cost_usd(model: str, usage: TokenUsage) -> Decimal | None:
    rates = _rates_for_model(model)
    if rates is None:
        logger.warning("llm_pricing: unknown model %r — estimated_cost_usd left null", model)
        return None
    input_rate, cached_rate, cache_write_rate, output_rate = rates
    cached = max(0, usage.cached_tokens)
    cache_write = max(0, usage.cache_write_tokens)
    prompt = max(0, usage.prompt_tokens)
    completion = max(0, usage.completion_tokens)
    uncached = max(0, prompt - cached - cache_write)
    cost = (
        (Decimal(cached) * cached_rate)
        + (Decimal(cache_write) * cache_write_rate)
        + (Decimal(uncached) * input_rate)
        + (Decimal(completion) * output_rate)
    ) / _MILLION
    return cost.quantize(_COST_QUANT, rounding=ROUND_HALF_UP)

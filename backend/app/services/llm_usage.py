"""Best-effort LLM metering — never raises into lookup/enrichment."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID, uuid4

from app.services.app_log import profile_id_var, request_id_var, user_id_var
from app.services.llm_pricing import PRICING_VERSION, TokenUsage, estimate_cost_usd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmUsageContext:
    operation_id: UUID | None = None
    operation_kind: str | None = None
    query: str | None = None
    lemma: str | None = None
    pos: str | None = None
    lang_pair: str | None = None
    card_id: UUID | None = None
    user_id: UUID | None = None
    profile_id: UUID | None = None


_usage_ctx: ContextVar[LlmUsageContext] = ContextVar(
    "llm_usage_ctx", default=LlmUsageContext()
)


def current_llm_usage_context() -> LlmUsageContext:
    return _usage_ctx.get()


def bind_llm_usage_context(
    *,
    overwrite_operation: bool = False,
    **kwargs: Any,
) -> None:
    """Merge metering fields into the current task context.

    Existing operation_id / operation_kind are kept unless overwrite_operation
    is set, so a nested lookup inside enrichment stays on the parent operation.
    """
    current = _usage_ctx.get()
    data = asdict(current)
    keep_op = bool(data.get("operation_id")) and not overwrite_operation
    for key, value in kwargs.items():
        if value is None:
            continue
        if keep_op and key in {"operation_id", "operation_kind"}:
            continue
        data[key] = value
    _usage_ctx.set(LlmUsageContext(**data))


def clear_llm_usage_context() -> None:
    _usage_ctx.set(LlmUsageContext())


def _as_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _clip(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    return value if len(value) <= limit else value[: limit - 1] + "…"


async def record_llm_usage(
    *,
    provider: str,
    model: str,
    purpose: str,
    status: str = "ok",
    duration_ms: int | None = None,
    usage: TokenUsage | None = None,
) -> None:
    try:
        from app.db.session import async_session_factory
        from app.models import LlmUsage

        ctx = _usage_ctx.get()
        usage = usage or TokenUsage()
        cost = estimate_cost_usd(model, usage) if status == "ok" else None
        row = LlmUsage(
            id=uuid4(),
            provider=(provider or "openai")[:16],
            model=(model or "")[:64],
            purpose=(purpose or "chat_json")[:32],
            operation_id=ctx.operation_id,
            operation_kind=_clip(ctx.operation_kind, 32),
            query=_clip(ctx.query, 200),
            lemma=_clip(ctx.lemma, 255),
            pos=_clip(ctx.pos, 32),
            lang_pair=_clip(ctx.lang_pair, 16),
            card_id=_as_uuid(ctx.card_id),
            user_id=_as_uuid(ctx.user_id) or user_id_var.get(),
            profile_id=_as_uuid(ctx.profile_id) or profile_id_var.get(),
            request_id=request_id_var.get(),
            openai_response_id=_clip(usage.provider_response_id, 64),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cached_tokens=usage.cached_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            estimated_cost_usd=cost,
            pricing_version=PRICING_VERSION if cost is not None else None,
            duration_ms=duration_ms,
            status=(status or "ok")[:16],
        )
        async with async_session_factory() as db:
            db.add(row)
            await db.commit()
    except Exception:
        logger.exception("llm_usage write failed purpose=%s model=%s", purpose, model)

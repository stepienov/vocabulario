"""Best-effort LLM metering — never raises into lookup/enrichment."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, update

from app.core.config import get_settings
from app.services.app_log import profile_id_var, request_id_var, user_id_var
from app.services.llm_pricing import PRICING_VERSION, TokenUsage, estimate_cost_usd

logger = logging.getLogger(__name__)

_PROMPT_CLIP = 100_000
_PURGE_EVERY_S = 1800
_last_payload_purge_at = 0.0


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
    lookup_event_id: UUID | None = None


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
        if key in {"card_id", "user_id", "profile_id", "lookup_event_id", "operation_id"}:
            data[key] = _as_uuid(value) or value
        else:
            data[key] = value
    _usage_ctx.set(LlmUsageContext(**data))


def clear_llm_usage_context() -> None:
    _usage_ctx.set(LlmUsageContext())


def schedule_llm_meter(
    usage_kwargs: dict[str, Any],
    log_kwargs: dict[str, Any] | None = None,
) -> None:
    from app.services.background import spawn_background

    async def _write() -> None:
        if log_kwargs is not None:
            from app.services.app_log import log_event

            await log_event(**log_kwargs)
        await record_llm_usage(**usage_kwargs)

    spawn_background(_write, name="llm_usage")


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


def build_llm_request_json(
    *,
    purpose: str,
    model: str,
    schema_name: str | None,
    prompt: str,
    prompt_dynamic: str | None = None,
    cache_key: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    dynamic = prompt_dynamic if prompt_dynamic is not None else prompt
    payload = {
        "purpose": purpose,
        "model": model,
        "schema": schema_name,
        "prompt_dynamic": _clip(dynamic, _PROMPT_CLIP),
        "cache_key": cache_key,
    }
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    return payload


def payload_cutoff(*, now: datetime | None = None, days: int | None = None) -> datetime:
    settings = get_settings()
    ttl = max(1, int(days if days is not None else settings.llm_payload_ttl_days))
    return (now or datetime.now(UTC)) - timedelta(days=ttl)


async def record_llm_usage(
    *,
    provider: str,
    model: str,
    purpose: str,
    status: str = "ok",
    duration_ms: int | None = None,
    usage: TokenUsage | None = None,
    request_json: dict | None = None,
    response_json: dict | list | None = None,
) -> UUID | None:
    try:
        from app.db.session import async_session_factory
        from app.models import LlmUsage

        ctx = _usage_ctx.get()
        usage = usage or TokenUsage()
        cost = estimate_cost_usd(model, usage) if status == "ok" else None
        row_id = uuid4()
        row = LlmUsage(
            id=row_id,
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
            lookup_event_id=_as_uuid(ctx.lookup_event_id),
        )
        settings = get_settings()
        store = bool(settings.llm_store_payloads) and (
            request_json is not None or response_json is not None
        )
        from app.models import LlmCallPayload

        # Flush the parent before the child. A combined flush can insert the
        # payload first, trip llm_call_payloads_llm_usage_id_fkey, and drop
        # the metric. A payload error rolls back only its savepoint.
        async with async_session_factory() as db:
            db.add(row)
            await db.flush()
            if store:
                try:
                    async with db.begin_nested():
                        db.add(
                            LlmCallPayload(
                                llm_usage_id=row_id,
                                request_json=request_json,
                                response_json=response_json
                                if isinstance(response_json, (dict, list))
                                else None,
                            )
                        )
                except Exception:
                    logger.exception(
                        "llm payload write failed id=%s purpose=%s model=%s",
                        row_id,
                        purpose,
                        model,
                    )
            await db.commit()
    except Exception:
        logger.exception("llm_usage write failed purpose=%s model=%s", purpose, model)
        return None
    return row_id


async def purge_expired_llm_payloads(*, force: bool = False) -> dict[str, int]:
    """Drop raw JSON older than TTL. Keeps llm_usage metric rows."""
    global _last_payload_purge_at
    import time

    now = time.monotonic()
    if not force and _last_payload_purge_at and now - _last_payload_purge_at < _PURGE_EVERY_S:
        return {"payloads": 0, "lookup_candidates_cleared": 0, "skipped": 1}
    try:
        from app.db.session import async_session_factory
        from app.models import LlmCallPayload, LookupEvent

        cutoff = payload_cutoff()
        async with async_session_factory() as db:
            payloads = await db.execute(
                delete(LlmCallPayload).where(LlmCallPayload.created_at < cutoff)
            )
            lookups = await db.execute(
                update(LookupEvent)
                .where(LookupEvent.created_at < cutoff)
                .values(candidates=[])
            )
            await db.commit()
        _last_payload_purge_at = now
        return {
            "payloads": int(payloads.rowcount or 0),
            "lookup_candidates_cleared": int(lookups.rowcount or 0),
            "skipped": 0,
        }
    except Exception:
        logger.exception("llm payload purge failed")
        return {"payloads": 0, "lookup_candidates_cleared": 0, "skipped": 0}

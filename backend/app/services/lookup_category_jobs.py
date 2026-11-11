"""Ósemki skojarzeń poza cyklem HTTP. Każda runda ma własne zadanie."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.db.session import async_session_factory
from app.services.lexical import LookupOutcome
from app.services.lookup_candidates import normalize_lookup_query
from app.services.lookup_events import record_lookup_event

logger = logging.getLogger(__name__)

_inflight: dict[tuple[str, str, str, int], asyncio.Task[LookupOutcome]] = {}


def _key(user_id: UUID, profile_id: UUID, text: str, round: int) -> tuple[str, str, str, int]:
    norm = normalize_lookup_query(text) or (text.strip().casefold()[:200] or "_")
    return (str(user_id), str(profile_id), "assoc:" + norm[:190], round)


def ensure_expand_task(
    user_id: UUID,
    profile_id: UUID,
    text: str,
    round: int,
) -> asyncio.Task[LookupOutcome]:
    key = _key(user_id, profile_id, text, round)
    existing = _inflight.get(key)
    if existing is not None and not existing.done():
        return existing
    task = asyncio.create_task(
        _run_expand(user_id, profile_id, text, round),
        name=f"lookup-assoc:{key[2][:40]}:{round}",
    )
    _inflight[key] = task

    def _done(_done_task: asyncio.Task) -> None:
        current = _inflight.get(key)
        if current is _done_task:
            _inflight.pop(key, None)

    task.add_done_callback(_done)
    return task


async def await_lookup_category_expand(
    user_id: UUID,
    profile_id: UUID,
    text: str,
    round: int,
) -> LookupOutcome:
    task = ensure_expand_task(user_id, profile_id, text, round)
    return await asyncio.shield(task)


async def _run_expand(
    user_id: UUID, profile_id: UUID, text: str, round: int
) -> LookupOutcome:
    from app.services.lexical import LexicalService

    async with async_session_factory() as db:
        service = LexicalService(db)
        outcome = await service.lookup_assoc_round(user_id, profile_id, text, round)
        if outcome.persist or outcome.source == "ai":
            await record_lookup_event(
                db,
                user_id=user_id,
                profile_id=profile_id,
                query=text,
                source=outcome.source or "category",
                candidate_count=len(outcome.candidates),
                candidates=outcome.candidates,
                ai_complete=outcome.ai_complete,
            )
            await db.commit()
        return outcome

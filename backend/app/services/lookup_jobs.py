"""Lookup expand poza cyklem żądania HTTP.

Klient może zminimalizować / zabić apkę w trakcie LLM — TCP się zrywa,
Starlette anuluje handler. Sam expand musi dokończyć zapis do
`lookup_query_cache`, żeby po powrocie `lookup/cached` oddał wynik.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.db import session as db_session
from app.services.lexical import LookupOutcome
from app.services.lookup_candidates import normalize_lookup_query
from app.services.lookup_events import record_lookup_event

logger = logging.getLogger(__name__)

_inflight: dict[tuple[str, str, str, bool, UUID | None], asyncio.Task[LookupOutcome]] = {}


def _key(
    user_id: UUID, profile_id: UUID, text: str, more: bool, operation_id: UUID | None
) -> tuple[str, str, str, bool, UUID | None]:
    norm = normalize_lookup_query(text) or (text.strip().casefold()[:200] or "_")
    return (str(user_id), str(profile_id), norm, more, operation_id if more else None)


def ensure_expand_task(
    user_id: UUID,
    profile_id: UUID,
    text: str,
    *,
    more: bool = False,
    operation_id: UUID | None = None,
) -> asyncio.Task[LookupOutcome]:
    key = _key(user_id, profile_id, text, more, operation_id)
    existing = _inflight.get(key)
    if existing is not None and not existing.done():
        return existing
    task = asyncio.create_task(
        _run_expand(user_id, profile_id, text, more=more, operation_id=operation_id),
        name=f"lookup-expand:{key[2][:40]}",
    )
    _inflight[key] = task

    def _done(_done_task: asyncio.Task) -> None:
        current = _inflight.get(key)
        if current is _done_task:
            _inflight.pop(key, None)

    task.add_done_callback(_done)
    return task


async def await_lookup_expand(
    user_id: UUID,
    profile_id: UUID,
    text: str,
    *,
    more: bool = False,
    operation_id: UUID | None = None,
) -> LookupOutcome:
    """Czekaj na wynik, ale nie anuluj workera gdy klient się rozłączy."""
    task = ensure_expand_task(
        user_id, profile_id, text, more=more, operation_id=operation_id
    )
    return await asyncio.shield(task)


async def _run_expand(
    user_id: UUID, profile_id: UUID, text: str, *, more: bool = False,
    operation_id: UUID | None = None,
) -> LookupOutcome:
    from app.services.lexical import LexicalService

    async with db_session.async_session_factory() as db:
        service = LexicalService(db)
        outcome = await service.lookup_expand(
            user_id, profile_id, text, more=more, operation_id=operation_id
        )
        await record_lookup_event(
            db,
            user_id=user_id,
            profile_id=profile_id,
            query=text,
            source=outcome.source or "expand",
            candidate_count=len(outcome.candidates),
            candidates=outcome.candidates,
            ai_complete=outcome.ai_complete,
        )
        await db.commit()
        return outcome

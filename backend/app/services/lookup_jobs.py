"""Lookup expand poza cyklem żądania HTTP.

Klient może zminimalizować / zabić apkę w trakcie LLM — TCP się zrywa,
Starlette anuluje handler. Sam expand musi dokończyć zapis do
`lookup_query_cache`, żeby po powrocie `lookup/cached` oddał wynik.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.db.session import async_session_factory
from app.models import User
from app.services.lexical import LookupOutcome
from app.services.lookup_candidates import normalize_lookup_query
from app.services.lookup_events import record_lookup_event

logger = logging.getLogger(__name__)

_inflight: dict[tuple[str, str, str], asyncio.Task[LookupOutcome]] = {}


def _key(user_id: UUID, profile_id: UUID, text: str) -> tuple[str, str, str]:
    norm = normalize_lookup_query(text) or (text.strip().casefold()[:200] or "_")
    return (str(user_id), str(profile_id), norm)


def ensure_expand_task(
    user_id: UUID,
    profile_id: UUID,
    text: str,
) -> asyncio.Task[LookupOutcome]:
    key = _key(user_id, profile_id, text)
    existing = _inflight.get(key)
    if existing is not None and not existing.done():
        return existing
    task = asyncio.create_task(
        _run_expand(user_id, profile_id, text),
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
) -> LookupOutcome:
    """Czekaj na wynik, ale nie anuluj workera gdy klient się rozłączy."""
    task = ensure_expand_task(user_id, profile_id, text)
    return await asyncio.shield(task)


async def _run_expand(user_id: UUID, profile_id: UUID, text: str) -> LookupOutcome:
    from app.services.lexical import LexicalService

    async with async_session_factory() as db:
        user = await db.get(User, user_id)
        if user is None:
            raise ValueError("user not found")
        service = LexicalService(db)
        outcome = await service.lookup_expand(user, profile_id, text)
        await record_lookup_event(
            db,
            user_id=user.id,
            profile_id=profile_id,
            query=text,
            source=outcome.source or "expand",
            candidate_count=len(outcome.candidates),
            candidates=outcome.candidates,
            ai_complete=outcome.ai_complete,
        )
        await db.commit()
        return outcome

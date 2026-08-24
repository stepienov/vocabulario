"""Best-effort zapis historii wyszukiwań — nie psuje lookupu."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import lang_pair_key, normalize_text
from app.models import LanguageProfile, LookupEvent

logger = logging.getLogger(__name__)


async def record_lookup_event(
    db: AsyncSession,
    *,
    user_id: UUID,
    profile_id: UUID,
    query: str,
    source: str,
    candidate_count: int,
    http_status: int = 200,
) -> None:
    try:
        profile = (
            await db.execute(
                select(LanguageProfile).where(
                    LanguageProfile.id == profile_id,
                    LanguageProfile.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        pair = None
        if profile is not None:
            pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        raw = (query or "").strip()[:200]
        row = LookupEvent(
            id=uuid4(),
            user_id=user_id,
            profile_id=profile_id,
            query=raw,
            query_norm=normalize_text(raw)[:200] or raw,
            lang_pair=pair,
            source=(source or "lookup")[:16],
            candidate_count=max(0, int(candidate_count or 0)),
            http_status=http_status,
        )
        db.add(row)
        await db.flush()
    except Exception:
        logger.exception("lookup_event write failed user=%s query=%r", user_id, query)

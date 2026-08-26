"""Best-effort zapis historii wyszukiwań — nie psuje lookupu."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import lang_pair_key, normalize_text
from app.core.lemma_keys import canonical_lemma
from app.models import LanguageProfile, LookupEvent
from app.services.app_log import request_id_var
from app.services.pos_normalize import normalize_pos_bucket

logger = logging.getLogger(__name__)

LOOKUP_STITCH_WINDOW = timedelta(minutes=15)
_CANDIDATE_KEYS = (
    "lemma",
    "pos",
    "gloss",
    "lexical_entry_id",
    "in_learning",
    "learning_card_id",
    "enrichment_status",
)


def slim_lookup_candidates(candidates: list | None) -> list[dict]:
    out: list[dict] = []
    for item in candidates or []:
        if not isinstance(item, dict) or not item.get("lemma"):
            continue
        row: dict = {}
        for key in _CANDIDATE_KEYS:
            if key not in item or item[key] is None:
                continue
            value = item[key]
            if isinstance(value, UUID):
                value = str(value)
            row[key] = value
        out.append(row)
    return out


def lookup_event_matches_lemma(event: LookupEvent, lemma: str, pos: str | None) -> bool:
    lemma_n = normalize_text(lemma)
    lemma_c = canonical_lemma(lemma)
    query = event.query or ""
    query_norm = event.query_norm or ""
    if normalize_text(query) == lemma_n or canonical_lemma(query) == lemma_c:
        return True
    if query_norm and (
        query_norm == lemma_n or canonical_lemma(query_norm) == lemma_c
    ):
        return True
    want = normalize_pos_bucket(pos)
    for raw in event.candidates or []:
        if not isinstance(raw, dict):
            continue
        cand = str(raw.get("lemma") or "")
        if not cand:
            continue
        if normalize_text(cand) != lemma_n and canonical_lemma(cand) != lemma_c:
            continue
        got = normalize_pos_bucket(raw.get("pos"))
        if want != "unknown" and got != "unknown" and want != got:
            continue
        return True
    return False


async def find_lookup_event_for_card(
    db: AsyncSession,
    *,
    user_id: UUID,
    profile_id: UUID,
    lemma: str,
    pos: str | None,
) -> LookupEvent | None:
    cutoff = datetime.now(UTC) - LOOKUP_STITCH_WINDOW
    rows = list(
        (
            await db.execute(
                select(LookupEvent)
                .where(
                    LookupEvent.user_id == user_id,
                    LookupEvent.profile_id == profile_id,
                    LookupEvent.created_at >= cutoff,
                )
                .order_by(LookupEvent.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
    )
    for event in rows:
        if lookup_event_matches_lemma(event, lemma, pos):
            return event
    return None


async def record_lookup_event(
    db: AsyncSession,
    *,
    user_id: UUID,
    profile_id: UUID,
    query: str,
    source: str,
    candidate_count: int,
    http_status: int = 200,
    candidates: list | None = None,
    ai_complete: bool = False,
) -> LookupEvent | None:
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
        slim = slim_lookup_candidates(candidates)
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
            request_id=request_id_var.get(),
            candidates=slim,
            ai_complete=bool(ai_complete),
        )
        db.add(row)
        await db.flush()
        return row
    except Exception:
        logger.exception("lookup_event write failed user=%s query=%r", user_id, query)
        return None

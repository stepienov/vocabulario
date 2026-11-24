"""Operator-published changes to authoritative lexical content."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.lemma_keys import canonical_lemma
from app.models import LanguageProfile, LearningCard, LexicalEntry, SrsState
from app.schemas import CardContent


def content_revision(content: dict) -> str:
    encoded = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def current_learning_generation(db: AsyncSession, card: LearningCard) -> int:
    if card.lexical_entry_id is None or card._content is not None:
        return 1
    entry = (
        await db.execute(
            select(LexicalEntry)
            .where(LexicalEntry.id == card.lexical_entry_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if entry is None:
        raise LookupError("shared_card_content_unavailable")
    card.lexical_entry = entry
    return entry.learning_generation


async def publish_lexical_content(
    db: AsyncSession,
    *,
    entry_id: UUID,
    expected_generation: int,
    expected_content_revision: str,
    content: dict,
    learning_impact: bool,
) -> tuple[LexicalEntry, int]:
    entry = (
        await db.execute(
            select(LexicalEntry)
            .where(LexicalEntry.id == entry_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if entry is None:
        raise LookupError("lexical_entry_not_found")
    cards = list(
        (
            await db.execute(
                select(LearningCard)
                .where(LearningCard.lexical_entry_id == entry_id)
                .order_by(LearningCard.id)
                .with_for_update()
            )
        ).scalars()
    )
    if entry.learning_generation != expected_generation:
        raise ValueError("content_generation_conflict")
    if content_revision(entry.content) != expected_content_revision:
        raise ValueError("content_revision_conflict")
    if not isinstance(content, dict):
        raise ValueError("content_must_be_object")
    if content == entry.content:
        if learning_impact:
            raise ValueError("unchanged_content_cannot_reset_learning")
        return entry, 0
    if any(card._content is not None for card in cards):
        raise ValueError("unmigrated_card_content")

    from app.services.card_jobs import (
        content_is_complete,
        resolve_enrichment_entry_kind,
        same_headword,
        same_pos_bucket,
    )

    try:
        parsed = CardContent.model_validate(content)
    except ValidationError as exc:
        raise ValueError("incomplete_shared_content") from exc
    app_lang, separator, learning_lang = entry.lang_pair.partition(">")
    if (
        not separator
        or parsed.language.lower() != learning_lang.lower()
        or not same_headword(parsed.lemma, entry.lemma_l2)
        or not same_pos_bucket(parsed.pos, entry.pos)
        or resolve_enrichment_entry_kind(content, pos=entry.pos)
        != resolve_enrichment_entry_kind(entry.content, pos=entry.pos)
    ):
        raise ValueError("content_identity_conflict")
    if not content_is_complete(content, learning_lang=learning_lang):
        raise ValueError("incomplete_shared_content")
    gloss = parsed.meanings[0].get("gloss_l1")
    if not isinstance(gloss, str) or not gloss.strip() or len(gloss) > 255:
        raise ValueError("incomplete_shared_content")
    if (content.get("word_family_l2") or []) != (entry.content.get("word_family_l2") or []):
        raise ValueError("family_edit_requires_reconciliation")

    old_lemma = entry.content.get("lemma") or entry.lemma_l2
    old_gloss = entry.lemma_l1_primary
    entry.content = content
    entry.lemma_l1_primary = gloss
    entry.lemma_key_l1 = canonical_lemma(gloss) or None
    if parsed.lemma != old_lemma:
        entry.lemma_l2 = parsed.lemma
        entry.lemma_key_l2 = canonical_lemma(parsed.lemma) or None
    for card in cards:
        card.gloss_primary = gloss
        if parsed.lemma != old_lemma:
            card.lemma_l2 = parsed.lemma
    if entry.word_family_id is not None and (parsed.lemma != old_lemma or gloss != old_gloss):
        from app.services.word_families import sync_word_family

        profile = LanguageProfile(app_lang=app_lang, learning_lang=learning_lang)
        entry.content = await sync_word_family(db, profile, dict(content), entry)
    reset_count = 0
    if learning_impact:
        entry.learning_generation += 1
        if cards:
            states = (
                await db.execute(
                    select(SrsState)
                    .where(
                        SrsState.card_id.in_([card.id for card in cards]),
                        SrsState.scope == "main",
                    )
                    .order_by(SrsState.card_id)
                    .with_for_update()
                )
            ).scalars().all()
            for state in states:
                state.status = "new"
                state.ease = 2.5
                state.interval_days = 0
                state.repetitions = 0
                state.lapses = 0
                state.next_review_at = None
                state.last_reviewed_at = None
                state.last_grade = None
                state.stability = None
                state.difficulty = None
                state.fsrs_step = None
            reset_count = len(states)

    await db.flush()
    return entry, reset_count


async def compact_exact_card_copies(
    db: AsyncSession, *, batch_size: int = 500
) -> tuple[int, int]:
    """Link only exact, unambiguous matches; retain every conflicting snapshot for review."""
    linked = 0
    cleared = 0
    while True:
        result = await db.execute(
            text(
                "WITH candidates AS ("
                " SELECT c.id, min(e.id::text)::uuid AS entry_id "
                " FROM learning_cards c "
                " JOIN language_profiles p ON p.id = c.profile_id "
                " JOIN lexical_entries e "
                "   ON e.lang_pair = p.app_lang || '>' || p.learning_lang "
                "  AND lower(e.lemma_l2) = lower(c.lemma_l2) "
                "  AND lower(COALESCE(e.pos, '')) = lower(COALESCE(c.pos, '')) "
                " WHERE c.lexical_entry_id IS NULL AND c.deleted_at IS NULL "
                "   AND c.enrichment_status = 'ready' AND c.content IS NOT NULL "
                " GROUP BY c.id HAVING count(*) = 1 AND bool_and(e.content = c.content) "
                " AND bool_and(e.learning_generation = 1) "
                " ORDER BY c.id LIMIT :n"
                ") "
                "UPDATE learning_cards c SET lexical_entry_id = x.entry_id, "
                "content = NULL, updated_at = NOW() FROM candidates x "
                "WHERE c.id = x.id AND c.lexical_entry_id IS NULL "
                "AND c.content = (SELECT e.content FROM lexical_entries e WHERE e.id = x.entry_id) "
                "RETURNING c.id"
            ),
            {"n": batch_size},
        )
        batch_linked = len(result.all())
        linked += batch_linked
        if batch_linked:
            await db.commit()

        result = await db.execute(
            text(
                "WITH candidates AS ("
                " SELECT c.id FROM learning_cards c "
                " JOIN language_profiles p ON p.id = c.profile_id "
                " JOIN lexical_entries e ON e.id = c.lexical_entry_id "
                " WHERE c.enrichment_status = 'ready' "
                "   AND c.content IS NOT NULL AND c.content = e.content "
                "   AND e.learning_generation = 1 "
                "   AND e.lang_pair = p.app_lang || '>' || p.learning_lang "
                "   AND lower(e.lemma_l2) = lower(c.lemma_l2) "
                "   AND lower(COALESCE(e.pos, '')) = lower(COALESCE(c.pos, '')) "
                "   AND NOT EXISTS (SELECT 1 FROM lexical_entries other "
                "     WHERE other.id <> e.id AND other.lang_pair = e.lang_pair "
                "       AND lower(other.lemma_l2) = lower(e.lemma_l2) "
                "       AND lower(COALESCE(other.pos, '')) = lower(COALESCE(e.pos, ''))) "
                " ORDER BY c.id LIMIT :n FOR UPDATE OF c, e SKIP LOCKED"
                ") "
                "UPDATE learning_cards c SET content = NULL, updated_at = NOW() "
                "FROM candidates x WHERE c.id = x.id RETURNING c.id"
            ),
            {"n": batch_size},
        )
        batch_cleared = len(result.all())
        cleared += batch_cleared
        if batch_cleared:
            await db.commit()
        if batch_linked == 0 and batch_cleared == 0:
            break
    return linked, cleared


async def shared_content_copy_counts(db: AsyncSession) -> dict[str, int]:
    row = (
        await db.execute(
            text(
                "SELECT "
                "count(*) FILTER (WHERE c.deleted_at IS NULL "
                "  AND c.lexical_entry_id IS NOT NULL AND c.content IS NOT NULL "
                "  AND c.content = e.content) AS linked_exact, "
                "count(*) FILTER (WHERE c.deleted_at IS NULL "
                "  AND c.lexical_entry_id IS NOT NULL AND c.content IS NOT NULL "
                "  AND c.content IS DISTINCT FROM e.content) AS linked_conflicting, "
                "count(*) FILTER (WHERE c.deleted_at IS NOT NULL "
                "  AND c.lexical_entry_id IS NOT NULL AND c.content IS NOT NULL "
                "  AND c.content = e.content) AS linked_exact_deleted, "
                "count(*) FILTER (WHERE c.deleted_at IS NOT NULL "
                "  AND c.lexical_entry_id IS NOT NULL AND c.content IS NOT NULL "
                "  AND c.content IS DISTINCT FROM e.content) AS linked_conflicting_deleted, "
                "count(*) FILTER (WHERE c.deleted_at IS NULL "
                "  AND c.lexical_entry_id IS NULL AND c.enrichment_status = 'ready' "
                "  AND c.content IS NOT NULL) AS unlinked_ready "
                "FROM learning_cards c "
                "LEFT JOIN lexical_entries e ON e.id = c.lexical_entry_id"
            )
        )
    ).one()
    return {
        "linked_exact": int(row.linked_exact or 0),
        "linked_conflicting": int(row.linked_conflicting or 0),
        "linked_exact_deleted": int(row.linked_exact_deleted or 0),
        "linked_conflicting_deleted": int(row.linked_conflicting_deleted or 0),
        "unlinked_ready": int(row.unlinked_ready or 0),
    }

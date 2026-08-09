"""Card correction reports, self-edit, history, and admin review queue."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models import (
    AdminCardReview,
    CardCorrection,
    CardHistoryEvent,
    LanguageProfile,
    LearningCard,
)
from app.services.llm import LLMService
from app.services.push import notify_correction_resolved

logger = logging.getLogger(__name__)

ALLOWED_SECTIONS = {
    "lemma",
    "pos",
    "gloss",
    "meanings",
    "examples",
    "conjugation",
    "similar",
    "pronunciation",
    "other",
}

CORRECTION_RESULT_CODES = {
    "correction_accepted",
    "correction_unfounded",
    "correction_insufficient_info",
    "correction_not_applicable",
    "correction_processing_failed",
}

CORRECTION_DAILY_LIMIT = 20

_PLACEHOLDER_RE = re.compile(
    r"^[\s\-—–.?…]+$|^(n/?a|none|brak|unknown|todo|tbd|xxx)$",
    re.IGNORECASE,
)

SELF_EDIT_VERDICT_CODES = {
    "self_edit_ok",
    "self_edit_questionable",
    "self_edit_invalid",
}


def _validate_sections(sections: list[str]) -> list[str]:
    cleaned = [s.strip().lower() for s in sections if s and s.strip()]
    invalid = [s for s in cleaned if s not in ALLOWED_SECTIONS]
    if invalid:
        raise ValueError(f"Invalid sections: {', '.join(invalid)}")
    return cleaned


def _card_snapshot(card: LearningCard) -> dict:
    return {
        "lemma_l2": card.lemma_l2,
        "pos": card.pos,
        "gloss_primary": card.gloss_primary,
        "content": dict(card.content or {}),
        "lexical_entry_id": str(card.lexical_entry_id) if card.lexical_entry_id else None,
    }


def _apply_snapshot(card: LearningCard, snapshot: dict) -> None:
    card.lemma_l2 = str(snapshot.get("lemma_l2") or card.lemma_l2)
    card.pos = snapshot.get("pos")
    card.gloss_primary = snapshot.get("gloss_primary")
    card.content = dict(snapshot.get("content") or {})
    lex_id = snapshot.get("lexical_entry_id")
    if lex_id:
        card.lexical_entry_id = UUID(str(lex_id))
    else:
        card.lexical_entry_id = None


def _apply_patch_to_content(content: dict, patch: dict, sections: list[str]) -> dict:
    """Apply all keys present in patch (full-card correction). sections kept for logging only."""
    merged = dict(content or {})
    if patch.get("lemma"):
        merged["lemma"] = patch["lemma"]
    if patch.get("pos"):
        merged["pos"] = patch["pos"]
    if patch.get("gloss_primary"):
        meanings = list(merged.get("meanings") or [])
        if meanings:
            first = dict(meanings[0])
            first["gloss_l1"] = patch["gloss_primary"]
            meanings[0] = first
            merged["meanings"] = meanings
        else:
            merged["meanings"] = [
                {"gloss_l1": patch["gloss_primary"], "synonyms_l1": [], "examples": [], "usages": []}
            ]
    for key in ("meanings", "examples", "conjugation", "similar_words", "ipa"):
        if key in patch:
            merged[key] = patch[key]
    return merged


def _norm_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _is_placeholder(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return bool(_PLACEHOLDER_RE.match(text))


def _content_words(value: str | None) -> set[str]:
    return {w for w in re.findall(r"\w{3,}", _norm_text(value), flags=re.UNICODE)}


def _is_stylistic_gloss_change(old: str | None, new: str | None) -> bool:
    """True when both glosses are valid but only rephrased (not a factual fix)."""
    old_n, new_n = _norm_text(old), _norm_text(new)
    if not old_n or not new_n:
        return False
    if old_n == new_n:
        return True
    if old_n in new_n or new_n in old_n:
        return True
    old_words = _content_words(old)
    new_words = _content_words(new)
    if old_words & new_words:
        return True
    old_stems = {w[:4] for w in old_words if len(w) >= 4}
    new_stems = {w[:4] for w in new_words if len(w) >= 4}
    return bool(old_stems & new_stems)


def _json_stable(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _conjugation_has_placeholders(conjugation: object) -> bool:
    if not isinstance(conjugation, dict):
        return False
    blob = _json_stable(conjugation)
    return "—" in blob or '"-"' in blob or "…" in blob


def _primary_gloss(snapshot: dict) -> str | None:
    gloss = snapshot.get("gloss_primary")
    if gloss:
        return str(gloss)
    content = snapshot.get("content") or {}
    meanings = content.get("meanings") or []
    if meanings and isinstance(meanings[0], dict):
        g = meanings[0].get("gloss_l1")
        return str(g) if g else None
    return None


def patch_is_material(before: dict, patch: dict) -> tuple[bool, str | None]:
    """Reject LLM accepts that would not fix a real error (stylistic-only or no-op)."""
    if not isinstance(patch, dict) or not patch:
        return False, "Brak zmian w poprawce."

    content = dict(before.get("content") or {})
    merged = _apply_patch_to_content(content, patch, [])
    material: list[str] = []

    if patch.get("lemma"):
        old_lemma = _norm_text(before.get("lemma_l2") or content.get("lemma"))
        new_lemma = _norm_text(patch.get("lemma"))
        if new_lemma and new_lemma != old_lemma:
            material.append("lemma")

    if patch.get("pos"):
        old_pos = _norm_text(before.get("pos") or content.get("pos"))
        new_pos = _norm_text(patch.get("pos"))
        if new_pos and new_pos != old_pos:
            material.append("pos")

    if patch.get("gloss_primary"):
        old_gloss = _primary_gloss(before)
        new_gloss = str(patch["gloss_primary"])
        if _is_placeholder(old_gloss):
            material.append("gloss")
        elif not _is_stylistic_gloss_change(old_gloss, new_gloss):
            material.append("gloss")

    if patch.get("ipa"):
        old_ipa = _norm_text(content.get("ipa"))
        new_ipa = _norm_text(patch.get("ipa"))
        if new_ipa and (new_ipa != old_ipa or _is_placeholder(content.get("ipa"))):
            material.append("pronunciation")

    for key in ("meanings", "examples", "similar_words"):
        if key not in patch:
            continue
        if _json_stable(content.get(key)) != _json_stable(patch.get(key)):
            material.append(key)

    if "conjugation" in patch:
        old_conj = content.get("conjugation")
        new_conj = patch.get("conjugation")
        if _json_stable(old_conj) != _json_stable(new_conj):
            if _conjugation_has_placeholders(old_conj) or _conjugation_has_placeholders(new_conj):
                material.append("conjugation")
            elif old_conj is None and new_conj:
                material.append("conjugation")

    after_top = {
        "lemma_l2": patch.get("lemma") or before.get("lemma_l2"),
        "pos": patch.get("pos") or before.get("pos"),
        "gloss_primary": patch.get("gloss_primary") or before.get("gloss_primary"),
        "content": merged,
    }
    if not material and _json_stable(before) == _json_stable(after_top):
        return False, "Poprawka nie wprowadza żadnych rzeczywistych zmian."

    if not material:
        return (
            False,
            "Karta jest poprawna — zmiana byłaby tylko stylistyczna lub równoważna semantycznie.",
        )
    return True, None


def _diff_summary(before: dict, after: dict) -> str:
    parts: list[str] = []
    if before.get("lemma_l2") != after.get("lemma_l2"):
        parts.append(f"lemma: {before.get('lemma_l2')} → {after.get('lemma_l2')}")
    if before.get("pos") != after.get("pos"):
        parts.append(f"pos: {before.get('pos')} → {after.get('pos')}")
    if before.get("gloss_primary") != after.get("gloss_primary"):
        parts.append(f"gloss: {before.get('gloss_primary')} → {after.get('gloss_primary')}")
    before_content = before.get("content") or {}
    after_content = after.get("content") or {}
    if before_content.get("ipa") != after_content.get("ipa"):
        parts.append(f"ipa: {before_content.get('ipa')} → {after_content.get('ipa')}")
    if _json_stable(before_content.get("conjugation")) != _json_stable(after_content.get("conjugation")):
        parts.append("conjugation updated")
    if _json_stable(before_content.get("meanings")) != _json_stable(after_content.get("meanings")):
        parts.append("meanings updated")
    if _json_stable(before_content.get("similar_words")) != _json_stable(after_content.get("similar_words")):
        parts.append("similar words updated")
    return "; ".join(parts) if parts else "content updated"


async def _add_history_event(
    db: AsyncSession,
    *,
    card_id: UUID,
    user_id: UUID,
    event_type: str,
    actor: str,
    result_code: str | None = None,
    summary: str | None = None,
    payload: dict | None = None,
) -> CardHistoryEvent:
    event = CardHistoryEvent(
        card_id=card_id,
        user_id=user_id,
        event_type=event_type,
        actor=actor,
        result_code=result_code,
        summary=summary,
        payload=payload,
    )
    db.add(event)
    await db.flush()
    return event


def _can_restore_event(event: CardHistoryEvent, all_events: list[CardHistoryEvent]) -> bool:
    if event.event_type != "self_edit_applied":
        return False
    prior = [e for e in all_events if e.created_at < event.created_at]
    submissions = [e for e in prior if e.event_type == "correction_submitted"]
    if not submissions:
        return True
    last_sub = max(submissions, key=lambda e: e.created_at)
    resolutions = [
        e
        for e in prior
        if e.created_at >= last_sub.created_at
        and e.event_type in {"correction_accepted", "correction_rejected"}
    ]
    if any(e.event_type == "correction_accepted" for e in resolutions):
        return False
    return any(e.event_type == "correction_rejected" for e in resolutions)


def _pair_rows_equal(a: list, b: list) -> bool:
  def norm_row(row: dict) -> tuple[str, str]:
      return (_norm_text(row.get("l2")), _norm_text(row.get("l1")))

  return [norm_row(dict(r)) for r in a if isinstance(r, dict)] == [
      norm_row(dict(r)) for r in b if isinstance(r, dict)
  ]


def compute_self_edit_user_changes(before: dict, after: dict) -> dict:
    """Diff only user-editable fields: pos, notes, meanings (gloss/examples/usages)."""
    changes: dict = {}
    if _norm_text(before.get("pos")) != _norm_text(after.get("pos")):
        changes["pos"] = {"from": before.get("pos"), "to": after.get("pos")}
    if _norm_text(before.get("notes")) != _norm_text(after.get("notes")):
        changes["notes"] = {"from": before.get("notes") or "", "to": after.get("notes") or ""}

    before_meanings = [dict(m) for m in (before.get("meanings") or []) if isinstance(m, dict)]
    after_meanings = [dict(m) for m in (after.get("meanings") or []) if isinstance(m, dict)]
    meaning_changes: list[dict] = []
    max_len = max(len(before_meanings), len(after_meanings))
    for index in range(max_len):
        before_m = before_meanings[index] if index < len(before_meanings) else {}
        after_m = after_meanings[index] if index < len(after_meanings) else {}
        entry: dict = {"index": index}
        changed = False
        if _norm_text(before_m.get("gloss_l1")) != _norm_text(after_m.get("gloss_l1")):
            entry["gloss_l1"] = {
                "from": before_m.get("gloss_l1") or "",
                "to": after_m.get("gloss_l1") or "",
            }
            changed = True
        if not _pair_rows_equal(before_m.get("examples") or [], after_m.get("examples") or []):
            entry["examples"] = {
                "from": before_m.get("examples") or [],
                "to": after_m.get("examples") or [],
            }
            changed = True
        if not _pair_rows_equal(before_m.get("usages") or [], after_m.get("usages") or []):
            entry["usages"] = {
                "from": before_m.get("usages") or [],
                "to": after_m.get("usages") or [],
            }
            changed = True
        if changed:
            meaning_changes.append(entry)
    if meaning_changes:
        changes["meanings"] = meaning_changes
    return changes


async def validate_self_edit_before_save(
    *,
    card: LearningCard,
    profile: LanguageProfile,
    after_content: dict,
) -> dict:
    before = dict(card.content or {})
    changes = compute_self_edit_user_changes(before, after_content)
    if not changes:
        return {"ok": True, "issues": []}
    llm = LLMService()
    return await llm.validate_self_edit_changes(
        lemma=str(after_content.get("lemma") or card.lemma_l2),
        learning_lang=profile.learning_lang,
        app_lang=profile.app_lang,
        changes=changes,
    )


def apply_self_edit_content(card: LearningCard, content: dict) -> dict:
    """Apply full user self-edit in-place; returns before snapshot for history."""
    before = _card_snapshot(card)
    merged = dict(content or {})
    lemma = str(merged.get("lemma") or card.lemma_l2).strip()
    if not lemma:
        raise ValueError("lemma is required")
    merged["lemma"] = lemma
    meanings = merged.get("meanings") or []
    gloss_primary = card.gloss_primary
    if meanings and isinstance(meanings[0], dict):
        g = meanings[0].get("gloss_l1")
        if g:
            gloss_primary = str(g)
    card.content = merged
    card.lemma_l2 = lemma
    card.pos = merged.get("pos")
    card.gloss_primary = gloss_primary
    card.lexical_entry_id = None
    card.content_review_status = "user_edited"
    card.has_content_changes = True
    card.card_activity_status = "self_edit_processing"
    return before


def apply_self_edit(
    card: LearningCard,
    *,
    lemma_l2: str,
    pos: str | None,
    gloss_primary: str | None,
    extra_glosses: list[str],
) -> dict:
    """Legacy narrow self-edit — prefer apply_self_edit_content."""
    content = dict(card.content or {})
    content["lemma"] = lemma_l2
    if pos:
        content["pos"] = pos
    glosses = [g for g in ([gloss_primary] if gloss_primary else []) + list(extra_glosses) if g and g.strip()]
    if glosses:
        meanings = list(content.get("meanings") or [])
        new_meanings: list[dict] = []
        for i, gloss in enumerate(glosses):
            if i < len(meanings):
                m = dict(meanings[i])
                m["gloss_l1"] = gloss
                new_meanings.append(m)
            else:
                new_meanings.append(
                    {"gloss_l1": gloss, "synonyms_l1": [], "examples": [], "usages": []}
                )
        content["meanings"] = new_meanings
    return apply_self_edit_content(card, content)


async def count_corrections_today(db: AsyncSession, user_id: UUID) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count())
        .select_from(CardCorrection)
        .where(CardCorrection.user_id == user_id, CardCorrection.created_at >= start)
    )
    return int(result.scalar_one())


async def process_correction(correction_id: UUID) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(CardCorrection, LearningCard, LanguageProfile)
            .join(LearningCard, LearningCard.id == CardCorrection.card_id)
            .join(LanguageProfile, LanguageProfile.id == LearningCard.profile_id)
            .where(CardCorrection.id == correction_id)
        )
        row = result.one_or_none()
        if row is None:
            return
        correction, card, profile = row
        if correction.status != "reported":
            return

        before = _card_snapshot(card)
        llm = LLMService()
        try:
            verdict = await llm.verify_card_correction(
                content=dict(card.content or {}),
                sections=list(correction.sections or []),
                note=correction.note or "",
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
            )
        except Exception:
            logger.exception("Correction LLM failed for %s", correction_id)
            now = datetime.now(UTC)
            correction.status = "rejected"
            correction.result_code = "correction_processing_failed"
            correction.reason = "Processing failed"
            correction.resolved_at = now
            card.content_review_status = "correction_rejected"
            card.card_activity_status = None
            await _add_history_event(
                db,
                card_id=card.id,
                user_id=correction.user_id,
                event_type="correction_rejected",
                actor="system",
                result_code="correction_processing_failed",
                summary="Nie udało się przetworzyć zgłoszenia.",
                payload={"sections": correction.sections, "note": correction.note},
            )
            await db.commit()
            await notify_correction_resolved(db, card.user_id, card.id, correction.status)
            return

        now = datetime.now(UTC)
        status = str(verdict.get("status", "rejected")).lower()
        result_code = str(verdict.get("code") or "correction_unfounded")
        if result_code not in CORRECTION_RESULT_CODES:
            result_code = "correction_unfounded" if status != "accepted" else "correction_accepted"
        reason = verdict.get("reason_detail") or verdict.get("reason")
        patch = verdict.get("patch")

        applied = False
        if status == "accepted" and isinstance(patch, dict):
            material, reject_reason = patch_is_material(before, patch)
            if material:
                card.content = _apply_patch_to_content(
                    dict(card.content or {}), patch, list(correction.sections or [])
                )
                if patch.get("lemma"):
                    card.lemma_l2 = str(patch["lemma"])
                if patch.get("pos"):
                    card.pos = str(patch["pos"])
                if patch.get("gloss_primary"):
                    card.gloss_primary = str(patch["gloss_primary"])
                card.lexical_entry_id = None
                card.content_review_status = "correction_accepted"
                card.has_content_changes = True
                correction.status = "accepted"
                correction.result_code = "correction_accepted"
                after = _card_snapshot(card)
                await _add_history_event(
                    db,
                    card_id=card.id,
                    user_id=correction.user_id,
                    event_type="correction_accepted",
                    actor="system",
                    result_code="correction_accepted",
                    summary=_diff_summary(before, after),
                    payload={"reason": reason, "patch": patch, "before": before, "after": after},
                )
                applied = True
            else:
                status = "rejected"
                result_code = "correction_unfounded"
                reason = reject_reason or "Karta jest poprawna — brak błędów do poprawy."
        elif status == "accepted":
            status = "rejected"
            result_code = "correction_unfounded"
            reason = reason or "Brak poprawki do zastosowania."

        if not applied:
            correction.status = "rejected"
            correction.result_code = result_code
            card.content_review_status = "correction_rejected"
            await _add_history_event(
                db,
                card_id=card.id,
                user_id=correction.user_id,
                event_type="correction_rejected",
                actor="system",
                result_code=result_code,
                summary=reason or result_code,
                payload={
                    "sections": correction.sections,
                    "note": correction.note,
                    "reason": reason,
                    **({"rejected_patch": patch} if isinstance(patch, dict) else {}),
                },
            )

        correction.reason = reason
        correction.patch = patch if isinstance(patch, dict) else None
        correction.resolved_at = now
        card.card_activity_status = None
        await db.commit()
        await notify_correction_resolved(db, card.user_id, card.id, correction.status)


async def review_self_edit(history_event_id: UUID) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(CardHistoryEvent, LearningCard, LanguageProfile)
            .join(LearningCard, LearningCard.id == CardHistoryEvent.card_id)
            .join(LanguageProfile, LanguageProfile.id == LearningCard.profile_id)
            .where(CardHistoryEvent.id == history_event_id)
        )
        row = result.one_or_none()
        if row is None:
            return
        event, card, profile = row
        if event.event_type != "self_edit_applied":
            return

        payload = dict(event.payload or {})
        before = payload.get("before") or {}
        after = payload.get("after") or _card_snapshot(card)

        llm = LLMService()
        try:
            verdict = await llm.review_self_edit(
                before_content=dict(before.get("content") or {}),
                after_content=dict(after.get("content") or {}),
                before_lemma=str(before.get("lemma_l2") or ""),
                after_lemma=str(after.get("lemma_l2") or ""),
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
            )
            ai_verdict = str(verdict.get("verdict") or "self_edit_ok")
            if ai_verdict not in SELF_EDIT_VERDICT_CODES:
                ai_verdict = "self_edit_questionable"
            ai_reason = verdict.get("reason")
        except Exception:
            logger.exception("Self-edit review failed for event %s", history_event_id)
            ai_verdict = "self_edit_questionable"
            ai_reason = "Review processing failed"

        review = AdminCardReview(
            user_id=event.user_id,
            card_id=card.id,
            source="self_edit",
            source_id=event.id,
            learning_lang=profile.learning_lang,
            before_snapshot=before,
            after_snapshot=after,
            ai_verdict=ai_verdict.replace("self_edit_", ""),
            ai_reason=ai_reason,
            admin_status="pending",
        )
        db.add(review)
        await _add_history_event(
            db,
            card_id=card.id,
            user_id=event.user_id,
            event_type="self_edit_reviewed",
            actor="system",
            result_code=ai_verdict,
            summary=ai_reason or ai_verdict,
            payload={"review_id": str(review.id)},
        )
        card.card_activity_status = None
        await db.commit()


async def restore_card_from_history(
    db: AsyncSession,
    *,
    card: LearningCard,
    user_id: UUID,
    history_event_id: UUID,
) -> CardHistoryEvent:
    events_q = await db.execute(
        select(CardHistoryEvent)
        .where(CardHistoryEvent.card_id == card.id, CardHistoryEvent.user_id == user_id)
        .order_by(CardHistoryEvent.created_at.asc())
    )
    all_events = list(events_q.scalars().all())
    target = next((e for e in all_events if e.id == history_event_id), None)
    if target is None:
        raise ValueError("History event not found")
    if not _can_restore_event(target, all_events):
        raise ValueError("Restore not allowed for this event")

    snapshot = (target.payload or {}).get("pre_edit_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("No snapshot available")

    _apply_snapshot(card, snapshot)
    card.content_review_status = None
    card.card_activity_status = None
    restored = await _add_history_event(
        db,
        card_id=card.id,
        user_id=user_id,
        event_type="restored_to_original",
        actor="user",
        summary="Przywrócono oryginalną wersję karty",
        payload={"restored_from_event_id": str(history_event_id)},
    )
    return restored


async def create_correction_submitted_event(
    db: AsyncSession,
    *,
    card: LearningCard,
    user_id: UUID,
    sections: list[str],
    note: str | None,
) -> None:
    section_labels = ", ".join(sections) if sections else "—"
    await _add_history_event(
        db,
        card_id=card.id,
        user_id=user_id,
        event_type="correction_submitted",
        actor="user",
        summary=f"Zgłoszenie: {section_labels}",
        payload={"sections": sections, "note": note},
    )


async def create_self_edit_history_event(
    db: AsyncSession,
    *,
    card: LearningCard,
    user_id: UUID,
    before: dict,
) -> CardHistoryEvent:
    after = _card_snapshot(card)
    return await _add_history_event(
        db,
        card_id=card.id,
        user_id=user_id,
        event_type="self_edit_applied",
        actor="user",
        summary=_diff_summary(before, after),
        payload={
            "before": before,
            "after": after,
            "pre_edit_snapshot": before,
        },
    )


def history_event_response(event: CardHistoryEvent, all_events: list[CardHistoryEvent]) -> dict:
    return {
        "id": event.id,
        "card_id": event.card_id,
        "event_type": event.event_type,
        "actor": event.actor,
        "result_code": event.result_code,
        "summary": event.summary,
        "payload": event.payload,
        "created_at": event.created_at,
        "can_restore": _can_restore_event(event, all_events),
    }

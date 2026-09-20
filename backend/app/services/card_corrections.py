"""Card correction reports, history, and admin escalation queue."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.lsp.lang_utils import articles_for
from app.models import (
    AdminEscalation,
    CardCorrection,
    CardHistoryEvent,
    LanguageProfile,
    LearningCard,
)
from app.services.correction_evidence import both_glosses_attested, gather_correction_evidence
from app.services.llm import LLMService
from app.services.pos_normalize import (
    ensure_noun_article,
    infer_gender_from_lemma,
    infer_gender_from_pos,
    lemma_has_article,
    normalize_pos_bucket,
)
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
    "family",
    "associations",
    "synonyms",
    "antonyms",
    "other",
}

PATCH_CONTENT_KEYS = (
    "meanings",
    "examples",
    "conjugation",
    "similar_words",
    "ipa",
    "notes",
    "synonyms_l2",
    "antonyms_l2",
    "word_family_l2",
    "associations_l2",
)

PATCH_PROMPT_FIELDS = (
    "lemma",
    "pos",
    "gloss_primary",
    *PATCH_CONTENT_KEYS,
)

STYLE_REJECT_REASON = (
    "Karta jest poprawna — zmiana byłaby tylko stylistyczna lub równoważna semantycznie."
)

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


def _apply_patch_to_content(content: dict, patch: dict, sections: list[str] | None = None) -> dict:
    """Apply every known card field present in patch."""
    merged = dict(content or {})
    if patch.get("lemma"):
        merged["lemma"] = str(patch["lemma"]).strip()
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
    for key in PATCH_CONTENT_KEYS:
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
    """Reject accepts that would not fix a real error (stylistic-only or no-op)."""
    if not isinstance(patch, dict) or not patch:
        return False, "Brak zmian w poprawce."

    content = dict(before.get("content") or {})
    merged = _apply_patch_to_content(content, patch)
    material: list[str] = []

    if patch.get("lemma"):
        old_lemma = _norm_text(before.get("lemma_l2") or content.get("lemma"))
        new_lemma = _norm_text(patch.get("lemma"))
        inner_lemma = _norm_text(content.get("lemma"))
        if new_lemma and (new_lemma != old_lemma or new_lemma != inner_lemma):
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

    if "notes" in patch:
        if _norm_text(content.get("notes")) != _norm_text(patch.get("notes")):
            material.append("notes")

    for key in ("meanings", "examples", "similar_words", "synonyms_l2", "antonyms_l2", "word_family_l2", "associations_l2"):
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
    if not material and _json_stable(
        {k: before.get(k) for k in ("lemma_l2", "pos", "gloss_primary", "content")}
    ) == _json_stable(after_top):
        return False, "Poprawka nie wprowadza żadnych rzeczywistych zmian."

    if not material:
        return False, STYLE_REJECT_REASON
    return True, None


def gate_accepted_patch(
    before: dict,
    patch: dict,
    evidence: dict | None = None,
) -> tuple[bool, str | None]:
    """Hard checks after the model accepts: materiality + synonym ping-pong."""
    material, reason = patch_is_material(before, patch)
    if not material:
        return False, reason
    if patch.get("gloss_primary") and evidence:
        old_gloss = _primary_gloss(before)
        new_gloss = str(patch["gloss_primary"])
        if both_glosses_attested(old_gloss, new_gloss, evidence):
            return False, STYLE_REJECT_REASON
    return True, None


def obvious_headword_fix(before: dict, learning_lang: str) -> dict | None:
    """Sync the two headword fields; prefer the citation form with an article when the language has them."""
    content = dict(before.get("content") or {})
    top = str(before.get("lemma_l2") or "").strip()
    inner = str(content.get("lemma") or "").strip()
    if not top and not inner:
        return None
    if _norm_text(top) == _norm_text(inner) and top and inner:
        return None
    chosen = top or inner
    if articles_for(learning_lang):
        if lemma_has_article(top, learning_lang) and not lemma_has_article(inner, learning_lang):
            chosen = top
        elif lemma_has_article(inner, learning_lang) and not lemma_has_article(top, learning_lang):
            chosen = inner
    if not chosen:
        return None
    if _norm_text(chosen) == _norm_text(inner) and _norm_text(chosen) == _norm_text(top):
        return None
    return {"lemma": chosen}


def _citation_lemma(lemma: str, pos: str | None, learning_lang: str) -> str:
    text = str(lemma or "").strip()
    if not text:
        return text
    if normalize_pos_bucket(pos) != "noun":
        return text
    if not articles_for(learning_lang):
        return text
    gender = infer_gender_from_lemma(text, learning_lang) or infer_gender_from_pos(pos)
    return ensure_noun_article(text, learning_lang=learning_lang, gender=gender)


def apply_correction_patch(card: LearningCard, patch: dict, learning_lang: str) -> None:
    content = _apply_patch_to_content(dict(card.content or {}), patch)
    lemma = str(content.get("lemma") or patch.get("lemma") or card.lemma_l2 or "").strip()
    pos = str(patch.get("pos") or content.get("pos") or card.pos or "") or None
    lemma = _citation_lemma(lemma, pos, learning_lang)
    content["lemma"] = lemma
    if pos:
        content["pos"] = pos
        card.pos = pos
    card.lemma_l2 = lemma
    card.content = content
    if patch.get("gloss_primary"):
        card.gloss_primary = str(patch["gloss_primary"])
    else:
        meanings = content.get("meanings") or []
        if meanings and isinstance(meanings[0], dict) and meanings[0].get("gloss_l1"):
            card.gloss_primary = str(meanings[0]["gloss_l1"])
    card.lexical_entry_id = None


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
    for key, label in (
        ("conjugation", "conjugation updated"),
        ("meanings", "meanings updated"),
        ("examples", "examples updated"),
        ("similar_words", "similar words updated"),
        ("synonyms_l2", "synonyms updated"),
        ("antonyms_l2", "antonyms updated"),
        ("word_family_l2", "word family updated"),
        ("associations_l2", "associations updated"),
        ("notes", "notes updated"),
    ):
        if _json_stable(before_content.get(key)) != _json_stable(after_content.get(key)):
            parts.append(label)
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


async def count_corrections_today(db: AsyncSession, user_id: UUID) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count())
        .select_from(CardCorrection)
        .where(CardCorrection.user_id == user_id, CardCorrection.created_at >= start)
    )
    return int(result.scalar_one())


def _accept_patch(
    card: LearningCard,
    correction: CardCorrection,
    *,
    patch: dict,
    before: dict,
    reason: str | None,
    learning_lang: str,
) -> None:
    apply_correction_patch(card, patch, learning_lang)
    card.content_review_status = "correction_accepted"
    card.has_content_changes = True
    correction.status = "accepted"
    correction.result_code = "correction_accepted"


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
        evidence: dict = {}
        try:
            evidence = await gather_correction_evidence(
                dict(card.content or {}),
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
            )
        except Exception:
            logger.exception("Correction dictionary lookup failed for %s", correction_id)
            evidence = {"lookup_empty": True, "lookup_error": True, "lemma_candidates": []}

        llm = LLMService()
        try:
            verdict = await llm.verify_card_correction(
                content=dict(card.content or {}),
                sections=list(correction.sections or []),
                note=correction.note or "",
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
                evidence=evidence,
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
            ok, reject_reason = gate_accepted_patch(before, patch, evidence)
            if ok:
                _accept_patch(
                    card,
                    correction,
                    patch=patch,
                    before=before,
                    reason=reason,
                    learning_lang=profile.learning_lang,
                )
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
                reason = reject_reason or STYLE_REJECT_REASON
        elif status == "accepted":
            status = "rejected"
            result_code = "correction_unfounded"
            reason = reason or "Brak poprawki do zastosowania."

        if not applied:
            obvious = obvious_headword_fix(before, profile.learning_lang)
            if obvious:
                ok, _ = gate_accepted_patch(before, obvious, evidence)
                if ok:
                    _accept_patch(
                        card,
                        correction,
                        patch=obvious,
                        before=before,
                        reason=reason,
                        learning_lang=profile.learning_lang,
                    )
                    after = _card_snapshot(card)
                    await _add_history_event(
                        db,
                        card_id=card.id,
                        user_id=correction.user_id,
                        event_type="correction_accepted",
                        actor="system",
                        result_code="correction_accepted",
                        summary=_diff_summary(before, after),
                        payload={
                            "reason": "Zsynchronizowano hasło karty.",
                            "patch": obvious,
                            "before": before,
                            "after": after,
                        },
                    )
                    applied = True
                    patch = obvious
                    reason = "Zsynchronizowano hasło karty."

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


async def escalate_rejected_correction(
    db: AsyncSession,
    *,
    user_id: UUID,
    card: LearningCard,
    correction: CardCorrection,
) -> AdminEscalation:
    if correction.user_id != user_id or correction.card_id != card.id:
        raise ValueError("Correction not found")
    if correction.status != "rejected":
        raise ValueError("Only a rejected report can be sent to administration")
    existing = (
        await db.execute(
            select(AdminEscalation).where(AdminEscalation.correction_id == correction.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = AdminEscalation(
        user_id=user_id,
        card_id=card.id,
        correction_id=correction.id,
        user_note=correction.note,
        sections=list(correction.sections or []),
        reject_reason=correction.reason,
        card_snapshot=_card_snapshot(card),
        status="pending",
    )
    db.add(row)
    await db.flush()
    await _add_history_event(
        db,
        card_id=card.id,
        user_id=user_id,
        event_type="correction_escalated",
        actor="user",
        summary="Zgłoszono do administracji",
        payload={"escalation_id": str(row.id), "correction_id": str(correction.id)},
    )
    return row


async def mark_escalation_done(db: AsyncSession, escalation_id: UUID) -> AdminEscalation | None:
    row = await db.get(AdminEscalation, escalation_id)
    if row is None:
        return None
    row.status = "done"
    row.resolved_at = datetime.now(UTC)
    await db.flush()
    return row


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
        "can_restore": False,
    }

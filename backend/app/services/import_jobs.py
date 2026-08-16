"""Import / analiza jako trwałe zadanie w PostgreSQL.

Praca nie zależy od gniazda HTTP klienta. Telefon tylko startuje job
i odpytuje GET /imports/jobs/{id}/progress.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models import (
    ACTIVE_IMPORT_STATUSES,
    ImportJob,
    ImportJobEvent,
    ImportJobItem,
    LanguageProfile,
    LearningCard,
    SrsState,
    User,
    WordList,
)
from app.services.card_jobs import (
    STATUS_PENDING,
    STATUS_READY,
    build_import_display_content,
    build_pending_content,
    enrich_card,
    hydrate_from_lexical_cache,
)
from app.lsp.constants import SUPPORTED_L2_LANGS
from app.lsp.lang_utils import articles_for
from app.services.import_classify import (
    _note_input,
    _vocabulario_lemma,
    classify_notes_detailed,
)
from app.services.import_display import resolve_import_display_cards
from app.services.import_format import ensure_deck_segmented
from app.services.import_package import (
    ImportPackageError,
    RawImportDeck,
    load_raw_import,
    load_text_import,
)
from app.services.import_urls import ImportUrlError, detect_import_url, fetch_words_from_url
from app.services.llm import LLMService
from app.services.word_lists import find_card_anywhere

logger = logging.getLogger(__name__)

COMMIT_MAX_ATTEMPTS = 3
COMMIT_BACKOFF_S = (0.5, 1.0, 2.0)
HEARTBEAT_STALE_S = 90
WATCHDOG_INTERVAL_S = 30

_LEADING_ARTICLES = frozenset().union(*(articles_for(code) for code in SUPPORTED_L2_LANGS))

_running: set[UUID] = set()


def _now() -> datetime:
    return datetime.now(UTC)


def _note_label(note: list[Any]) -> str:
    return " | ".join(str(c).strip() for c in (note or []) if str(c).strip())[:200]


def format_error_lemmas(items: list[ImportJobItem]) -> str:
    """Schowek: `lemat1; lemat2; lemat3`."""
    parts: list[str] = []
    for it in sorted(items, key=lambda x: x.ordinal):
        if it.verdict != "failed":
            continue
        label = (it.lemma or it.input_label or "").strip()
        if label:
            parts.append(label)
    return "; ".join(parts)


async def _add_event(
    db: AsyncSession,
    job_id: UUID,
    event: str,
    *,
    level: str = "info",
    item_id: UUID | None = None,
    payload: dict | None = None,
) -> None:
    db.add(
        ImportJobEvent(
            job_id=job_id,
            item_id=item_id,
            level=level,
            event=event,
            payload=payload,
        )
    )


async def _load_job(db: AsyncSession, job_id: UUID, *, with_items: bool = False) -> ImportJob | None:
    q = select(ImportJob).where(ImportJob.id == job_id)
    if with_items:
        q = q.options(selectinload(ImportJob.items))
    return (await db.execute(q)).scalar_one_or_none()


async def _touch(
    db: AsyncSession,
    job: ImportJob,
    **fields: Any,
) -> None:
    if not job.cancel_requested:
        await db.refresh(job, attribute_names=["cancel_requested", "status"])
    if job.cancel_requested or job.status in {"cancelled", "cancelling"}:
        incoming = fields.get("status")
        if incoming not in {"cancelled", "failed"}:
            fields.pop("status", None)
    for key, value in fields.items():
        setattr(job, key, value)
    job.heartbeat_at = _now()
    job.updated_at = _now()


async def _refresh_counts(job: ImportJob, items: list[ImportJobItem]) -> None:
    job.ready_count = sum(1 for i in items if i.verdict == "ready")
    job.duplicate_count = sum(1 for i in items if i.verdict == "duplicate")
    job.failed_count = sum(1 for i in items if i.verdict == "failed")


async def find_active_job(
    db: AsyncSession,
    user_id: UUID,
    profile_id: UUID,
) -> ImportJob | None:
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.user_id == user_id,
            ImportJob.profile_id == profile_id,
            ImportJob.status.in_(ACTIVE_IMPORT_STATUSES),
        )
    )
    return result.scalar_one_or_none()


async def create_job_from_text(
    db: AsyncSession,
    *,
    user: User,
    profile: LanguageProfile,
    word_list: WordList,
    text: str,
    mode: str,
) -> ImportJob:
    mode_n = (mode or "vocabulario").strip().lower()
    if mode_n not in {"vocabulario", "preserve"}:
        mode_n = "vocabulario"
    url = detect_import_url(text)
    source_kind = "url" if url else "paste"
    source_name = "paste"
    notes: list[list[str]] = []
    raw_text: str | None = text
    kind = "raw_text"
    field_names: list[str] | None = None
    if url:
        if mode_n == "preserve":
            raise ImportPackageError("Preserve-cards mode works with paste/file, not a URL.")
        words = await fetch_words_from_url(url)
        if not words:
            raise ImportPackageError("No words to import")
        notes = [[w] for w in words]
        raw_text = "\n".join(words)
        kind = "plain"
        source_name = url[:200]
    else:
        deck = load_text_import(text)
        notes = list(deck.notes)
        raw_text = deck.raw_text or text
        kind = deck.kind
        field_names = deck.field_names
        if not notes and not (deck.raw_text or "").strip():
            raise ImportPackageError("No words to import")

    return await _insert_job(
        db,
        user=user,
        profile=profile,
        word_list=word_list,
        mode=mode_n,
        source_kind=source_kind,
        source_name=source_name,
        notes=notes,
        raw_text=raw_text,
        kind=kind,
        field_names=field_names,
        input_bytes=text.encode("utf-8", errors="replace"),
    )


async def create_job_from_file(
    db: AsyncSession,
    *,
    user: User,
    profile: LanguageProfile,
    word_list: WordList,
    filename: str,
    data: bytes,
    mode: str,
) -> ImportJob:
    mode_n = (mode or "vocabulario").strip().lower()
    if mode_n not in {"vocabulario", "preserve"}:
        mode_n = "vocabulario"
    deck = load_raw_import(filename, data)
    if not deck.notes and not (deck.raw_text or "").strip():
        raise ImportPackageError("No words to import")
    return await _insert_job(
        db,
        user=user,
        profile=profile,
        word_list=word_list,
        mode=mode_n,
        source_kind="file",
        source_name=filename or "import.bin",
        notes=list(deck.notes),
        raw_text=deck.raw_text,
        kind=deck.kind,
        field_names=deck.field_names,
        input_bytes=data,
    )


async def _insert_job(
    db: AsyncSession,
    *,
    user: User,
    profile: LanguageProfile,
    word_list: WordList,
    mode: str,
    source_kind: str,
    source_name: str,
    notes: list[list[str]],
    raw_text: str | None,
    kind: str,
    field_names: list[str] | None,
    input_bytes: bytes,
) -> ImportJob:
    existing = await find_active_job(db, user.id, profile.id)
    if existing is not None:
        raise ActiveImportJobError(existing.id)

    digest = hashlib.sha256(input_bytes).hexdigest()
    meta_text = raw_text if raw_text is not None and len(raw_text) <= 600_000 else None
    job = ImportJob(
        user_id=user.id,
        profile_id=profile.id,
        list_id=word_list.id,
        phase="analyze",
        status="queued",
        stage="queued",
        source_kind=source_kind,
        source_name=source_name[:255],
        mode=mode,
        total=len(notes),
        input_sha256=digest,
        input_meta={
            "kind": kind,
            "field_names": field_names or [],
            "filename": source_name,
            "bytes": len(input_bytes),
            "notes": len(notes),
            "lang_pair": f"{profile.app_lang}>{profile.learning_lang}",
            "raw_text": meta_text,
        },
    )
    db.add(job)
    await db.flush()
    for i, note in enumerate(notes):
        db.add(
            ImportJobItem(
                job_id=job.id,
                ordinal=i,
                raw_note=list(note),
                input_label=_note_label(note),
            )
        )
    await _add_event(
        db,
        job.id,
        "job_created",
        payload={"source_kind": source_kind, "mode": mode, "notes": len(notes)},
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        again = await find_active_job(db, user.id, profile.id)
        if again is not None:
            raise ActiveImportJobError(again.id) from exc
        raise
    await db.refresh(job)
    return job


class ActiveImportJobError(Exception):
    def __init__(self, job_id: UUID):
        super().__init__("import_job_active")
        self.job_id = job_id


def spawn_job(job_id: UUID) -> None:
    if job_id in _running:
        return
    _running.add(job_id)
    asyncio.create_task(_run_guarded(job_id))


async def _run_guarded(job_id: UUID) -> None:
    try:
        await run_import_job(job_id)
    except Exception as exc:
        logger.exception("import job %s crashed", job_id)
        from app.services.app_log import log_event

        await log_event(
            level="error",
            category="import",
            event="import_worker_crash",
            status="error",
            entity_type="import_job",
            entity_id=str(job_id),
            message=f"import worker crashed {job_id}",
            exc=exc,
        )
        async with async_session_factory() as db:
            job = await _load_job(db, job_id)
            if job and job.status in {"queued", "analyzing", "committing", "cancelling"}:
                if job.cancel_requested or job.status == "cancelling":
                    await finalize_cancel(db, job)
                else:
                    await _touch(
                        db,
                        job,
                        status="failed",
                        error_code="worker_crash",
                        error_message="Import worker crashed",
                        finished_at=_now(),
                    )
                    await _add_event(db, job.id, "worker_crash", level="error")
                    await db.commit()
    finally:
        _running.discard(job_id)


async def run_import_job(job_id: UUID) -> None:
    async with async_session_factory() as db:
        job = await _load_job(db, job_id, with_items=True)
        if job is None:
            return
        if job.status == "cancelled":
            return
        if job.cancel_requested or job.status == "cancelling":
            await finalize_cancel(db, job)
            return
        if job.status in {"queued", "analyzing"}:
            await _run_analyze(db, job)
            job = await _load_job(db, job_id, with_items=True)
            if job is None:
                return
        if job.status == "committing":
            await _run_commit(db, job)
        elif job.status == "cancelling" or (job and job.cancel_requested):
            await finalize_cancel(db, job)


async def request_cancel(db: AsyncSession, job: ImportJob) -> ImportJob:
    job.cancel_requested = True
    if job.status in {"done", "failed", "cancelled"}:
        await db.commit()
        return job
    await _add_event(db, job.id, "cancel_requested")
    await finalize_cancel(db, job)
    return job


async def request_commit(db: AsyncSession, job: ImportJob, item_ids: list[UUID] | None) -> ImportJob:
    if job.status != "review":
        raise ValueError("import_job_not_review")
    items = (
        await db.execute(
            select(ImportJobItem)
            .where(ImportJobItem.job_id == job.id)
            .order_by(ImportJobItem.ordinal)
        )
    ).scalars().all()
    ready = [i for i in items if i.verdict == "ready"]
    if item_ids:
        allow = set(item_ids)
        ready = [i for i in ready if i.id in allow]
    if not ready:
        raise ValueError("import_job_nothing_to_commit")
    for i in items:
        if i.verdict == "ready" and i not in ready:
            i.verdict = "failed"
            i.reason_code = "deselected"
            i.verdict_phase = "commit"
    await _touch(
        db,
        job,
        status="committing",
        phase="commit",
        stage="write",
        processed=0,
        total=len(ready),
        current_attempt=0,
        started_at=_now(),
    )
    await _add_event(db, job.id, "commit_started", payload={"total": len(ready)})
    await db.commit()
    spawn_job(job.id)
    return job


async def finalize_cancel(db: AsyncSession, job: ImportJob) -> None:
    await _add_event(db, job.id, "rollback_started")
    now = _now()
    cards = (
        await db.execute(
            select(LearningCard).where(
                LearningCard.import_job_id == job.id,
                LearningCard.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for card in cards:
        card.deleted_at = now
    items = (
        await db.execute(select(ImportJobItem).where(ImportJobItem.job_id == job.id))
    ).scalars().all()
    for it in items:
        it.created_card_id = None
    await _touch(
        db,
        job,
        status="cancelled",
        stage="rollback",
        created_count=0,
        finished_at=now,
        current_label=None,
        current_ordinal=None,
    )
    await _add_event(db, job.id, "rollback_done", payload={"cards": len(cards)})
    await db.commit()


async def _cancelled(db: AsyncSession, job: ImportJob) -> bool:
    # Nie wołaj refresh(job) — expire relacji items + delete-orphan przy
    # flushu nadpisuje niezacommitowane werdykty (zostają tylko idx % 10).
    row = (
        await db.execute(
            select(ImportJob.cancel_requested, ImportJob.status).where(ImportJob.id == job.id)
        )
    ).one()
    job.cancel_requested = bool(row[0])
    if row[1] in {"cancelling", "cancelled"}:
        job.status = row[1]
    return bool(job.cancel_requested or job.status in {"cancelling", "cancelled"})


def _apply_lemma_verify(
    ready_items: list[ImportJobItem],
    payload: dict[str, Any],
) -> None:
    """Odrzuć ready, które weryfikacja LLM uznała za nie-lematy."""
    for raw in payload.get("invalid") or []:
        if not isinstance(raw, dict):
            continue
        try:
            idx = int(raw["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(ready_items):
            continue
        item = ready_items[idx]
        item.verdict = "failed"
        item.reason_code = "llm_invalid"
        item.reason_detail = str(raw.get("reason") or "not a dictionary lemma")[:2000]
        item.verdict_phase = "analyze"


async def _verify_ready_lemmas(
    db: AsyncSession,
    job: ImportJob,
    items: list[ImportJobItem],
    llm: LLMService,
    learning_lang: str,
) -> None:
    ready = [i for i in items if i.verdict == "ready" and (i.lemma or "").strip()]
    if not ready or llm.mock:
        return
    lemmas = [(i.lemma or "").strip() for i in ready]
    await _add_event(db, job.id, "llm_call", payload={"phase": "verify", "n": len(lemmas)})
    await db.commit()
    try:
        payload = await llm.analyze_import_verify_lemmas(
            learning=learning_lang,
            lemmas=lemmas,
        )
    except Exception as exc:
        logger.exception("import lemma verify failed job=%s", job.id)
        from app.services.app_log import log_event

        await log_event(
            level="error",
            category="import",
            event="import_verify_failed",
            status="error",
            user_id=job.user_id,
            profile_id=job.profile_id,
            entity_type="import_job",
            entity_id=str(job.id),
            message="import lemma verify failed",
            exc=exc,
        )
        await _add_event(db, job.id, "llm_fail", level="warn", payload={"phase": "verify"})
        await db.commit()
        return
    _apply_lemma_verify(ready, payload)
    await _add_event(
        db, job.id, "llm_ok",
        payload={"phase": "verify", "invalid": len(payload.get("invalid") or [])},
    )


def _finalize_analyze_verdicts(items: list[ImportJobItem]) -> None:
    """pending + lemma = ready; goły pending = failed. Nic nie zostaje w limbo."""
    for item in items:
        if item.verdict != "pending":
            continue
        if (item.lemma or "").strip():
            item.verdict = "ready"
            item.verdict_phase = item.verdict_phase or "analyze"
        else:
            item.verdict = "failed"
            item.reason_code = item.reason_code or "no_lemma"
            item.verdict_phase = "analyze"


async def _run_analyze(db: AsyncSession, job: ImportJob) -> None:
    profile = (
        await db.execute(select(LanguageProfile).where(LanguageProfile.id == job.profile_id))
    ).scalar_one_or_none()
    if profile is None:
        await _touch(
            db, job, status="failed", error_code="profile_missing",
            error_message="Language profile not found", finished_at=_now(),
        )
        await db.commit()
        return

    await _touch(
        db, job, status="analyzing", phase="analyze", stage="format",
        started_at=job.started_at or _now(), processed=0,
    )
    await _add_event(db, job.id, "analyze_started")
    await db.commit()

    if await _cancelled(db, job):
        await finalize_cancel(db, job)
        return

    meta = dict(job.input_meta or {})
    raw_text = meta.get("raw_text")
    items = (
        await db.execute(
            select(ImportJobItem)
            .where(ImportJobItem.job_id == job.id)
            .order_by(ImportJobItem.ordinal)
        )
    ).scalars().all()
    job.items = list(items)
    notes = [list(it.raw_note or []) for it in items]
    deck = RawImportDeck(
        kind=str(meta.get("kind") or "notes"),
        notes=notes,
        field_names=list(meta.get("field_names") or []) or None,
        raw_text=raw_text,
    )
    llm = LLMService()
    try:
        if deck.needs_format_analysis:
            deck = await ensure_deck_segmented(
                deck,
                app_lang=profile.app_lang,
                learning_lang=profile.learning_lang,
                llm=llm,
            )
            await _replace_items_from_notes(db, job, deck.notes)
            items = (
                await db.execute(
                    select(ImportJobItem)
                    .where(ImportJobItem.job_id == job.id)
                    .order_by(ImportJobItem.ordinal)
                )
            ).scalars().all()
            job.items = list(items)
    except ImportPackageError as exc:
        await _touch(
            db, job, status="failed", error_code="import_format",
            error_message=str(exc)[:2000], finished_at=_now(),
        )
        await _add_event(db, job.id, "llm_fail", level="error", payload={"phase": "format", "err": str(exc)})
        await db.commit()
        return
    except Exception as exc:
        logger.exception("import format failed job=%s", job.id)
        from app.services.app_log import log_event

        await log_event(
            level="error",
            category="import",
            event="import_format_failed",
            status="error",
            user_id=job.user_id,
            profile_id=job.profile_id,
            entity_type="import_job",
            entity_id=str(job.id),
            message="import format failed",
            exc=exc,
        )
        await _touch(
            db, job, status="failed", error_code="llm_fail",
            error_message=str(exc)[:2000], finished_at=_now(),
        )
        await _add_event(db, job.id, "llm_fail", level="error", payload={"phase": "format"})
        await db.commit()
        return

    if await _cancelled(db, job):
        await finalize_cancel(db, job)
        return

    if not items:
        await _touch(
            db, job, status="failed", error_code="import_empty",
            error_message="No words to import", finished_at=_now(),
        )
        await db.commit()
        return

    try:
        if job.mode == "preserve":
            await _analyze_preserve(db, job, profile, deck, llm)
        else:
            await _analyze_vocabulario(db, job, profile, items, llm)
    except Exception as exc:
        logger.exception("import analyze failed job=%s", job.id)
        from app.services.app_log import log_event

        await log_event(
            level="error",
            category="import",
            event="import_analyze_failed",
            status="error",
            user_id=job.user_id,
            profile_id=job.profile_id,
            entity_type="import_job",
            entity_id=str(job.id),
            message="import analyze failed",
            exc=exc,
        )
        await _touch(
            db, job, status="failed", error_code="llm_fail",
            error_message=str(exc)[:2000], finished_at=_now(),
        )
        await _add_event(db, job.id, "llm_fail", level="error", payload={"err": str(exc)[:500]})
        await db.commit()
        return

    if await _cancelled(db, job):
        await finalize_cancel(db, job)
        return

    items = (
        await db.execute(
            select(ImportJobItem)
            .where(ImportJobItem.job_id == job.id)
            .order_by(ImportJobItem.ordinal)
        )
    ).scalars().all()
    _finalize_analyze_verdicts(list(items))
    await _refresh_counts(job, list(items))
    await _touch(
        db, job, status="review", stage="review",
        processed=len(items), total=len(items),
        current_label=None, current_ordinal=None, current_attempt=0,
    )
    await _add_event(
        db, job.id, "analyze_finished",
        payload={
            "ready": job.ready_count,
            "duplicate": job.duplicate_count,
            "failed": job.failed_count,
        },
    )
    await db.commit()


async def _replace_items_from_notes(
    db: AsyncSession,
    job: ImportJob,
    notes: list[list[str]],
) -> None:
    existing = (
        await db.execute(select(ImportJobItem).where(ImportJobItem.job_id == job.id))
    ).scalars().all()
    for it in existing:
        await db.delete(it)
    await db.flush()
    for i, note in enumerate(notes):
        db.add(
            ImportJobItem(
                job_id=job.id,
                ordinal=i,
                raw_note=list(note),
                input_label=_note_label(note),
            )
        )
    job.total = len(notes)
    await db.flush()


async def _analyze_vocabulario(
    db: AsyncSession,
    job: ImportJob,
    profile: LanguageProfile,
    items: list[ImportJobItem],
    llm: LLMService,
) -> None:
    notes = [list(it.raw_note or []) for it in items]
    await _touch(db, job, stage="classify", total=len(items), processed=0)
    await _add_event(db, job.id, "llm_call", payload={"phase": "classify", "n": len(notes)})
    await db.commit()

    classified = await classify_notes_detailed(
        notes,
        app_lang=profile.app_lang,
        learning_lang=profile.learning_lang,
        llm=llm,
    )
    await _add_event(db, job.id, "llm_ok", payload={"phase": "classify", "n": len(classified)})

    if await _cancelled(db, job):
        return

    await _touch(db, job, stage="dedup", processed=0, total=len(items))
    await db.commit()

    seen: dict[str, UUID] = {}
    for idx, item in enumerate(items):
        if await _cancelled(db, job):
            return
        raw = classified[idx] if idx < len(classified) else {}
        await _touch(
            db, job, processed=idx, current_ordinal=idx,
            current_label=item.input_label, stage="dedup",
        )
        _apply_vocab_item(item, raw, profile.learning_lang)
        if item.verdict == "pending" and item.lemma:
            key = item.lemma.casefold()
            if key in seen:
                item.verdict = "duplicate"
                item.reason_code = "in_file_duplicate"
                item.verdict_phase = "analyze"
            else:
                existing = await find_card_anywhere(
                    db, job.user_id, job.profile_id, item.lemma, item.pos
                )
                if existing is not None:
                    item.verdict = "duplicate"
                    item.reason_code = "already_on_list"
                    item.existing_card_id = existing.id
                    item.verdict_phase = "analyze"
                else:
                    item.verdict = "ready"
                    item.verdict_phase = "analyze"
                    seen[key] = item.id
        elif item.verdict == "pending":
            item.verdict = "failed"
            item.reason_code = item.reason_code or "no_lemma"
            item.verdict_phase = "analyze"
        await _add_event(
            db, job.id, "item_verdict",
            item_id=item.id,
            payload={"verdict": item.verdict, "reason": item.reason_code},
        )
        if idx % 10 == 0:
            await db.commit()
    _finalize_analyze_verdicts(items)
    await _verify_ready_lemmas(db, job, items, llm, profile.learning_lang)
    await _refresh_counts(job, items)
    await db.commit()


def _strip_leading_article(text: str) -> str:
    parts = text.split()
    if len(parts) >= 2 and parts[0].casefold() in _LEADING_ARTICLES:
        return " ".join(parts[1:])
    folded = text.casefold()
    if folded.startswith("l'") or folded.startswith("l’"):
        return text[2:].lstrip()
    return text


_LATIN_VOWELS = frozenset("aeiouyáéíóúüàèìòùäöâêîôûæøåąęóýůаеёиоуыэюяіїє")


def _token_looks_like_word(token: str) -> bool:
    letters = sum(1 for ch in token if ch.isalpha())
    digits = sum(1 for ch in token if ch.isdigit())
    junk = sum(1 for ch in token if not ch.isalnum() and ch not in "-'’")
    if letters < 2:
        return False
    if digits > letters:
        return False
    if junk >= 2:
        return False
    if junk and junk >= letters:
        return False
    return True


def _is_cjk_heavy(text: str) -> bool:
    return any(
        "\u4e00" <= ch <= "\u9fff"
        or "\u3040" <= ch <= "\u30ff"
        or "\uac00" <= ch <= "\ud7af"
        for ch in text
    )


def _core_looks_like_lexeme(core: str) -> bool:
    """Czy rdzeń może być hasłem słownikowym — nie ppppp / 123 / xxxzzz."""
    letters = [ch.casefold() for ch in core if ch.isalpha()]
    if not letters:
        return False
    unique = set(letters)
    if _is_cjk_heavy(core):
        return not (len(letters) >= 3 and len(unique) == 1)
    if len(unique) == 1:
        return False
    if len(letters) >= 5:
        top = max(letters.count(ch) for ch in unique)
        if top / len(letters) >= 0.7:
            return False
    if not any(ch in _LATIN_VOWELS for ch in letters):
        return False
    if len(letters) >= 6 and len(unique) <= 2:
        return False
    return True


def _plain_import_headword(label: str) -> str | None:
    """Pojedyncze hasło do nauki — nie zdanie, nie liczba, nie śmieci z klawiatury."""
    text = (label or "").strip()
    if not text or len(text) > 80:
        return None
    if text.endswith((".", "?", "!", "。", "？", "！")):
        return None
    words = text.split()
    if not (1 <= len(words) <= 6):
        return None
    core = _strip_leading_article(text)
    if not core:
        return None
    if not all(_token_looks_like_word(tok) for tok in core.split()):
        return None
    if not _core_looks_like_lexeme(core):
        return None
    return text


def _reject_garbage_lemma(item: ImportJobItem, raw: dict[str, Any], head: str) -> None:
    item.verdict = "failed"
    item.reason_code = "llm_invalid"
    item.reason_detail = (raw.get("invalid_reason") or "not recognized")[:2000]
    item.verdict_phase = "analyze"
    item.lemma = head or None


def _apply_vocab_item(item: ImportJobItem, raw: dict[str, Any], learning_lang: str) -> None:
    head = (raw.get("headword_l2") or item.input_label or "").strip()
    if not raw.get("valid", True) or not head:
        fallback = _plain_import_headword(head or item.input_label or "")
        if fallback:
            item.lemma = fallback
            item.input_label = item.input_label or fallback
            item.entry_kind = "lemma"
            item.verdict = "pending"
            return
        _reject_garbage_lemma(item, raw, head)
        return
    lemma = _vocabulario_lemma(raw, learning_lang=learning_lang)
    if not lemma:
        item.verdict = "failed"
        item.reason_code = "no_lemma"
        item.reason_detail = (raw.get("invalid_reason") or "phrase without base_lemma")[:2000]
        item.lemma = head
        item.verdict_phase = "analyze"
        return
    if _plain_import_headword(lemma) is None:
        _reject_garbage_lemma(item, raw, lemma)
        return
    item.lemma = lemma
    item.gloss = (raw.get("gloss_l1") or "").strip() or None
    item.pos = raw.get("pos")
    item.entry_kind = "lemma"
    item.input_label = raw.get("input") or item.input_label or _note_input(list(item.raw_note or []))
    item.verdict = "pending"


async def _analyze_preserve(
    db: AsyncSession,
    job: ImportJob,
    profile: LanguageProfile,
    deck: RawImportDeck,
    llm: LLMService,
) -> None:
    await _touch(db, job, stage="layout", processed=0)
    await _add_event(db, job.id, "llm_call", payload={"phase": "layout"})
    await db.commit()
    result = await resolve_import_display_cards(
        deck,
        app_lang=profile.app_lang,
        learning_lang=profile.learning_lang,
        llm=llm,
    )
    cards = list(result.get("cards") or [])
    await _add_event(db, job.id, "llm_ok", payload={"phase": "layout", "n": len(cards)})
    if await _cancelled(db, job):
        return

    await _replace_items_from_notes(db, job, deck.notes)
    items = (
        await db.execute(
            select(ImportJobItem)
            .where(ImportJobItem.job_id == job.id)
            .order_by(ImportJobItem.ordinal)
        )
    ).scalars().all()
    await _touch(db, job, stage="dedup", processed=0, total=len(items))
    await db.commit()

    seen: set[str] = set()
    for idx, item in enumerate(items):
        if await _cancelled(db, job):
            return
        card = cards[idx] if idx < len(cards) else None
        await _touch(
            db, job, processed=idx, current_ordinal=idx,
            current_label=item.input_label, stage="dedup",
        )
        if card is None:
            item.verdict = "failed"
            item.reason_code = "llm_invalid"
            item.reason_detail = "no display card"
            item.verdict_phase = "analyze"
            continue
        lemma = (card.get("lemma_l2") or "").strip()
        item.lemma = lemma or None
        item.gloss = card.get("gloss_primary")
        item.display = card.get("display")
        item.entry_kind = "imported"
        if not lemma:
            item.verdict = "failed"
            item.reason_code = "no_lemma"
            item.verdict_phase = "analyze"
            continue
        if _plain_import_headword(lemma) is None:
            item.verdict = "failed"
            item.reason_code = "llm_invalid"
            item.reason_detail = "not a dictionary headword"
            item.verdict_phase = "analyze"
            continue
        key = lemma.casefold()
        if key in seen:
            item.verdict = "duplicate"
            item.reason_code = "in_file_duplicate"
            item.verdict_phase = "analyze"
            continue
        existing = await find_card_anywhere(
            db, job.user_id, job.profile_id, lemma, "imported"
        )
        if existing is not None:
            item.verdict = "duplicate"
            item.reason_code = "already_on_list"
            item.existing_card_id = existing.id
            item.verdict_phase = "analyze"
            continue
        item.verdict = "ready"
        item.verdict_phase = "analyze"
        seen.add(key)
        if idx % 10 == 0:
            await db.commit()
    await _refresh_counts(job, list(items))
    await db.commit()


async def _run_commit(db: AsyncSession, job: ImportJob) -> None:
    profile = (
        await db.execute(select(LanguageProfile).where(LanguageProfile.id == job.profile_id))
    ).scalar_one_or_none()
    wl = (
        await db.execute(select(WordList).where(WordList.id == job.list_id))
    ).scalar_one_or_none()
    if profile is None or wl is None:
        await _touch(
            db, job, status="failed", error_code="list_not_found",
            error_message="List or profile missing", finished_at=_now(),
        )
        await db.commit()
        return

    items = (
        await db.execute(
            select(ImportJobItem)
            .where(ImportJobItem.job_id == job.id, ImportJobItem.verdict == "ready")
            .order_by(ImportJobItem.ordinal)
        )
    ).scalars().all()
    await _touch(db, job, stage="write", processed=0, total=len(items))
    await db.commit()

    created = 0
    for idx, item in enumerate(items):
        if await _cancelled(db, job):
            await finalize_cancel(db, job)
            return
        if item.created_card_id:
            live = (
                await db.execute(
                    select(LearningCard).where(
                        LearningCard.id == item.created_card_id,
                        LearningCard.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if live is not None:
                created += 1
                await _touch(db, job, processed=idx + 1, created_count=created)
                await db.commit()
                continue

        ok = False
        for attempt in range(1, COMMIT_MAX_ATTEMPTS + 1):
            if await _cancelled(db, job):
                await finalize_cancel(db, job)
                return
            item.attempt = attempt
            await _touch(
                db, job, stage="write", processed=idx,
                current_ordinal=item.ordinal,
                current_label=item.lemma or item.input_label,
                current_attempt=attempt,
            )
            await db.commit()
            try:
                card = await _create_card_for_item(db, job, profile, wl, item)
                item.created_card_id = card.id
                item.verdict_phase = "commit"
                item.last_error = None
                created += 1
                ok = True
                await _add_event(
                    db, job.id, "item_created", item_id=item.id,
                    payload={"card_id": str(card.id), "attempt": attempt},
                )
                await db.commit()
                if card.enrichment_status != STATUS_READY:
                    asyncio.create_task(enrich_card(card.id))
                break
            except DuplicateImportError as exc:
                item.verdict = "duplicate"
                item.reason_code = "already_on_list"
                item.existing_card_id = exc.card_id
                item.verdict_phase = "commit"
                await _add_event(
                    db, job.id, "item_verdict", item_id=item.id,
                    payload={"verdict": "duplicate", "phase": "commit"},
                )
                await db.commit()
                ok = True
                break
            except Exception as exc:
                item.last_error = str(exc)[:2000]
                await _add_event(
                    db, job.id, "item_retry", level="warn", item_id=item.id,
                    payload={
                        "attempt": attempt,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:500],
                    },
                )
                await db.commit()
                if attempt < COMMIT_MAX_ATTEMPTS:
                    await asyncio.sleep(COMMIT_BACKOFF_S[attempt - 1])
        if not ok:
            item.verdict = "failed"
            item.reason_code = "write_failed"
            item.reason_detail = item.last_error
            item.verdict_phase = "commit"
            await _add_event(
                db, job.id, "item_verdict", level="error", item_id=item.id,
                payload={"verdict": "failed", "reason": "write_failed"},
            )
            await db.commit()
        await _touch(db, job, processed=idx + 1, created_count=created)
        await db.commit()

    if await _cancelled(db, job):
        await finalize_cancel(db, job)
        return

    all_items = (
        await db.execute(select(ImportJobItem).where(ImportJobItem.job_id == job.id))
    ).scalars().all()
    await _refresh_counts(job, list(all_items))
    await _touch(
        db, job, status="done", stage="write",
        processed=job.total, created_count=created,
        finished_at=_now(), current_label=None, current_ordinal=None, current_attempt=0,
    )
    await _add_event(db, job.id, "commit_finished", payload={"created": created})
    await db.commit()


class DuplicateImportError(Exception):
    def __init__(self, card_id: UUID):
        super().__init__("duplicate")
        self.card_id = card_id


async def _create_card_for_item(
    db: AsyncSession,
    job: ImportJob,
    profile: LanguageProfile,
    wl: WordList,
    item: ImportJobItem,
) -> LearningCard:
    lemma = (item.lemma or "").strip()
    if not lemma:
        raise ValueError("empty lemma")
    pos = item.pos if job.mode != "preserve" else "imported"
    existing = await find_card_anywhere(db, job.user_id, job.profile_id, lemma, pos)
    if existing is not None:
        raise DuplicateImportError(existing.id)

    if job.mode == "preserve":
        content = build_import_display_content(
            lemma=lemma,
            gloss=item.gloss,
            learning_lang=profile.learning_lang,
            display=item.display or {},
        )
        status = STATUS_READY
    else:
        content = build_pending_content(
            lemma=lemma,
            pos=item.pos,
            gloss=item.gloss,
            learning_lang=profile.learning_lang,
            entry_kind=item.entry_kind or "lemma",
        )
        status = STATUS_PENDING

    card = LearningCard(
        user_id=job.user_id,
        profile_id=job.profile_id,
        deck_id=None if wl.is_system else wl.id,
        lemma_l2=lemma,
        pos=pos,
        gloss_primary=item.gloss,
        content=content,
        enrichment_status=status,
        import_job_id=job.id,
    )
    db.add(card)
    await db.flush()
    if wl.is_system:
        db.add(SrsState(card_id=card.id, scope="main", status="new"))
    if status == STATUS_PENDING:
        await hydrate_from_lexical_cache(db, card, profile)
    return card


async def resume_unfinished_jobs() -> None:
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(ImportJob.id).where(ImportJob.status.in_(ACTIVE_IMPORT_STATUSES))
            )
        ).scalars().all()
        for job_id in rows:
            await _add_event(db, job_id, "worker_resumed")
        if rows:
            await db.commit()
    for job_id in rows:
        spawn_job(job_id)


async def start_heartbeat_watchdog() -> None:
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL_S)
        try:
            await _watchdog_tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("import job watchdog failed")
            from app.services.app_log import log_event

            await log_event(
                level="error",
                category="import",
                event="import_watchdog_failed",
                status="error",
                message="import watchdog failed",
                exc=exc,
            )


async def _watchdog_tick() -> None:
    cutoff = datetime.now(UTC).timestamp() - HEARTBEAT_STALE_S
    async with async_session_factory() as db:
        jobs = (
            await db.execute(
                select(ImportJob).where(
                    ImportJob.status.in_(("queued", "analyzing", "committing", "cancelling"))
                )
            )
        ).scalars().all()
        stale: list[UUID] = []
        for job in jobs:
            hb = job.heartbeat_at
            if hb is None or hb.timestamp() < cutoff:
                if job.id not in _running:
                    await _add_event(db, job.id, "worker_heartbeat_stale", level="warn")
                    stale.append(job.id)
        if stale:
            await db.commit()
    for job_id in stale:
        spawn_job(job_id)

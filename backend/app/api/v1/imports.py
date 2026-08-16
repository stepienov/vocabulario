from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_admin_user, get_current_user
from app.core.http_errors import api_error
from app.db.session import get_db
from app.models import ImportJob, ImportJobEvent, ImportJobItem, LanguageProfile, User, WordList
from app.schemas import (
    ImportJobAdminResponse,
    ImportJobCommitRequest,
    ImportJobCreateRequest,
    ImportJobDetailResponse,
    ImportJobEventResponse,
    ImportJobItemResponse,
    ImportJobProgressResponse,
)
from app.services.import_jobs import (
    ActiveImportJobError,
    create_job_from_file,
    create_job_from_text,
    find_active_job,
    request_cancel,
    request_commit,
    spawn_job,
)
from app.services.import_package import ImportPackageError
from app.services.import_urls import ImportUrlError
from app.services.lexical import LexicalService

router = APIRouter(tags=["imports"])


async def _profile(db: AsyncSession, user: User, profile_id: UUID) -> LanguageProfile:
    try:
        return await LexicalService(db).get_profile(user.id, profile_id)
    except ValueError as exc:
        raise api_error(404, "profile_not_found", str(exc)) from exc


async def _list_for(
    db: AsyncSession, user: User, profile: LanguageProfile, list_id: UUID
) -> WordList:
    wl = (
        await db.execute(
            select(WordList).where(
                WordList.id == list_id,
                WordList.profile_id == profile.id,
                WordList.user_id == user.id,
                WordList.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if wl is None:
        raise api_error(404, "list_not_found", "List not found")
    return wl


async def _owned_job(db: AsyncSession, user: User, job_id: UUID) -> ImportJob:
    job = (
        await db.execute(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if job is None:
        raise api_error(404, "import_job_not_found", "Import job not found")
    return job


async def _list_name(db: AsyncSession, list_id: UUID) -> str | None:
    wl = (
        await db.execute(select(WordList).where(WordList.id == list_id))
    ).scalar_one_or_none()
    return wl.name if wl else None


def _progress(job: ImportJob, list_name: str | None = None) -> ImportJobProgressResponse:
    return ImportJobProgressResponse(
        job_id=job.id,
        status=job.status,
        phase=job.phase,
        stage=job.stage,
        source_name=job.source_name,
        mode=job.mode,
        list_id=job.list_id,
        list_name=list_name,
        processed=job.processed,
        total=job.total,
        current_ordinal=job.current_ordinal,
        current_label=job.current_label,
        current_attempt=job.current_attempt,
        ready_count=job.ready_count,
        duplicate_count=job.duplicate_count,
        failed_count=job.failed_count,
        created_count=job.created_count,
        cancel_requested=job.cancel_requested,
        error_code=job.error_code,
        error_message=job.error_message,
        heartbeat_at=job.heartbeat_at,
    )


def _item_out(it: ImportJobItem) -> ImportJobItemResponse:
    return ImportJobItemResponse(
        id=it.id,
        ordinal=it.ordinal,
        input_label=it.input_label,
        verdict=it.verdict,
        reason_code=it.reason_code,
        reason_detail=it.reason_detail,
        lemma=it.lemma,
        gloss=it.gloss,
        pos=it.pos,
        entry_kind=it.entry_kind,
        display=None,
        existing_card_id=it.existing_card_id,
        created_card_id=it.created_card_id,
        attempt=it.attempt,
    )


async def _detail(db: AsyncSession, job: ImportJob) -> ImportJobDetailResponse:
    items = (
        await db.execute(
            select(ImportJobItem)
            .where(ImportJobItem.job_id == job.id)
            .order_by(ImportJobItem.ordinal)
        )
    ).scalars().all()
    base = _progress(job, await _list_name(db, job.list_id))
    return ImportJobDetailResponse(**base.model_dump(), items=[_item_out(i) for i in items])


@router.post("/imports/jobs", response_model=ImportJobProgressResponse, status_code=202)
async def create_import_job(
    body: ImportJobCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _profile(db, user, body.profile_id)
    word_list = await _list_for(db, user, profile, body.list_id)
    try:
        job = await create_job_from_text(
            db,
            user=user,
            profile=profile,
            word_list=word_list,
            text=body.text,
            mode=body.mode,
        )
    except ActiveImportJobError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "import_job_active",
                "message": f"An import is already running: {exc.job_id}",
                "job_id": str(exc.job_id),
            },
        ) from exc
    except (ImportPackageError, ImportUrlError) as exc:
        raise api_error(400, "import_empty", str(exc)) from exc
    spawn_job(job.id)
    return _progress(job, word_list.name)


@router.post("/imports/jobs/file", response_model=ImportJobProgressResponse, status_code=202)
async def create_import_job_file(
    profile_id: UUID = Form(...),
    list_id: UUID = Form(...),
    mode: str = Form("vocabulario"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _profile(db, user, profile_id)
    word_list = await _list_for(db, user, profile, list_id)
    data = await file.read()
    try:
        job = await create_job_from_file(
            db,
            user=user,
            profile=profile,
            word_list=word_list,
            filename=file.filename or "import.bin",
            data=data,
            mode=mode,
        )
    except ActiveImportJobError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "import_job_active",
                "message": f"An import is already running: {exc.job_id}",
                "job_id": str(exc.job_id),
            },
        ) from exc
    except ImportPackageError as exc:
        raise api_error(400, "import_empty", str(exc)) from exc
    spawn_job(job.id)
    return _progress(job, word_list.name)


def _admin_job(job: ImportJob, list_name: str | None = None) -> ImportJobAdminResponse:
    base = _progress(job, list_name)
    return ImportJobAdminResponse(
        **base.model_dump(),
        user_id=job.user_id,
        profile_id=job.profile_id,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


@router.get("/imports/jobs", response_model=list[ImportJobAdminResponse])
async def list_import_jobs_admin(
    user_id: UUID | None = Query(None),
    status: str | None = Query(None),
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ImportJob)
    if user_id is not None:
        q = q.where(ImportJob.user_id == user_id)
    if status:
        q = q.where(ImportJob.status == status)
    if from_ts is not None:
        q = q.where(ImportJob.created_at >= from_ts)
    if to_ts is not None:
        q = q.where(ImportJob.created_at <= to_ts)
    q = q.order_by(ImportJob.created_at.desc()).limit(limit)
    jobs = (await db.execute(q)).scalars().all()
    return [_admin_job(job, await _list_name(db, job.list_id)) for job in jobs]


@router.get("/imports/jobs/{job_id}/events", response_model=list[ImportJobEventResponse])
async def list_import_job_events(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = (
        await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise api_error(404, "import_job_not_found", "Import job not found")
    if job.user_id != user.id and (user.role or "").strip().lower() != "admin":
        raise api_error(403, "forbidden", "Not allowed")
    events = (
        await db.execute(
            select(ImportJobEvent)
            .where(ImportJobEvent.job_id == job_id)
            .order_by(ImportJobEvent.at)
        )
    ).scalars().all()
    return [
        ImportJobEventResponse(
            id=ev.id,
            job_id=ev.job_id,
            item_id=ev.item_id,
            at=ev.at,
            level=ev.level,
            event=ev.event,
            payload=ev.payload,
        )
        for ev in events
    ]


@router.get("/imports/jobs/active", response_model=ImportJobProgressResponse)
async def get_active_import_job(
    profile_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await find_active_job(db, user.id, profile_id)
    if job is None:
        raise api_error(404, "import_job_none", "No active import")
    return _progress(job, await _list_name(db, job.list_id))


@router.get("/imports/jobs/{job_id}/progress", response_model=ImportJobProgressResponse)
async def get_import_job_progress(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _owned_job(db, user, job_id)
    return _progress(job, await _list_name(db, job.list_id))


@router.get("/imports/jobs/{job_id}", response_model=ImportJobDetailResponse)
async def get_import_job(
    job_id: UUID,
    include_items: bool = Query(True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _owned_job(db, user, job_id)
    if not include_items:
        base = _progress(job, await _list_name(db, job.list_id))
        return ImportJobDetailResponse(**base.model_dump(), items=[])
    return await _detail(db, job)


@router.post("/imports/jobs/{job_id}/commit", response_model=ImportJobProgressResponse)
async def commit_import_job(
    job_id: UUID,
    body: ImportJobCommitRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _owned_job(db, user, job_id)
    try:
        job = await request_commit(db, job, (body.item_ids if body else None))
    except ValueError as exc:
        code = str(exc)
        raise api_error(400, code, code) from exc
    return _progress(job, await _list_name(db, job.list_id))


@router.post("/imports/jobs/{job_id}/cancel", response_model=ImportJobProgressResponse)
async def cancel_import_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _owned_job(db, user, job_id)
    job = await request_cancel(db, job)
    return _progress(job, await _list_name(db, job.list_id))

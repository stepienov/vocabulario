# -*- coding: utf-8 -*-
"""Import 8 list A2 na konto produkcyjne alextest@test.pl (bez plików „dokument”)."""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_tmp_listy_zip"

_env_path = ROOT / ".env"
_loaded: dict[str, str] = {}
for _line in _env_path.read_text(encoding="utf-8").splitlines():
    raw = _line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        continue
    k, v = raw.split("=", 1)
    _loaded[k.strip()] = v.strip().strip('"').strip("'")

prod = _loaded.get("PROD_DATABASE_URL")
if not prod:
    raise SystemExit("PROD_DATABASE_URL missing in .env")
os.environ["DATABASE_URL"] = prod
os.environ["ENVIRONMENT"] = "production"
os.environ["DEBUG"] = "false"
os.environ["LLM_MOCK"] = "false"
os.environ["PERSIST_WORDS"] = "true"
os.environ.setdefault("OPENAI_API_KEY", _loaded.get("OPENAI_API_KEY", ""))
os.environ.setdefault("LLM_PROVIDER", _loaded.get("LLM_PROVIDER", "openai"))
os.environ.setdefault(
    "LLM_LOOKUP_MODEL", _loaded.get("LLM_LOOKUP_MODEL", "gpt-5.6-terra")
)
os.environ.setdefault(
    "LLM_ENRICHMENT_MODEL", _loaded.get("LLM_ENRICHMENT_MODEL", "gpt-5.6-terra")
)
os.environ.setdefault("LLM_LIGHT_MODEL", _loaded.get("LLM_LIGHT_MODEL", "gpt-5.6-luna"))
os.environ.setdefault("JWT_SECRET", _loaded.get("JWT_SECRET", "unused"))

sys.path.insert(0, str(ROOT / "backend"))

EMAIL = "alextest@test.pl"
LISTS = [
    ("a2 1-10.txt", "a2 1-10"),
    ("a2 11-20.txt", "a2 11-20"),
    ("a2 21-30.txt", "a2 21-30"),
    ("a2 31-40.txt", "a2 31-40"),
    ("a2 41-50.txt", "a2 41-50"),
    ("a2 51-60.txt", "a2 51-60"),
    ("a2 61-70.txt", "a2 61-70"),
    ("a2 71-80.txt", "a2 71-80"),
]
LEMMA_FIXES = {
    "el sonnido": "el sonido",
    "egoista": "egoísta",
    "(com)portarse": "comportarse",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def strip_notes(lemma: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\s*\([^)]*\)", "", lemma)).strip()


def clean_file_text(path: Path) -> str:
    rows: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or ";" not in line:
            continue
        l2, l1 = line.split(";", 1)
        l2, l1 = l2.strip(), l1.strip()
        l2 = LEMMA_FIXES.get(l2, l2)
        l2 = strip_notes(l2)
        rows.append(f"{l2};{l1}")
    if len(rows) != 30:
        raise SystemExit(f"{path.name}: expected 30 rows, got {len(rows)}")
    return "\n".join(rows)


async def load_user_profile(db):
    from sqlalchemy import select

    from app.models import LanguageProfile, User

    user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
    profile = (
        await db.execute(
            select(LanguageProfile).where(
                LanguageProfile.user_id == user.id,
                LanguageProfile.learning_lang == "es",
            )
        )
    ).scalar_one()
    return user, profile


async def get_or_create_list(db, user, profile, name: str):
    from sqlalchemy import func, select

    from app.models import LearningCard, WordList

    wl = (
        await db.execute(
            select(WordList).where(
                WordList.user_id == user.id,
                WordList.profile_id == profile.id,
                func.lower(WordList.name) == name.lower(),
                WordList.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if wl is None:
        wl = WordList(
            user_id=user.id,
            profile_id=profile.id,
            name=name,
            is_system=False,
            is_pending_inbox=False,
        )
        db.add(wl)
        await db.commit()
        await db.refresh(wl)
        log(f"created list {name!r} {wl.id}")
        return wl, 0
    n = int(
        (
            await db.execute(
                select(func.count())
                .select_from(LearningCard)
                .where(
                    LearningCard.deck_id == wl.id,
                    LearningCard.deleted_at.is_(None),
                )
            )
        ).scalar_one()
    )
    log(f"reuse list {name!r} {wl.id} cards={n}")
    return wl, n


async def import_one(filename: str, list_name: str, text: str) -> None:
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models import ImportJob, ImportJobItem
    from app.services.import_jobs import create_job_from_text, request_commit, run_import_job

    async with async_session_factory() as db:
        user, profile = await load_user_profile(db)
        wl, n = await get_or_create_list(db, user, profile, list_name)
        if n >= 30:
            log(f"SKIP {list_name} — already {n} cards")
            return
        log(f"ANALYZE {list_name} ({filename})")
        job = await create_job_from_text(
            db,
            user=user,
            profile=profile,
            word_list=wl,
            text=text,
            mode="vocabulario",
        )
        job_id = job.id
        log(f"  job {job_id} queued")

    await run_import_job(job_id)

    async with async_session_factory() as db:
        job = (await db.execute(select(ImportJob).where(ImportJob.id == job_id))).scalar_one()
        items = (
            await db.execute(
                select(ImportJobItem)
                .where(ImportJobItem.job_id == job_id)
                .order_by(ImportJobItem.ordinal)
            )
        ).scalars().all()
        log(
            f"  after analyze status={job.status} ready={job.ready_count} "
            f"dup={job.duplicate_count} fail={job.failed_count}"
        )
        for it in items:
            if it.verdict != "ready":
                log(
                    f"    ! {it.verdict:10s} {it.reason_code or '-':18s} "
                    f"{it.lemma or it.input_label!r}"
                )
        if job.status != "review":
            raise RuntimeError(f"{list_name}: expected review, got {job.status} {job.error_message}")
        if job.ready_count < 1:
            raise RuntimeError(f"{list_name}: nothing to commit")
        await request_commit(db, job, None)
        log(f"  COMMIT started ({job.ready_count} ready)")

    for _ in range(180):
        await asyncio.sleep(2)
        async with async_session_factory() as db:
            job = (
                await db.execute(select(ImportJob).where(ImportJob.id == job_id))
            ).scalar_one()
            if job.status in {"done", "failed", "cancelled"}:
                log(
                    f"  commit {job.status} created={job.created_count} "
                    f"fail={job.failed_count} err={job.error_message}"
                )
                if job.status != "done":
                    raise RuntimeError(f"{list_name} commit {job.status}")
                return
    raise TimeoutError(f"{list_name} commit timed out")


async def summarize() -> None:
    from sqlalchemy import func, select

    from app.db.session import async_session_factory
    from app.models import LearningCard, WordList

    async with async_session_factory() as db:
        user, profile = await load_user_profile(db)
        log("\n=== SUMMARY ===")
        for _, name in LISTS:
            wl = (
                await db.execute(
                    select(WordList).where(
                        WordList.user_id == user.id,
                        WordList.profile_id == profile.id,
                        func.lower(WordList.name) == name.lower(),
                        WordList.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if wl is None:
                log(f"{name}: MISSING")
                continue
            rows = (
                await db.execute(
                    select(LearningCard.enrichment_status, func.count())
                    .where(
                        LearningCard.deck_id == wl.id,
                        LearningCard.deleted_at.is_(None),
                    )
                    .group_by(LearningCard.enrichment_status)
                )
            ).all()
            counts = {s: int(n) for s, n in rows}
            total = sum(counts.values())
            log(f"{name}: {total} cards  {counts}")


async def wait_enrichment(timeout_s: int = 5400) -> None:
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    from app.db.session import async_session_factory
    from app.models import LearningCard, WordList
    from app.services.card_jobs import resume_pending_enrichment

    deadline = datetime.now(UTC).timestamp() + timeout_s
    names = {n.lower() for _, n in LISTS}
    while datetime.now(UTC).timestamp() < deadline:
        await resume_pending_enrichment(stale_only=False)
        async with async_session_factory() as db:
            user, profile = await load_user_profile(db)
            lists = (
                await db.execute(
                    select(WordList).where(
                        WordList.user_id == user.id,
                        WordList.profile_id == profile.id,
                        WordList.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            pending = 0
            total = 0
            parts = []
            for wl in lists:
                if wl.name.lower() not in names:
                    continue
                rows = (
                    await db.execute(
                        select(LearningCard.enrichment_status, func.count())
                        .where(
                            LearningCard.deck_id == wl.id,
                            LearningCard.deleted_at.is_(None),
                        )
                        .group_by(LearningCard.enrichment_status)
                    )
                ).all()
                counts = {s: int(n) for s, n in rows}
                n = sum(counts.values())
                total += n
                p = sum(
                    c
                    for s, c in counts.items()
                    if s in {"pending", "preparing", "prep_problem"}
                )
                pending += p
                parts.append(f"{wl.name}:{counts}")
            log(f"enrichment pending={pending}/{total}  " + " | ".join(parts))
            if total >= 240 and pending == 0:
                return
        await asyncio.sleep(20)
    log("enrichment wait timed out")


async def main() -> None:
    cleaned = {fn: clean_file_text(SRC / fn) for fn, _ in LISTS}
    for filename, list_name in LISTS:
        await import_one(filename, list_name, cleaned[filename])
    await summarize()
    log("waiting for enrichment (production + local workers)...")
    await wait_enrichment()
    await summarize()
    log("done")


if __name__ == "__main__":
    asyncio.run(main())

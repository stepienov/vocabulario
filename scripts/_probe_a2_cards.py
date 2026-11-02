# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_env_path = ROOT / ".env"
_loaded: dict[str, str] = {}
for _line in _env_path.read_text(encoding="utf-8").splitlines():
    raw = _line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        continue
    k, v = raw.split("=", 1)
    _loaded[k.strip()] = v.strip().strip('"').strip("'")
os.environ["DATABASE_URL"] = _loaded["PROD_DATABASE_URL"]
os.environ["ENVIRONMENT"] = "production"
os.environ["LLM_MOCK"] = "false"
os.environ["PERSIST_WORDS"] = "true"
os.environ.setdefault("OPENAI_API_KEY", _loaded.get("OPENAI_API_KEY", ""))
os.environ.setdefault("JWT_SECRET", _loaded.get("JWT_SECRET", "unused"))
sys.path.insert(0, str(ROOT / "backend"))

EMAIL = "alextest@test.pl"


async def main() -> None:
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models import ImportJob, LearningCard, User, WordList

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
        lists = (
            await db.execute(
                select(WordList).where(
                    WordList.user_id == user.id,
                    WordList.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for wl in lists:
            print(f"\nLIST {wl.name!r} {wl.id}", flush=True)
            cards = (
                await db.execute(
                    select(LearningCard)
                    .where(
                        LearningCard.deck_id == wl.id,
                        LearningCard.deleted_at.is_(None),
                    )
                    .order_by(LearningCard.created_at)
                )
            ).scalars().all()
            for c in cards:
                print(
                    f"  {c.lemma_l2!r:30s} pos={c.pos!r:12s} "
                    f"status={c.enrichment_status:12s} gloss={c.gloss_primary!r}",
                    flush=True,
                )
        jobs = (
            await db.execute(
                select(ImportJob)
                .where(ImportJob.user_id == user.id)
                .order_by(ImportJob.created_at.desc())
                .limit(10)
            )
        ).scalars().all()
        print("\nJOBS", flush=True)
        for j in jobs:
            print(
                f"  {j.created_at} {j.status:12s} {j.source_name!r} "
                f"list={j.list_id} ready={j.ready_count} dup={j.duplicate_count} "
                f"fail={j.failed_count} created={j.created_count}",
                flush=True,
            )


if __name__ == "__main__":
    asyncio.run(main())

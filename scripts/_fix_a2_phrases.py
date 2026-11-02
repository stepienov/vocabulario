# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
loaded: dict[str, str] = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    loaded[k.strip()] = v.strip().strip('"').strip("'")
os.environ["DATABASE_URL"] = loaded["PROD_DATABASE_URL"]
os.environ["ENVIRONMENT"] = "production"
os.environ["LLM_MOCK"] = "false"
os.environ["PERSIST_WORDS"] = "true"
os.environ.setdefault("OPENAI_API_KEY", loaded.get("OPENAI_API_KEY", ""))
os.environ.setdefault("JWT_SECRET", loaded.get("JWT_SECRET", "x"))
sys.path.insert(0, str(ROOT / "backend"))

EMAIL = "alextest@test.pl"
LEMMAS = ("pedir perdón", "tener prisa", "tener sueño")


async def main() -> None:
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models import LanguageProfile, LearningCard, User
    from app.services.card_jobs import (
        hydrate_from_lexical_cache,
        request_manual_enrichment_retry,
        spawn_enrich,
    )

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
        cards = (
            await db.execute(
                select(LearningCard).where(
                    LearningCard.user_id == user.id,
                    LearningCard.deleted_at.is_(None),
                    LearningCard.lemma_l2.in_(LEMMAS),
                )
            )
        ).scalars().all()
        for card in cards:
            profile = (
                await db.execute(
                    select(LanguageProfile).where(LanguageProfile.id == card.profile_id)
                )
            ).scalar_one()
            print(
                f"fix {card.lemma_l2!r} status={card.enrichment_status}",
                flush=True,
            )
            ok = await hydrate_from_lexical_cache(db, card, profile)
            if ok:
                print(f"  cache hit → {card.enrichment_status}", flush=True)
                await db.commit()
                continue
            print("  no cache, manual retry", flush=True)
            await request_manual_enrichment_retry(db, card)
            await db.commit()
            spawn_enrich(card.id)

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
        rows = (
            await db.execute(
                select(LearningCard).where(
                    LearningCard.user_id == user.id,
                    LearningCard.lemma_l2.in_(LEMMAS),
                    LearningCard.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for c in rows:
            print(f"after {c.lemma_l2!r} {c.enrichment_status}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

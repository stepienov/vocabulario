"""Force LLM re-enrich bypassing lexical cache."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_env = Path(__file__).resolve().parents[1] / ".env"
for line in _env.read_text(encoding="utf-8").splitlines():
    if line.startswith("PROD_DATABASE_URL="):
        os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()
        break
else:
    raise SystemExit("PROD_DATABASE_URL missing")

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("LLM_MOCK", "false")

EMAIL = "alextest@test.pl"
LEMMA = "tener que"


async def main() -> None:
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models import LanguageProfile, LearningCard, User
    from app.services.enrichment import enrich_adaptive_card_content

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
        card = (
            await db.execute(
                select(LearningCard)
                .where(
                    LearningCard.user_id == user.id,
                    LearningCard.lemma_l2 == LEMMA,
                    LearningCard.deleted_at.is_(None),
                )
                .order_by(LearningCard.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        profile = (
            await db.execute(
                select(LanguageProfile).where(LanguageProfile.id == card.profile_id)
            )
        ).scalar_one()

        print(f"LLM enrich (no cache) card={card.id} {LEMMA!r}")
        content = await enrich_adaptive_card_content(
            profile,
            headword=LEMMA,
            entry_kind="construction",
            gloss="mieć obowiązek",
            pos="verb",
            base_lemma="tener",
            pattern="tener que + infinitivo",
        )
        meanings = content.get("meanings") or []
        examples = sum(len(m.get("examples") or []) for m in meanings if isinstance(m, dict))
        gloss = meanings[0].get("gloss_l1") if meanings else None

        card.content = content
        card.lexical_entry_id = None
        card.pos = content.get("pos") or card.pos
        card.gloss_primary = gloss or card.gloss_primary
        card.enrichment_status = "ready"
        card.enrichment_error = None
        await db.commit()

        ok = len(meanings) >= 1 and examples >= 1 and bool(gloss)
        print(
            f"status=ready schema={content.get('schema_version')!r} "
            f"meanings={len(meanings)} examples={examples} gloss={gloss!r} ok={ok}"
        )
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

"""Live probe: raw LLM vs filtered final for known FAIL queries."""
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select, text

from app.db.session import async_session_factory
from app.models import LanguageProfile, User
from app.services.lexical import LexicalService
from app.services.lookup_candidates import normalize_lookup_query

QUERIES = ["droga", "drog", "cara", "casa"]


async def main() -> None:
    async with async_session_factory() as db:
        profile = (
            await db.execute(
                select(LanguageProfile).where(
                    LanguageProfile.app_lang == "pl",
                    LanguageProfile.learning_lang == "es",
                )
            )
        ).scalars().first()
        if profile is None:
            raise SystemExit("brak profilu pl>es")
        user = (
            await db.execute(select(User).where(User.id == profile.user_id))
        ).scalar_one()
        keys = [normalize_lookup_query(q) for q in QUERIES]
        await db.execute(
            text(
                "delete from lookup_query_cache where lang_pair = 'pl>es' and input_norm = any(:k)"
            ),
            {"k": keys},
        )
        await db.commit()
        db.expunge(user)
        profile_id = profile.id

    async with async_session_factory() as db:
        service = LexicalService(db)
        for query in QUERIES:
            t0 = datetime.now(UTC)
            outcome = await service.lookup_cached(
                user, profile_id, query, annotate=False
            )
            await db.commit()
            raw_row = (
                await db.execute(
                    text(
                        """
                        select u.prompt_tokens, u.completion_tokens, u.status,
                               p.response_json
                        from llm_usage u
                        left join llm_call_payloads p on p.llm_usage_id = u.id
                        where u.query = :q
                          and u.created_at >= :t
                          and u.purpose = 'lookup_draft'
                        order by u.created_at desc
                        limit 1
                        """
                    ),
                    {"q": query, "t": t0},
                )
            ).mappings().first()
            print(f"==== {query} source={outcome.source} n={len(outcome.candidates)}")
            if raw_row:
                print(
                    f"tokens in/out {raw_row['prompt_tokens']}/"
                    f"{raw_row['completion_tokens']} {raw_row['status']}"
                )
                cands = (raw_row["response_json"] or {}).get("candidates") or []
                print("RAW:")
                for cand in cands:
                    print(" ", json.dumps(cand, ensure_ascii=False))
            print("FINAL:")
            for cand in outcome.candidates:
                print(
                    f"  {cand.get('lemma')}/{cand.get('pos')}/{cand.get('gloss')}"
                )
            print()
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())

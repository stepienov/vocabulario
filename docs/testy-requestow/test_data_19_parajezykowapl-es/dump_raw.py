"""Surowe odpowiedzi modelu z iteracji 1, bez nowego pytania."""
import asyncio
import json

from datetime import UTC, datetime

from sqlalchemy import text

from app.db.session import async_session_factory

START = datetime(2026, 11, 8, 20, 2, 57, tzinfo=UTC)


async def main():
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                text(
                    """
                    select u.created_at, u.purpose, u.query, u.lang_pair,
                           u.prompt_tokens, u.completion_tokens, u.status,
                           p.response_json
                    from llm_usage u
                    left join llm_call_payloads p on p.llm_usage_id = u.id
                    where u.created_at >= :start
                      and u.purpose in ('lookup_draft', 'lookup_expand')
                    order by u.created_at
                    """
                ),
                {"start": START},
            )
        ).mappings().all()
    print(f"rows {len(rows)}")
    for row in rows:
        payload = row["response_json"] or {}
        text_out = json.dumps(payload, ensure_ascii=False)
        print(
            f"{row['created_at']} {row['purpose']} q={row['query']!r} "
            f"pair={row['lang_pair']} in={row['prompt_tokens']} out={row['completion_tokens']} {row['status']}"
        )
        print(text_out[:900])
        print("---")


asyncio.run(main())

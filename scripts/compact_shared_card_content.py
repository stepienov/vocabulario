"""Safely release exact duplicate LearningCard.content snapshots.

Dry-run by default. Writing requires both --apply and the exact database name.
Conflicting snapshots and cards without an exact unique lexical entry are left untouched.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def run(*, apply: bool, confirmed_database: str | None) -> None:
    from app.core.config import get_settings
    from app.services.shared_content import compact_exact_card_copies, shared_content_copy_counts

    engine = create_async_engine(get_settings().database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            database = (await db.execute(text("SELECT current_database()"))).scalar_one()
            print(f"database={database}")
            before = await shared_content_copy_counts(db)
            print(f"before={before}")
            if not apply:
                await db.rollback()
                print("dry-run; pass --apply and --confirm-database to write")
                return
            if confirmed_database != database:
                raise SystemExit("--confirm-database must exactly match the connected database")

            linked, cleared = await compact_exact_card_copies(db)
            after = await shared_content_copy_counts(db)
            print(f"linked_exact_unlinked_cards={linked} cleared_exact_snapshots={cleared}")
            print(f"after={after}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write exact, unambiguous matches")
    parser.add_argument("--confirm-database", help="Exact current_database() name required with --apply")
    args = parser.parse_args()
    if args.confirm_database and not args.apply:
        parser.error("--confirm-database is only valid with --apply")
    asyncio.run(run(apply=args.apply, confirmed_database=args.confirm_database))


if __name__ == "__main__":
    main()

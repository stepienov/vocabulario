"""Wyrównanie starych list wyrazów pokrewnych do wspólnych rodzin — bez LLM.

Domyślnie dry-run (nic nie zapisuje). Zapis: --apply
Produkcja: --prod (czyta PROD_DATABASE_URL z .env)

Przykłady:
  python scripts/backfill_word_families.py --lang-pair pl>es
  python scripts/backfill_word_families.py --lang-pair pl>es --apply
  python scripts/backfill_word_families.py --prod --fill-articles
  python scripts/backfill_word_families.py --prod --fill-articles --apply
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _load_env_value(key: str) -> str | None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def _configure_database(*, prod: bool) -> None:
    if prod:
        url = _load_env_value("PROD_DATABASE_URL")
        if not url:
            raise SystemExit("PROD_DATABASE_URL missing in .env")
        os.environ["DATABASE_URL"] = url
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("LLM_MOCK", "true")


def _print_fill_report(report) -> None:
    print(
        f"pair={report.lang_pair} needing={report.members_needing} "
        f"filled={report.members_filled} families={report.families_projected}"
    )
    for example in report.examples:
        print(f"  {example}")


def _print_report(report) -> None:
    print(
        f"pair={report.lang_pair} entries={report.entries_seen} "
        f"skipped_non_lemma={report.skipped_non_lemma} families={report.families} "
        f"members={report.members} singleton_skipped={report.singleton_skipped} "
        f"cards={report.cards_patched} orphans={report.orphan_cards_patched}"
    )
    for example in report.examples:
        print(f"  {example}")


async def _run(args: argparse.Namespace) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import get_settings
    from app.services.word_families import fill_missing_family_articles
    from app.services.word_family_backfill import backfill_lang_pair, list_lang_pairs

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    dry_run = not args.apply
    if dry_run:
        print("dry-run (pass --apply to write)")
    else:
        print("APPLY — writing to DB")

    async with factory() as db:
        pairs = [args.lang_pair] if args.lang_pair else await list_lang_pairs(db)
        if not pairs:
            print("no lang pairs found")
            return
        for pair in pairs:
            if args.fill_articles:
                report = await fill_missing_family_articles(
                    db, pair, dry_run=dry_run
                )
                _print_fill_report(report)
            else:
                report = await backfill_lang_pair(
                    db, pair, dry_run=dry_run, limit=args.limit
                )
                _print_report(report)
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang-pair", help="Only this pair, e.g. pl>es")
    parser.add_argument("--limit", type=int, default=None, help="Max lexical entries (smoke test)")
    parser.add_argument("--apply", action="store_true", help="Write to DB (default is dry-run)")
    parser.add_argument("--prod", action="store_true", help="Use PROD_DATABASE_URL from .env")
    parser.add_argument(
        "--fill-articles",
        action="store_true",
        help="Only fill missing citation articles on family members (no rebuild)",
    )
    args = parser.parse_args()
    _configure_database(prod=args.prod)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

"""Lekkie, idempotentne migracje kolumn.

`Base.metadata.create_all` zakłada nowe tabele, ale nie dodaje kolumn do tych,
które już istnieją. Dopóki projekt nie ma Alembica, brakujące kolumny dokładamy
tutaj — każda instrukcja jest bezpieczna przy wielokrotnym uruchomieniu.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_STATEMENTS = (
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_status VARCHAR(16) NOT NULL DEFAULT 'ready'",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_error VARCHAR(500)",
    "CREATE INDEX IF NOT EXISTS ix_learning_cards_enrichment_status "
    "ON learning_cards (enrichment_status)",
    "ALTER TABLE favorite_words ADD COLUMN IF NOT EXISTS "
    "enrichment_status VARCHAR(16) NOT NULL DEFAULT 'ready'",
    "CREATE INDEX IF NOT EXISTS ix_favorite_words_enrichment_status "
    "ON favorite_words (enrichment_status)",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_usages BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_synonyms_antonyms BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_periphrases BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "conjugation_expanded_default BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_example_sentences BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "related_words_expanded_default BOOLEAN NOT NULL DEFAULT false",
)


async def run_migrations(conn: AsyncConnection) -> None:
    for statement in _STATEMENTS:
        await conn.execute(text(statement))

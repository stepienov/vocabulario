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
    "ALTER TABLE learning_cards DROP COLUMN IF EXISTS is_favorite",
    "DROP TABLE IF EXISTS favorite_words",
    "ALTER TABLE word_lists ADD COLUMN IF NOT EXISTS "
    "is_pending_inbox BOOLEAN NOT NULL DEFAULT false",
    "CREATE TABLE IF NOT EXISTS applied_sync_moves ("
    "client_id UUID PRIMARY KEY, "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "card_id UUID NOT NULL REFERENCES learning_cards(id) ON DELETE CASCADE, "
    "moved_at TIMESTAMPTZ NOT NULL, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_applied_sync_moves_card_id "
    "ON applied_sync_moves (card_id)",
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
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_synonyms BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_antonyms BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_word_family BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "show_conjugation BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE srs_state ADD COLUMN IF NOT EXISTS stability DOUBLE PRECISION",
    "ALTER TABLE srs_state ADD COLUMN IF NOT EXISTS difficulty DOUBLE PRECISION",
    "ALTER TABLE srs_state ADD COLUMN IF NOT EXISTS fsrs_step INTEGER",
    "ALTER TABLE review_logs ADD COLUMN IF NOT EXISTS client_id UUID",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_review_logs_client_id "
    "ON review_logs (client_id) WHERE client_id IS NOT NULL",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "content_review_status VARCHAR(32)",
    "CREATE TABLE IF NOT EXISTS card_corrections ("
    "id UUID PRIMARY KEY, "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "card_id UUID NOT NULL REFERENCES learning_cards(id) ON DELETE CASCADE, "
    "sections JSONB NOT NULL, "
    "note VARCHAR(2000), "
    "status VARCHAR(32) NOT NULL DEFAULT 'reported', "
    "reason VARCHAR(2000), "
    "patch JSONB, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
    "resolved_at TIMESTAMPTZ"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_card_corrections_card_id ON card_corrections (card_id)",
    "CREATE TABLE IF NOT EXISTS device_tokens ("
    "token VARCHAR(512) PRIMARY KEY, "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "platform VARCHAR(16) NOT NULL DEFAULT 'android', "
    "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    ")",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "study_reminder_enabled BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "cards_ready_push_enabled BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS "
    "reminder_hour INTEGER NOT NULL DEFAULT 19",
    # LSP: native_lang → app_lang + tense_label_lang on language_profiles
    "DO $$ BEGIN "
    "IF EXISTS (SELECT 1 FROM information_schema.columns "
    "WHERE table_name = 'language_profiles' AND column_name = 'native_lang') "
    "THEN ALTER TABLE language_profiles RENAME COLUMN native_lang TO app_lang; "
    "END IF; END $$",
    "ALTER TABLE language_profiles ADD COLUMN IF NOT EXISTS "
    "tense_label_lang VARCHAR(16) NOT NULL DEFAULT 'app_lang'",
    "ALTER TABLE language_profiles DROP CONSTRAINT IF EXISTS "
    "language_profiles_user_id_native_lang_learning_lang_key",
    "ALTER TABLE language_profiles DROP CONSTRAINT IF EXISTS "
    "uq_language_profiles_user_id_native_lang_learning_lang",
    "DO $$ BEGIN "
    "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = "
    "'language_profiles_user_id_app_lang_learning_lang_key') THEN "
    "ALTER TABLE language_profiles ADD CONSTRAINT "
    "language_profiles_user_id_app_lang_learning_lang_key "
    "UNIQUE (user_id, app_lang, learning_lang); "
    "END IF; END $$",
    "ALTER TABLE users DROP COLUMN IF EXISTS ui_lang",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "card_activity_status VARCHAR(32)",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "has_content_changes BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE card_corrections ADD COLUMN IF NOT EXISTS "
    "result_code VARCHAR(64)",
    "CREATE TABLE IF NOT EXISTS card_history_events ("
    "id UUID PRIMARY KEY, "
    "card_id UUID NOT NULL REFERENCES learning_cards(id) ON DELETE CASCADE, "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "event_type VARCHAR(64) NOT NULL, "
    "actor VARCHAR(16) NOT NULL, "
    "result_code VARCHAR(64), "
    "summary VARCHAR(2000), "
    "payload JSONB, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_card_history_events_card_id "
    "ON card_history_events (card_id)",
    "CREATE TABLE IF NOT EXISTS admin_card_reviews ("
    "id UUID PRIMARY KEY, "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "card_id UUID NOT NULL REFERENCES learning_cards(id) ON DELETE CASCADE, "
    "source VARCHAR(32) NOT NULL, "
    "source_id UUID, "
    "learning_lang VARCHAR(8), "
    "before_snapshot JSONB, "
    "after_snapshot JSONB, "
    "ai_verdict VARCHAR(32) NOT NULL DEFAULT 'pending', "
    "ai_reason VARCHAR(2000), "
    "admin_status VARCHAR(32) NOT NULL DEFAULT 'pending', "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_admin_card_reviews_card_id "
    "ON admin_card_reviews (card_id)",
    # --- Offline-first: soft-delete + tombstones + incremental pull ---
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_learning_cards_deleted_at "
    "ON learning_cards (deleted_at)",
    "ALTER TABLE word_lists ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "ALTER TABLE word_lists ADD COLUMN IF NOT EXISTS "
    "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "CREATE INDEX IF NOT EXISTS ix_word_lists_deleted_at "
    "ON word_lists (deleted_at)",
    # Replace full unique constraints with partial (live-rows-only) unique indexes so
    # a soft-deleted row no longer blocks re-adding the same card / list name.
    "DO $$ DECLARE c record; BEGIN "
    "FOR c IN SELECT conname FROM pg_constraint "
    "WHERE conrelid = 'learning_cards'::regclass AND contype = 'u' LOOP "
    "EXECUTE 'ALTER TABLE learning_cards DROP CONSTRAINT ' || quote_ident(c.conname); "
    "END LOOP; END $$",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_learning_cards_active "
    "ON learning_cards (user_id, profile_id, lemma_l2, pos, deck_id) "
    "WHERE deleted_at IS NULL",
    "DO $$ DECLARE c record; BEGIN "
    "FOR c IN SELECT conname FROM pg_constraint "
    "WHERE conrelid = 'word_lists'::regclass AND contype = 'u' LOOP "
    "EXECUTE 'ALTER TABLE word_lists DROP CONSTRAINT ' || quote_ident(c.conname); "
    "END LOOP; END $$",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_word_lists_profile_name_active "
    "ON word_lists (profile_id, name) WHERE deleted_at IS NULL",
    "CREATE TABLE IF NOT EXISTS applied_sync_ops ("
    "client_op_id UUID PRIMARY KEY, "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "op_type VARCHAR(32) NOT NULL, "
    "server_id UUID, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    ")",
)


async def run_migrations(conn: AsyncConnection) -> None:
    for statement in _STATEMENTS:
        await conn.execute(text(statement))

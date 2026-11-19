"""Lekkie, idempotentne migracje kolumn.

`Base.metadata.create_all` zakłada nowe tabele, ale nie dodaje kolumn do tych,
które już istnieją. Dopóki projekt nie ma Alembica, brakujące kolumny dokładamy
tutaj — każda instrukcja jest bezpieczna przy wielokrotnym uruchomieniu.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

# Stabilny klucz; sesyjny lock, żeby dwie repliki nie robiły DDL naraz.
_SCHEMA_LOCK_KEY = 872314559
_DEADLOCK_RETRIES = 8

_STATEMENTS = (
    "ALTER TABLE lookup_query_cache ADD COLUMN IF NOT EXISTS "
    "more_exhausted BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE lookup_more_operations ADD COLUMN IF NOT EXISTS "
    "lang_pair VARCHAR(16) NOT NULL DEFAULT ''",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_status VARCHAR(16) NOT NULL DEFAULT 'ready'",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_error VARCHAR(500)",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_side_retries INTEGER NOT NULL DEFAULT 0",
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
    "show_associations BOOLEAN NOT NULL DEFAULT true",
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
    "CREATE TABLE IF NOT EXISTS import_jobs ("
    "id UUID PRIMARY KEY, "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "profile_id UUID NOT NULL REFERENCES language_profiles(id) ON DELETE CASCADE, "
    "list_id UUID NOT NULL REFERENCES word_lists(id) ON DELETE CASCADE, "
    "phase VARCHAR(16) NOT NULL DEFAULT 'analyze', "
    "status VARCHAR(16) NOT NULL DEFAULT 'queued', "
    "stage VARCHAR(16) NOT NULL DEFAULT 'queued', "
    "source_kind VARCHAR(16) NOT NULL DEFAULT 'paste', "
    "source_name VARCHAR(255) NOT NULL DEFAULT '', "
    "mode VARCHAR(16) NOT NULL DEFAULT 'vocabulario', "
    "cancel_requested BOOLEAN NOT NULL DEFAULT false, "
    "processed INTEGER NOT NULL DEFAULT 0, "
    "total INTEGER NOT NULL DEFAULT 0, "
    "current_ordinal INTEGER, "
    "current_label VARCHAR(500), "
    "current_attempt INTEGER NOT NULL DEFAULT 0, "
    "ready_count INTEGER NOT NULL DEFAULT 0, "
    "duplicate_count INTEGER NOT NULL DEFAULT 0, "
    "failed_count INTEGER NOT NULL DEFAULT 0, "
    "created_count INTEGER NOT NULL DEFAULT 0, "
    "error_code VARCHAR(64), "
    "error_message VARCHAR(2000), "
    "started_at TIMESTAMPTZ, "
    "heartbeat_at TIMESTAMPTZ, "
    "finished_at TIMESTAMPTZ, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
    "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
    "input_sha256 VARCHAR(64), "
    "input_meta JSONB NOT NULL DEFAULT '{}'::jsonb"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_import_jobs_user_created "
    "ON import_jobs (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_import_jobs_status ON import_jobs (status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_import_jobs_one_active "
    "ON import_jobs (user_id, profile_id) "
    "WHERE status IN ('queued','analyzing','review','committing','cancelling')",
    "CREATE TABLE IF NOT EXISTS import_job_items ("
    "id UUID PRIMARY KEY, "
    "job_id UUID NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE, "
    "ordinal INTEGER NOT NULL, "
    "raw_note JSONB NOT NULL DEFAULT '[]'::jsonb, "
    "input_label VARCHAR(500) NOT NULL DEFAULT '', "
    "verdict VARCHAR(16) NOT NULL DEFAULT 'pending', "
    "verdict_phase VARCHAR(16), "
    "reason_code VARCHAR(64), "
    "reason_detail VARCHAR(2000), "
    "lemma VARCHAR(255), "
    "pos VARCHAR(32), "
    "gloss VARCHAR(255), "
    "entry_kind VARCHAR(32), "
    "lexical_entry_id UUID, "
    "display JSONB, "
    "existing_card_id UUID, "
    "created_card_id UUID, "
    "attempt INTEGER NOT NULL DEFAULT 0, "
    "last_error VARCHAR(2000), "
    "UNIQUE (job_id, ordinal)"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_import_job_items_job_id ON import_job_items (job_id)",
    "CREATE TABLE IF NOT EXISTS import_job_events ("
    "id UUID PRIMARY KEY, "
    "job_id UUID NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE, "
    "item_id UUID, "
    "at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
    "level VARCHAR(8) NOT NULL DEFAULT 'info', "
    "event VARCHAR(64) NOT NULL, "
    "payload JSONB"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_import_job_events_job_id ON import_job_events (job_id)",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS import_job_id UUID "
    "REFERENCES import_jobs(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS ix_learning_cards_import_job_id "
    "ON learning_cards (import_job_id)",
    "ALTER TABLE lexical_entries ADD COLUMN IF NOT EXISTS lemma_key_l2 VARCHAR(255)",
    "ALTER TABLE lexical_entries ADD COLUMN IF NOT EXISTS lemma_key_l1 VARCHAR(255)",
    "CREATE INDEX IF NOT EXISTS ix_lexical_entries_pair_key_l2 "
    "ON lexical_entries (lang_pair, lemma_key_l2)",
    "CREATE INDEX IF NOT EXISTS ix_lexical_entries_pair_key_l1 "
    "ON lexical_entries (lang_pair, lemma_key_l1)",
    """
    CREATE TABLE IF NOT EXISTS app_logs (
        id UUID PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        level VARCHAR(16) NOT NULL DEFAULT 'info',
        category VARCHAR(32) NOT NULL DEFAULT 'http',
        event VARCHAR(64) NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'ok',
        request_id UUID,
        user_id UUID,
        profile_id UUID,
        http_method VARCHAR(16),
        http_path VARCHAR(512),
        http_status INTEGER,
        entity_type VARCHAR(32),
        entity_id VARCHAR(64),
        duration_ms INTEGER,
        message VARCHAR(4000),
        error_type VARCHAR(128),
        error_message VARCHAR(4000),
        traceback TEXT,
        payload JSONB
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_app_logs_created_at ON app_logs (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_app_logs_level_created ON app_logs (level, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_app_logs_category_created ON app_logs (category, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_app_logs_event_created ON app_logs (event, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_app_logs_user_created ON app_logs (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_app_logs_request_id ON app_logs (request_id)",
    # Homographs (play/verb vs play/noun) are distinct cards. The old unique
    # (…, deck_id) allowed two identical verbs on the system list because
    # PostgreSQL treats NULL deck_id as distinct in unique indexes.
    """
    UPDATE learning_cards c
    SET deleted_at = NOW()
    FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY user_id, profile_id, lower(lemma_l2), lower(COALESCE(pos, ''))
            ORDER BY created_at ASC, id ASC
        ) AS rn
        FROM learning_cards
        WHERE deleted_at IS NULL
    ) d
    WHERE c.id = d.id AND d.rn > 1
    """,
    "DROP INDEX IF EXISTS uq_learning_cards_active",
    "DROP INDEX IF EXISTS uq_learning_cards_live_lemma_pos",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_learning_cards_live_lemma_pos "
    "ON learning_cards (user_id, profile_id, lower(lemma_l2), lower(COALESCE(pos, ''))) "
    "WHERE deleted_at IS NULL",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_retry_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_retry_at TIMESTAMPTZ",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_auto_retry_used BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS "
    "enrichment_manual_triggered BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE learning_cards ALTER COLUMN enrichment_status TYPE VARCHAR(32)",
    "CREATE INDEX IF NOT EXISTS ix_learning_cards_enrichment_retry_at "
    "ON learning_cards (enrichment_retry_at) "
    "WHERE enrichment_status = 'preparing'",
    """
    CREATE TABLE IF NOT EXISTS lookup_query_cache (
        id UUID PRIMARY KEY,
        lang_pair VARCHAR(16) NOT NULL,
        input_norm VARCHAR(200) NOT NULL,
        candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
        ai_complete BOOLEAN NOT NULL DEFAULT false,
        hit_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (lang_pair, input_norm)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_lookup_query_cache_lang_pair "
    "ON lookup_query_cache (lang_pair)",
    """
    CREATE TABLE IF NOT EXISTS llm_usage (
        id UUID PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        provider VARCHAR(16) NOT NULL DEFAULT 'openai',
        model VARCHAR(64) NOT NULL,
        purpose VARCHAR(32) NOT NULL,
        operation_id UUID,
        operation_kind VARCHAR(32),
        query VARCHAR(200),
        lemma VARCHAR(255),
        pos VARCHAR(32),
        lang_pair VARCHAR(16),
        card_id UUID,
        user_id UUID,
        profile_id UUID,
        request_id UUID,
        openai_response_id VARCHAR(64),
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        cached_tokens INTEGER NOT NULL DEFAULT 0,
        cache_write_tokens INTEGER NOT NULL DEFAULT 0,
        reasoning_tokens INTEGER NOT NULL DEFAULT 0,
        estimated_cost_usd NUMERIC(12, 8),
        pricing_version VARCHAR(16),
        duration_ms INTEGER,
        status VARCHAR(16) NOT NULL DEFAULT 'ok'
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_llm_usage_created_at ON llm_usage (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_llm_usage_operation_id ON llm_usage (operation_id)",
    "CREATE INDEX IF NOT EXISTS ix_llm_usage_lemma_pair ON llm_usage (lemma, lang_pair)",
    "CREATE INDEX IF NOT EXISTS ix_llm_usage_purpose ON llm_usage (purpose)",
    "CREATE INDEX IF NOT EXISTS ix_llm_usage_user_id ON llm_usage (user_id)",
    """
    CREATE TABLE IF NOT EXISTS lookup_events (
        id UUID PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        user_id UUID,
        profile_id UUID,
        query VARCHAR(200) NOT NULL,
        query_norm VARCHAR(200) NOT NULL,
        lang_pair VARCHAR(16),
        source VARCHAR(16) NOT NULL DEFAULT 'lookup',
        candidate_count INTEGER NOT NULL DEFAULT 0,
        http_status INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_lookup_events_created_at ON lookup_events (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_lookup_events_user_created ON lookup_events (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_lookup_events_query_norm ON lookup_events (query_norm)",
    """
    CREATE TABLE IF NOT EXISTS word_families (
        id UUID PRIMARY KEY,
        lang_pair VARCHAR(16) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_word_families_lang_pair ON word_families (lang_pair)",
    """
    CREATE TABLE IF NOT EXISTS word_family_members (
        id UUID PRIMARY KEY,
        family_id UUID NOT NULL REFERENCES word_families(id) ON DELETE CASCADE,
        lang_pair VARCHAR(16) NOT NULL,
        lemma_key VARCHAR(255) NOT NULL,
        lemma VARCHAR(255) NOT NULL,
        pos VARCHAR(32) NOT NULL,
        article VARCHAR(16),
        gloss_l1 VARCHAR(255),
        rank INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (family_id, lemma_key, pos),
        UNIQUE (lang_pair, lemma_key, pos)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_word_family_members_family_id "
    "ON word_family_members (family_id)",
    "CREATE INDEX IF NOT EXISTS ix_word_family_members_lookup "
    "ON word_family_members (lang_pair, lemma_key, pos)",
    "ALTER TABLE lexical_entries ADD COLUMN IF NOT EXISTS word_family_id UUID "
    "REFERENCES word_families(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS ix_lexical_entries_word_family_id "
    "ON lexical_entries (word_family_id)",
    """
    CREATE TABLE IF NOT EXISTS llm_call_payloads (
        llm_usage_id UUID PRIMARY KEY REFERENCES llm_usage(id) ON DELETE CASCADE,
        request_json JSONB,
        response_json JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_llm_call_payloads_created_at "
    "ON llm_call_payloads (created_at)",
    "ALTER TABLE lookup_events ADD COLUMN IF NOT EXISTS request_id UUID",
    "ALTER TABLE lookup_events ADD COLUMN IF NOT EXISTS candidates JSONB "
    "NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE lookup_events ADD COLUMN IF NOT EXISTS ai_complete BOOLEAN "
    "NOT NULL DEFAULT false",
    "ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS lookup_event_id UUID "
    "REFERENCES lookup_events(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS ix_llm_usage_lookup_event_id "
    "ON llm_usage (lookup_event_id)",
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS lookup_event_id UUID "
    "REFERENCES lookup_events(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS ix_learning_cards_lookup_event_id "
    "ON learning_cards (lookup_event_id)",
    """
    CREATE TABLE IF NOT EXISTS admin_escalations (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        card_id UUID NOT NULL REFERENCES learning_cards(id) ON DELETE CASCADE,
        correction_id UUID NOT NULL UNIQUE REFERENCES card_corrections(id) ON DELETE CASCADE,
        user_note VARCHAR(2000),
        sections JSONB NOT NULL DEFAULT '[]'::jsonb,
        reject_reason VARCHAR(2000),
        card_snapshot JSONB,
        status VARCHAR(32) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        resolved_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_admin_escalations_status "
    "ON admin_escalations (status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_admin_escalations_card_id "
    "ON admin_escalations (card_id)",
    # E-001/F-004/T-002: existing accounts get no verification proof (NULL), not today's date.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_revision BIGINT NOT NULL DEFAULT 1",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS credentials_revision BIGINT NOT NULL DEFAULT 1",
    # E-001/F-004/T-004: e-mail change links point at their change; purpose list grows.
    "ALTER TABLE account_action_tokens ADD COLUMN IF NOT EXISTS email_change_id UUID "
    "REFERENCES account_email_changes (id) ON DELETE CASCADE",
    "DO $$ BEGIN "
    "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_account_action_tokens_purpose' "
    "AND pg_get_constraintdef(oid) NOT LIKE '%change_email%') THEN "
    "ALTER TABLE account_action_tokens DROP CONSTRAINT ck_account_action_tokens_purpose; "
    "ALTER TABLE account_action_tokens ADD CONSTRAINT ck_account_action_tokens_purpose "
    "CHECK (purpose IN ('verify_email', 'reset_password', 'change_email')); "
    "END IF; "
    "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
    "WHERE conname = 'ck_account_action_tokens_email_change') THEN "
    "ALTER TABLE account_action_tokens ADD CONSTRAINT ck_account_action_tokens_email_change "
    "CHECK ((purpose = 'change_email') = (email_change_id IS NOT NULL)); "
    "END IF; END $$",
    # E-001/F-006/T-002: account lifecycle and deletion proofs.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS account_status VARCHAR(16) NOT NULL "
    "DEFAULT 'active'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS lifecycle_revision BIGINT NOT NULL DEFAULT 1",
    "ALTER TABLE account_action_tokens ADD COLUMN IF NOT EXISTS proof_method VARCHAR(16)",
    "ALTER TABLE account_action_tokens ADD COLUMN IF NOT EXISTS lifecycle_revision BIGINT",
    "ALTER TABLE account_action_tokens ADD COLUMN IF NOT EXISTS target_deletion_id UUID",
    "DO $$ BEGIN "
    "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_account_status') THEN "
    "ALTER TABLE users ADD CONSTRAINT ck_users_account_status "
    "CHECK (account_status IN ('active', 'deletion_pending', 'deleting')); "
    "END IF; "
    "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_account_action_tokens_purpose' "
    "AND pg_get_constraintdef(oid) NOT LIKE '%request_account_deletion%') THEN "
    "ALTER TABLE account_action_tokens DROP CONSTRAINT ck_account_action_tokens_purpose; "
    "ALTER TABLE account_action_tokens ADD CONSTRAINT ck_account_action_tokens_purpose "
    "CHECK (purpose IN ('verify_email', 'reset_password', 'change_email', "
    "'request_account_deletion', 'cancel_account_deletion')); "
    "END IF; "
    "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
    "WHERE conname = 'ck_account_action_tokens_deletion') THEN "
    "ALTER TABLE account_action_tokens ADD CONSTRAINT ck_account_action_tokens_deletion "
    "CHECK ((purpose IN ('request_account_deletion', 'cancel_account_deletion')) "
    "= (proof_method IS NOT NULL)); "
    "END IF; END $$",
    # E-001/F-005/T-001: Google snapshot of the linked identity and the new revocation reason.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_email VARCHAR(320)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_email_observed_at TIMESTAMPTZ",
    "DO $$ BEGIN "
    "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_auth_sessions_revocation_reason' "
    "AND pg_get_constraintdef(oid) NOT LIKE '%google_linked%') THEN "
    "ALTER TABLE auth_sessions DROP CONSTRAINT ck_auth_sessions_revocation_reason; "
    "ALTER TABLE auth_sessions ADD CONSTRAINT ck_auth_sessions_revocation_reason "
    "CHECK (revocation_reason IS NULL OR revocation_reason IN ('logout', 'password_reset', "
    "'password_change', 'password_added', 'google_linked', 'email_changed', "
    "'refresh_reuse', 'account_deleted')); "
    "END IF; END $$",
    # E-001/F-007/T-003: terms acceptance proof; old accounts stay NULL (never "accepted").
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS accepted_terms_version VARCHAR(32)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS accepted_privacy_version VARCHAR(32)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_locale VARCHAR(8)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS adult_statement_version VARCHAR(32)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS adult_confirmed_at TIMESTAMPTZ",
    # E-001/F-003/T-004: rewizja profilu i ostatnia mutacja (idempotentny retry edycji).
    "ALTER TABLE language_profiles ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 1",
    "ALTER TABLE language_profiles ADD COLUMN IF NOT EXISTS last_mutation_id UUID",
    "ALTER TABLE language_profiles ADD COLUMN IF NOT EXISTS last_mutation_fingerprint VARCHAR(64)",
    # E-001/F-003/T-003: ACK push, undo markers, list-create receipts, revision SRS.
    "ALTER TABLE srs_state ADD COLUMN IF NOT EXISTS review_revision BIGINT NOT NULL DEFAULT 0",
    "ALTER TABLE review_logs ADD COLUMN IF NOT EXISTS applied_revision BIGINT",
    "ALTER TABLE review_logs ADD COLUMN IF NOT EXISTS intent_fingerprint VARCHAR(64)",
    "ALTER TABLE applied_sync_moves ADD COLUMN IF NOT EXISTS intent_fingerprint VARCHAR(64)",
    # E-001/F-003/T-003 pkt 3: pull z jawnym xid8 i snapshotem PostgreSQL (bez zegara).
    "ALTER TABLE learning_cards ADD COLUMN IF NOT EXISTS sync_xid xid8",
    "ALTER TABLE word_lists ADD COLUMN IF NOT EXISTS sync_xid xid8",
    "CREATE TABLE IF NOT EXISTS sync_tombstones ("
    "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "profile_id UUID NOT NULL REFERENCES language_profiles(id) ON DELETE CASCADE, "
    "entity_type VARCHAR(8) NOT NULL CHECK (entity_type IN ('card', 'list')), "
    "entity_id UUID NOT NULL, "
    "sync_xid xid8 NOT NULL, "
    "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_sync_tombstones_cursor "
    "ON sync_tombstones (user_id, profile_id, sync_xid)",
    "CREATE INDEX IF NOT EXISTS ix_sync_tombstones_created ON sync_tombstones (created_at)",
    "CREATE TABLE IF NOT EXISTS profile_sync_state ("
    "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "profile_id UUID NOT NULL REFERENCES language_profiles(id) ON DELETE CASCADE, "
    "purged_through_xid xid8 NOT NULL, "
    "PRIMARY KEY (user_id, profile_id)"
    ")",
    "CREATE TABLE IF NOT EXISTS sync_epoch ("
    "id INTEGER PRIMARY KEY CHECK (id = 1), "
    "epoch UUID NOT NULL"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_learning_cards_sync_cursor "
    "ON learning_cards (user_id, profile_id, sync_xid)",
    "CREATE INDEX IF NOT EXISTS ix_word_lists_sync_cursor "
    "ON word_lists (user_id, profile_id, sync_xid)",
    "CREATE OR REPLACE FUNCTION vocab_set_sync_xid() RETURNS trigger AS $fn$ "
    "BEGIN NEW.sync_xid = pg_current_xact_id(); RETURN NEW; END $fn$ LANGUAGE plpgsql",
    "CREATE OR REPLACE FUNCTION vocab_touch_card_for_srs() RETURNS trigger AS $fn$ "
    "BEGIN "
    "UPDATE learning_cards SET sync_xid = pg_current_xact_id() "
    "WHERE id = NEW.card_id AND sync_xid IS DISTINCT FROM pg_current_xact_id(); "
    "RETURN NEW; END $fn$ LANGUAGE plpgsql",
    "CREATE OR REPLACE FUNCTION vocab_bump_srs_revision() RETURNS trigger AS $fn$ "
    "BEGIN "
    "IF ROW(NEW.status, NEW.ease, NEW.interval_days, NEW.repetitions, NEW.lapses, "
    "NEW.next_review_at, NEW.last_reviewed_at, NEW.last_grade, NEW.stability, "
    "NEW.difficulty, NEW.fsrs_step) IS DISTINCT FROM "
    "ROW(OLD.status, OLD.ease, OLD.interval_days, OLD.repetitions, OLD.lapses, "
    "OLD.next_review_at, OLD.last_reviewed_at, OLD.last_grade, OLD.stability, "
    "OLD.difficulty, OLD.fsrs_step) THEN "
    "NEW.review_revision = OLD.review_revision + 1; END IF; "
    "RETURN NEW; END $fn$ LANGUAGE plpgsql",
    # Tombstone tylko gdy właściciel i profil istnieją: kaskada z usuwania konta/profilu nic nie zostawia.
    "CREATE OR REPLACE FUNCTION vocab_sync_tombstone() RETURNS trigger AS $fn$ "
    "BEGIN "
    "IF EXISTS (SELECT 1 FROM users WHERE id = OLD.user_id) "
    "AND EXISTS (SELECT 1 FROM language_profiles WHERE id = OLD.profile_id) THEN "
    "INSERT INTO sync_tombstones (user_id, profile_id, entity_type, entity_id, sync_xid) "
    "VALUES (OLD.user_id, OLD.profile_id, TG_ARGV[0], OLD.id, pg_current_xact_id()); "
    "END IF; RETURN OLD; END $fn$ LANGUAGE plpgsql",
    "DO $$ BEGIN "
    "IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_learning_cards_sync_xid') THEN "
    "CREATE TRIGGER trg_learning_cards_sync_xid BEFORE INSERT OR UPDATE ON learning_cards "
    "FOR EACH ROW EXECUTE FUNCTION vocab_set_sync_xid(); END IF; "
    "IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_word_lists_sync_xid') THEN "
    "CREATE TRIGGER trg_word_lists_sync_xid BEFORE INSERT OR UPDATE ON word_lists "
    "FOR EACH ROW EXECUTE FUNCTION vocab_set_sync_xid(); END IF; "
    "IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_srs_state_touch_card') THEN "
    "CREATE TRIGGER trg_srs_state_touch_card AFTER INSERT OR UPDATE ON srs_state "
    "FOR EACH ROW EXECUTE FUNCTION vocab_touch_card_for_srs(); END IF; "
    "IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_srs_state_revision') THEN "
    "CREATE TRIGGER trg_srs_state_revision BEFORE UPDATE ON srs_state "
    "FOR EACH ROW EXECUTE FUNCTION vocab_bump_srs_revision(); END IF; "
    "IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_learning_cards_tombstone') THEN "
    "CREATE TRIGGER trg_learning_cards_tombstone BEFORE DELETE ON learning_cards "
    "FOR EACH ROW EXECUTE FUNCTION vocab_sync_tombstone('card'); END IF; "
    "IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_word_lists_tombstone') THEN "
    "CREATE TRIGGER trg_word_lists_tombstone BEFORE DELETE ON word_lists "
    "FOR EACH ROW EXECUTE FUNCTION vocab_sync_tombstone('list'); END IF; "
    "END $$",
)

_SYNC_BACKFILL_BATCH = 2000


def _is_deadlock(exc: BaseException) -> bool:
    orig = getattr(exc, "orig", exc)
    name = orig.__class__.__name__
    if name == "DeadlockDetectedError":
        return True
    return "deadlock detected" in str(orig).lower()


@asynccontextmanager
async def _schema_lock(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.connect() as lock_conn:
        is_pg = lock_conn.dialect.name == "postgresql"
        if is_pg:
            await lock_conn.execute(
                text("SELECT pg_advisory_lock(:k)"), {"k": _SCHEMA_LOCK_KEY}
            )
            await lock_conn.commit()
        try:
            yield
        finally:
            if is_pg:
                try:
                    await lock_conn.execute(
                        text("SELECT pg_advisory_unlock(:k)"),
                        {"k": _SCHEMA_LOCK_KEY},
                    )
                    await lock_conn.commit()
                except Exception:
                    await lock_conn.invalidate()


async def _run_statement(engine: AsyncEngine, statement: str) -> None:
    last_exc: BaseException | None = None
    for attempt in range(_DEADLOCK_RETRIES):
        try:
            async with engine.begin() as conn:
                await conn.execute(text(statement))
            return
        except DBAPIError as exc:
            last_exc = exc
            if not _is_deadlock(exc) or attempt == _DEADLOCK_RETRIES - 1:
                raise
            await asyncio.sleep(0.05 * (2**attempt))
    if last_exc is not None:
        raise last_exc


async def apply_schema(engine: AsyncEngine, metadata: MetaData) -> None:
    """create_all + migracje pod lockiem, każda instrukcja w osobnej transakcji.

    Dwie repliki startujące razem wcześniej trzymały wszystkie ALTER w jednym
    `BEGIN` i wpadały w deadlock (`DROP COLUMN ui_lang` vs. locki z create_all).
    """
    async with _schema_lock(engine):
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        for statement in _STATEMENTS:
            await _run_statement(engine, statement)
        async with engine.begin() as conn:
            await _backfill_lemma_keys(conn)
        async with engine.begin() as conn:
            await _backfill_sync_xid(conn)


async def run_migrations(conn: AsyncConnection) -> None:
    for statement in _STATEMENTS:
        await conn.execute(text(statement))
    await _backfill_lemma_keys(conn)
    await _backfill_sync_xid(conn)


async def _backfill_sync_xid(conn: AsyncConnection) -> None:
    """Uzupełnia brakujące znaczniki w batchach (trigger BEFORE UPDATE sam wpisuje xid), potem NOT NULL."""
    for table in ("learning_cards", "word_lists"):
        while True:
            done = await conn.execute(
                text(
                    f"UPDATE {table} SET sync_xid = pg_current_xact_id() WHERE id IN "
                    f"(SELECT id FROM {table} WHERE sync_xid IS NULL LIMIT :n)"
                ),
                {"n": _SYNC_BACKFILL_BATCH},
            )
            if not done.rowcount:
                break
        nullable = (
            await conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = :t "
                    "AND column_name = 'sync_xid'"
                ),
                {"t": table},
            )
        ).scalar_one_or_none()
        if nullable == "YES":
            await conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN sync_xid SET NOT NULL"))


async def _backfill_lemma_keys(conn: AsyncConnection) -> None:
    from app.core.lemma_keys import canonical_lemma

    rows = (
        await conn.execute(
            text(
                "SELECT id, lemma_l2, lemma_l1_primary FROM lexical_entries "
                "WHERE lemma_key_l2 IS NULL OR lemma_key_l1 IS NULL"
            )
        )
    ).all()
    for row in rows:
        await conn.execute(
            text(
                "UPDATE lexical_entries "
                "SET lemma_key_l2 = :k2, lemma_key_l1 = :k1 "
                "WHERE id = :id"
            ),
            {
                "id": row.id,
                "k2": canonical_lemma(row.lemma_l2) or None,
                "k1": canonical_lemma(row.lemma_l1_primary) or None,
            },
        )

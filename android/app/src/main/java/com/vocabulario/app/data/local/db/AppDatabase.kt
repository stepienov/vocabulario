package com.vocabulario.app.data.local.db

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [
        CachedCardEntity::class,
        CachedListEntity::class,
        PendingReviewEntity::class,
        PendingMoveEntity::class,
        PendingLookupEntity::class,
        PendingUndoEntity::class,
        LocalSettingsEntity::class,
        SyncMetaEntity::class,
        CachedProfileEntity::class,
        OutboxOpEntity::class,
        SessionOwnerEntity::class,
    ],
    version = 13,
    exportSchema = true,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun cachedCardDao(): CachedCardDao
    abstract fun cachedListDao(): CachedListDao
    abstract fun pendingReviewDao(): PendingReviewDao
    abstract fun pendingMoveDao(): PendingMoveDao
    abstract fun pendingLookupDao(): PendingLookupDao
    abstract fun pendingUndoDao(): PendingUndoDao
    abstract fun localSettingsDao(): LocalSettingsDao
    abstract fun syncMetaDao(): SyncMetaDao
    abstract fun cachedProfileDao(): CachedProfileDao
    abstract fun outboxOpDao(): OutboxOpDao
    abstract fun sessionOwnerDao(): SessionOwnerDao

    companion object {
        val MIGRATION_12_13 = object : Migration(12, 13) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE `cached_cards` ADD COLUMN `createdAt` TEXT")
                // Existing cards need a single full pull to recover their original creation dates.
                db.execSQL("UPDATE `sync_meta` SET `cursor` = NULL")
            }
        }

        /**
         * v6 → v7: dodaje ujednolicony outbox `outbox_ops` oraz kolumny lokalnych list.
         * Migracja NIE kasuje danych — chroni niewysłany outbox przy aktualizacji aplikacji.
         */
        val MIGRATION_6_7 = object : Migration(6, 7) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `outbox_ops` (" +
                        "`seq` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                        "`clientOpId` TEXT NOT NULL, " +
                        "`type` TEXT NOT NULL, " +
                        "`payloadJson` TEXT NOT NULL, " +
                        "`createdAt` INTEGER NOT NULL, " +
                        "`attempts` INTEGER NOT NULL, " +
                        "`status` TEXT NOT NULL, " +
                        "`lastError` TEXT)",
                )
                db.execSQL(
                    "ALTER TABLE `cached_lists` ADD COLUMN `isLocalOnly` INTEGER NOT NULL DEFAULT 0",
                )
                db.execSQL(
                    "ALTER TABLE `cached_lists` ADD COLUMN `pendingDelete` INTEGER NOT NULL DEFAULT 0",
                )
            }
        }

        /**
         * v7 → v8: kolejka lookupów offline dostaje stan `status` (`queued`/`needs_review`)
         * oraz `suggestionsJson` (propozycje dla słów wymagających sprawdzenia). Bez utraty danych.
         */
        val MIGRATION_7_8 = object : Migration(7, 8) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "ALTER TABLE `pending_lookups` ADD COLUMN `status` TEXT NOT NULL DEFAULT 'queued'",
                )
                db.execSQL(
                    "ALTER TABLE `pending_lookups` ADD COLUMN `suggestionsJson` TEXT",
                )
            }
        }

        /** v8 → v9: indeksy pod listy / kolejkę SRS przy dużym zbiorze kart. */
        val MIGRATION_8_9 = object : Migration(8, 9) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_cached_cards_profileId` " +
                        "ON `cached_cards` (`profileId`)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_cached_cards_profileId_deckId` " +
                        "ON `cached_cards` (`profileId`, `deckId`)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_cached_cards_queue` " +
                        "ON `cached_cards` (`profileId`, `enrichmentStatus`, `status`, `nextReviewAt`)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_cached_lists_profileId` " +
                        "ON `cached_lists` (`profileId`)",
                )
            }
        }

        /** Tabele z danymi jednego właściciela; czyszczone przy logout bez `clearAllTables`. */
        val OWNED_TABLES = listOf(
            "cached_cards",
            "cached_lists",
            "pending_reviews",
            "pending_moves",
            "pending_lookups",
            "pending_undos",
            "local_settings",
            "sync_meta",
            "cached_profile",
            "outbox_ops",
        )

        /**
         * v9 → v10: rekord właściciela bazy. Istniejące dane nie mają wiarygodnego właściciela,
         * więc trafiają do `legacy_unclaimed` (kwarantanna) — migracja niczego nie kasuje.
         */
        val MIGRATION_9_10 = object : Migration(9, 10) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `session_owner` (" +
                        "`id` INTEGER NOT NULL, " +
                        "`ownerUserId` TEXT, " +
                        "`generation` INTEGER NOT NULL, " +
                        "`phase` TEXT NOT NULL, " +
                        "`transitionId` TEXT, " +
                        "PRIMARY KEY(`id`))",
                )
                val hasData = OWNED_TABLES.any { table ->
                    db.query("SELECT 1 FROM `$table` LIMIT 1").use { it.moveToFirst() }
                }
                val phase = if (hasData) OwnerPhase.LEGACY_UNCLAIMED else OwnerPhase.SIGNED_OUT
                db.execSQL(
                    "INSERT OR IGNORE INTO `session_owner` (`id`, `ownerUserId`, `generation`, `phase`, `transitionId`) " +
                        "VALUES (0, NULL, 0, ?, NULL)",
                    arrayOf<Any>(phase),
                )
            }
        }

        /** v10 → v11: trwała dyspozycja logoutu i zaakceptowany fingerprint kolejek (addytywnie). */
        val MIGRATION_10_11 = object : Migration(10, 11) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE `session_owner` ADD COLUMN `logoutDisposition` TEXT")
                db.execSQL("ALTER TABLE `session_owner` ADD COLUMN `acceptedUnsentFingerprint` TEXT")
            }
        }

        /** v11 → v12: zablokowane operacje kolejek, kursor pull i wynik próby sync per profil (addytywnie). */
        val MIGRATION_11_12 = object : Migration(11, 12) {
            override fun migrate(db: SupportSQLiteDatabase) {
                for (table in listOf("pending_reviews", "pending_moves", "pending_undos")) {
                    db.execSQL("ALTER TABLE `$table` ADD COLUMN `blockedReason` TEXT")
                }
                db.execSQL("ALTER TABLE `sync_meta` ADD COLUMN `cursor` TEXT")
                db.execSQL("ALTER TABLE `sync_meta` ADD COLUMN `lastAttemptAt` INTEGER")
                db.execSQL("ALTER TABLE `sync_meta` ADD COLUMN `lastSuccessAt` INTEGER")
                db.execSQL("ALTER TABLE `sync_meta` ADD COLUMN `lastError` TEXT")
            }
        }
    }
}

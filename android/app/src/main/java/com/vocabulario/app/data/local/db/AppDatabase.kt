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
    ],
    version = 8,
    exportSchema = false,
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

    companion object {
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
    }
}

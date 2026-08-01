package com.vocabulario.app.data.local.db

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [
        CachedCardEntity::class,
        PendingReviewEntity::class,
        LocalSettingsEntity::class,
        SyncMetaEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun cachedCardDao(): CachedCardDao
    abstract fun pendingReviewDao(): PendingReviewDao
    abstract fun localSettingsDao(): LocalSettingsDao
    abstract fun syncMetaDao(): SyncMetaDao
}

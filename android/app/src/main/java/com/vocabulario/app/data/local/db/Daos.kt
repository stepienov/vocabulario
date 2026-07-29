package com.vocabulario.app.data.local.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface CachedCardDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(cards: List<CachedCardEntity>)

    @Query("SELECT * FROM cached_cards WHERE profileId = :profileId")
    suspend fun forProfile(profileId: String): List<CachedCardEntity>

    @Query("DELETE FROM cached_cards WHERE profileId = :profileId")
    suspend fun clearProfile(profileId: String)
}

@Dao
interface PendingReviewDao {
    @Insert
    suspend fun insert(review: PendingReviewEntity): Long

    @Query("SELECT * FROM pending_reviews ORDER BY createdAt ASC")
    suspend fun all(): List<PendingReviewEntity>

    @Query("DELETE FROM pending_reviews WHERE localId = :id")
    suspend fun delete(id: Long)
}

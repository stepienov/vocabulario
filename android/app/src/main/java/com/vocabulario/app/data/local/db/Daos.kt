package com.vocabulario.app.data.local.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update

@Dao
interface CachedCardDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(cards: List<CachedCardEntity>)

    @Update
    suspend fun update(card: CachedCardEntity)

    @Query("SELECT * FROM cached_cards WHERE profileId = :profileId")
    suspend fun forProfile(profileId: String): List<CachedCardEntity>

    @Query("SELECT * FROM cached_cards WHERE id = :id LIMIT 1")
    suspend fun byId(id: String): CachedCardEntity?

    @Query(
        """
        SELECT * FROM cached_cards
        WHERE profileId = :profileId
          AND enrichmentStatus = 'ready'
          AND (deckId IS NULL OR deckId = '')
        """,
    )
    suspend fun learningCards(profileId: String): List<CachedCardEntity>

    @Query("DELETE FROM cached_cards WHERE profileId = :profileId")
    suspend fun clearProfile(profileId: String)

    @Query("DELETE FROM cached_cards WHERE id IN (:ids)")
    suspend fun deleteIds(ids: List<String>)
}

@Dao
interface PendingReviewDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(review: PendingReviewEntity)

    @Query("SELECT * FROM pending_reviews ORDER BY createdAt ASC")
    suspend fun all(): List<PendingReviewEntity>

    @Query("DELETE FROM pending_reviews WHERE clientId = :clientId")
    suspend fun delete(clientId: String)

    @Query("DELETE FROM pending_reviews WHERE clientId IN (:ids)")
    suspend fun deleteIds(ids: List<String>)

    @Query("SELECT COUNT(*) FROM pending_reviews")
    suspend fun count(): Int
}

@Dao
interface LocalSettingsDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(settings: LocalSettingsEntity)

    @Query("SELECT * FROM local_settings WHERE userKey = 'me' LIMIT 1")
    suspend fun get(): LocalSettingsEntity?
}

@Dao
interface SyncMetaDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(meta: SyncMetaEntity)

    @Query("SELECT * FROM sync_meta WHERE profileId = :profileId LIMIT 1")
    suspend fun get(profileId: String): SyncMetaEntity?
}

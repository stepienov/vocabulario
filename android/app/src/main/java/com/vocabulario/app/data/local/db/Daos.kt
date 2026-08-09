package com.vocabulario.app.data.local.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface CachedCardDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(cards: List<CachedCardEntity>)

    @Update
    suspend fun update(card: CachedCardEntity)

    @Query("SELECT * FROM cached_cards WHERE profileId = :profileId")
    suspend fun forProfile(profileId: String): List<CachedCardEntity>

    @Query("SELECT * FROM cached_cards WHERE profileId = :profileId")
    fun observeForProfile(profileId: String): Flow<List<CachedCardEntity>>

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

    @Query(
        """
        SELECT * FROM cached_cards
        WHERE profileId = :profileId
          AND (deckId IS NULL OR deckId = '')
        ORDER BY updatedAt DESC
        """,
    )
    suspend fun systemListCards(profileId: String): List<CachedCardEntity>

    @Query(
        """
        SELECT * FROM cached_cards
        WHERE profileId = :profileId AND deckId = :deckId
        ORDER BY updatedAt DESC
        """,
    )
    suspend fun cardsForDeck(profileId: String, deckId: String): List<CachedCardEntity>

    @Query("SELECT * FROM cached_cards WHERE deckId = :deckId")
    suspend fun cardsByDeckId(deckId: String): List<CachedCardEntity>

    @Query("DELETE FROM cached_cards WHERE profileId = :profileId")
    suspend fun clearProfile(profileId: String)

    @Query("DELETE FROM cached_cards WHERE id IN (:ids)")
    suspend fun deleteIds(ids: List<String>)

    @Query("UPDATE cached_cards SET deckId = :newId WHERE deckId = :oldId")
    suspend fun migrateDeckId(oldId: String, newId: String)
}

@Dao
interface CachedListDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(lists: List<CachedListEntity>)

    @Query("SELECT * FROM cached_lists WHERE profileId = :profileId ORDER BY isSystem DESC, createdAt ASC")
    suspend fun forProfile(profileId: String): List<CachedListEntity>

    @Query("SELECT * FROM cached_lists WHERE profileId = :profileId ORDER BY isSystem DESC, createdAt ASC")
    fun observeForProfile(profileId: String): Flow<List<CachedListEntity>>

    @Query("SELECT * FROM cached_lists WHERE id = :id LIMIT 1")
    suspend fun byId(id: String): CachedListEntity?

    @Query(
        """
        SELECT * FROM cached_lists
        WHERE profileId = :profileId AND isPendingInbox = 1
        LIMIT 1
        """,
    )
    suspend fun pendingInbox(profileId: String): CachedListEntity?

    @Query("DELETE FROM cached_lists WHERE id = :id")
    suspend fun deleteById(id: String)

    @Query("DELETE FROM cached_lists WHERE profileId = :profileId")
    suspend fun clearProfile(profileId: String)
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
interface PendingMoveDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(move: PendingMoveEntity)

    @Query("SELECT * FROM pending_moves ORDER BY movedAt ASC")
    suspend fun all(): List<PendingMoveEntity>

    @Query("DELETE FROM pending_moves WHERE clientId IN (:ids)")
    suspend fun deleteIds(ids: List<String>)

    @Query("UPDATE pending_moves SET targetListId = :newId WHERE targetListId = :oldId")
    suspend fun remapTarget(oldId: String, newId: String)

    @Query("SELECT COUNT(*) FROM pending_moves")
    suspend fun count(): Int
}

@Dao
interface PendingLookupDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(lookup: PendingLookupEntity)

    @Query("SELECT * FROM pending_lookups WHERE profileId = :profileId ORDER BY createdAt ASC")
    suspend fun forProfile(profileId: String): List<PendingLookupEntity>

    @Query("SELECT * FROM pending_lookups WHERE listId = :listId ORDER BY createdAt ASC")
    suspend fun forList(listId: String): List<PendingLookupEntity>

    @Query(
        """
        SELECT * FROM pending_lookups
        WHERE profileId = :profileId AND lower(lemma) = lower(:lemma)
        LIMIT 1
        """,
    )
    suspend fun findLemma(profileId: String, lemma: String): PendingLookupEntity?

    @Query("DELETE FROM pending_lookups WHERE clientId IN (:ids)")
    suspend fun deleteIds(ids: List<String>)

    @Query("UPDATE pending_lookups SET listId = :newListId WHERE listId = :oldListId")
    suspend fun migrateLookupListId(oldListId: String, newListId: String)

    @Query("SELECT * FROM pending_lookups WHERE clientId = :clientId LIMIT 1")
    suspend fun byId(clientId: String): PendingLookupEntity?

    @Query(
        "UPDATE pending_lookups SET status = :status, suggestionsJson = :suggestionsJson " +
            "WHERE clientId = :clientId",
    )
    suspend fun setStatus(clientId: String, status: String, suggestionsJson: String?)

    @Query("SELECT * FROM pending_lookups ORDER BY createdAt ASC")
    suspend fun all(): List<PendingLookupEntity>
}

@Dao
interface PendingUndoDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: PendingUndoEntity)

    @Query("SELECT * FROM pending_undos ORDER BY clientId ASC")
    suspend fun all(): List<PendingUndoEntity>

    @Query("DELETE FROM pending_undos WHERE clientId = :clientId")
    suspend fun delete(clientId: String)
}

@Dao
interface LocalSettingsDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(settings: LocalSettingsEntity)

    @Query("SELECT * FROM local_settings WHERE userKey = 'me' LIMIT 1")
    suspend fun get(): LocalSettingsEntity?

    @Query("SELECT * FROM local_settings WHERE userKey = 'me' LIMIT 1")
    fun observe(): Flow<LocalSettingsEntity?>
}

@Dao
interface OutboxOpDao {
    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insert(op: OutboxOpEntity): Long

    @Query("SELECT * FROM outbox_ops WHERE status = 'pending' ORDER BY seq ASC")
    suspend fun pending(): List<OutboxOpEntity>

    @Query("SELECT * FROM outbox_ops ORDER BY seq ASC")
    suspend fun all(): List<OutboxOpEntity>

    @Update
    suspend fun update(op: OutboxOpEntity)

    @Query("DELETE FROM outbox_ops WHERE seq = :seq")
    suspend fun deleteBySeq(seq: Long)

    @Query("DELETE FROM outbox_ops WHERE clientOpId = :clientOpId")
    suspend fun deleteByClientOpId(clientOpId: String)

    @Query("SELECT COUNT(*) FROM outbox_ops WHERE status = 'pending'")
    suspend fun pendingCount(): Int
}

@Dao
interface SyncMetaDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(meta: SyncMetaEntity)

    @Query("SELECT * FROM sync_meta WHERE profileId = :profileId LIMIT 1")
    suspend fun get(profileId: String): SyncMetaEntity?
}

@Dao
interface CachedProfileDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(profile: CachedProfileEntity)

    @Query("SELECT * FROM cached_profile WHERE isActive = 1 LIMIT 1")
    suspend fun active(): CachedProfileEntity?

    @Query("SELECT * FROM cached_profile WHERE id = :id LIMIT 1")
    suspend fun byId(id: String): CachedProfileEntity?
}

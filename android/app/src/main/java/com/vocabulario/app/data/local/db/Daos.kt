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

    @Query(
        "SELECT id, lemmaL2, pos, deckId, enrichmentStatus FROM cached_cards WHERE profileId = :profileId",
    )
    fun observeMembershipRows(profileId: String): Flow<List<com.vocabulario.app.data.CardMembershipRow>>

    @Query("SELECT * FROM cached_cards WHERE id = :id LIMIT 1")
    suspend fun byId(id: String): CachedCardEntity?

    @Query("SELECT * FROM cached_cards WHERE id = :id LIMIT 1")
    fun observeById(id: String): Flow<CachedCardEntity?>

    @Query(
        """
        SELECT * FROM cached_cards
        WHERE profileId = :profileId
          AND enrichmentStatus IN ('ready', 'learnable')
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

    @Query("SELECT COUNT(*) FROM cached_cards WHERE profileId = :profileId")
    suspend fun countForProfile(profileId: String): Int

    @Query("DELETE FROM cached_cards WHERE id IN (:ids)")
    suspend fun deleteIds(ids: List<String>)

    @Query("UPDATE cached_cards SET deckId = :newId WHERE deckId = :oldId")
    suspend fun migrateDeckId(oldId: String, newId: String)

    /** Karty błędnie zapisane z UUID listy systemowej → NULL, żeby weszły do systemListCards. */
    @Query("UPDATE cached_cards SET deckId = NULL WHERE profileId = :profileId AND deckId = :systemListId")
    suspend fun clearDeckIdMatchingList(profileId: String, systemListId: String)
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

    @Query("SELECT * FROM pending_reviews WHERE blockedReason IS NULL ORDER BY createdAt ASC")
    suspend fun sendable(): List<PendingReviewEntity>

    @Query("UPDATE pending_reviews SET blockedReason = :reason WHERE clientId = :clientId")
    suspend fun block(clientId: String, reason: String)

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

    @Query("SELECT * FROM pending_moves WHERE blockedReason IS NULL ORDER BY movedAt ASC")
    suspend fun sendable(): List<PendingMoveEntity>

    @Query("UPDATE pending_moves SET blockedReason = :reason WHERE clientId = :clientId")
    suspend fun block(clientId: String, reason: String)

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

    @Query("SELECT * FROM pending_undos WHERE blockedReason IS NULL ORDER BY clientId ASC")
    suspend fun sendable(): List<PendingUndoEntity>

    @Query("UPDATE pending_undos SET blockedReason = :reason WHERE clientId = :clientId")
    suspend fun block(clientId: String, reason: String)

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

    @Query("SELECT * FROM outbox_ops WHERE seq = :seq LIMIT 1")
    suspend fun bySeq(seq: Long): OutboxOpEntity?

    /** Wartość nieistotna: Room emituje przy każdej zmianie któregokolwiek z tabel kolejek. */
    @Query(
        "SELECT (SELECT COUNT(*) FROM outbox_ops) + (SELECT COUNT(*) FROM pending_reviews) + " +
            "(SELECT COUNT(*) FROM pending_moves) + (SELECT COUNT(*) FROM pending_undos) + " +
            "(SELECT COUNT(*) FROM pending_lookups)",
    )
    fun observeQueueTouch(): Flow<Int>

    @Update
    suspend fun update(op: OutboxOpEntity)

    @Query("DELETE FROM outbox_ops WHERE seq = :seq")
    suspend fun deleteBySeq(seq: Long)

    @Query("DELETE FROM outbox_ops WHERE clientOpId = :clientOpId")
    suspend fun deleteByClientOpId(clientOpId: String)
}

@Dao
interface SyncMetaDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(meta: SyncMetaEntity)

    @Query("SELECT * FROM sync_meta WHERE profileId = :profileId LIMIT 1")
    suspend fun get(profileId: String): SyncMetaEntity?

    @Query("SELECT lastPulledAt FROM sync_meta WHERE profileId = :profileId LIMIT 1")
    fun observeLastPulledAt(profileId: String): Flow<String?>

    @Query("UPDATE sync_meta SET cursor = NULL WHERE profileId = :profileId")
    suspend fun clearCursor(profileId: String)

    @Query("SELECT * FROM sync_meta")
    suspend fun all(): List<SyncMetaEntity>
}

@Dao
interface CachedProfileDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(profile: CachedProfileEntity)

    @Query("SELECT * FROM cached_profile WHERE isActive = 1 LIMIT 1")
    suspend fun active(): CachedProfileEntity?

    @Query("SELECT * FROM cached_profile WHERE id = :id LIMIT 1")
    suspend fun byId(id: String): CachedProfileEntity?

    @Query("SELECT * FROM cached_profile")
    suspend fun all(): List<CachedProfileEntity>

    @Query("UPDATE cached_profile SET isActive = 0 WHERE id != :keepId")
    suspend fun deactivateOthers(keepId: String)

    @Query("DELETE FROM cached_profile WHERE id NOT IN (:keepIds)")
    suspend fun deleteNotIn(keepIds: List<String>)

    @Query("DELETE FROM cached_profile")
    suspend fun deleteAll()
}

@Dao
interface SessionOwnerDao {
    @Query("SELECT * FROM session_owner WHERE id = 0 LIMIT 1")
    suspend fun get(): SessionOwnerEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(owner: SessionOwnerEntity)

    /**
     * Identyfikatory operacji czekających na wysłanie (także zaparkowanych w outboxie i lookupów
     * do decyzji); liczba i fingerprint zgody na logout pochodzą z tego samego odczytu.
     */
    @Query(
        "SELECT 'r:' || clientId FROM pending_reviews UNION ALL " +
            "SELECT 'm:' || clientId FROM pending_moves UNION ALL " +
            "SELECT 'l:' || clientId FROM pending_lookups UNION ALL " +
            "SELECT 'u:' || clientId FROM pending_undos UNION ALL " +
            "SELECT 'o:' || seq FROM outbox_ops",
    )
    suspend fun unsentIds(): List<String>

    @Query(
        "SELECT EXISTS(SELECT 1 FROM cached_cards) OR EXISTS(SELECT 1 FROM cached_lists) OR " +
            "EXISTS(SELECT 1 FROM pending_reviews) OR EXISTS(SELECT 1 FROM pending_moves) OR " +
            "EXISTS(SELECT 1 FROM pending_lookups) OR EXISTS(SELECT 1 FROM pending_undos) OR " +
            "EXISTS(SELECT 1 FROM local_settings) OR EXISTS(SELECT 1 FROM sync_meta) OR " +
            "EXISTS(SELECT 1 FROM cached_profile) OR EXISTS(SELECT 1 FROM outbox_ops)",
    )
    suspend fun hasOwnedData(): Boolean
}

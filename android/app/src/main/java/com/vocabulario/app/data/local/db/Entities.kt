package com.vocabulario.app.data.local.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "cached_cards",
    indices = [
        Index(value = ["profileId"], name = "index_cached_cards_profileId"),
        Index(value = ["profileId", "deckId"], name = "index_cached_cards_profileId_deckId"),
        Index(
            value = ["profileId", "enrichmentStatus", "status", "nextReviewAt"],
            name = "index_cached_cards_queue",
        ),
    ],
)
data class CachedCardEntity(
    @PrimaryKey val id: String,
    val profileId: String,
    val deckId: String? = null,
    val lemmaL2: String,
    val glossPrimary: String?,
    val pos: String?,
    val contentJson: String,
    val enrichmentStatus: String = "ready",
    val status: String,
    val nextReviewAt: Long?,
    val lastReviewedAt: Long? = null,
    val intervalDays: Double = 0.0,
    val ease: Double = 2.5,
    val repetitions: Int = 0,
    val lapses: Int = 0,
    val stability: Double? = null,
    val difficulty: Double? = null,
    val fsrsStep: Int? = null,
    val lastGrade: String? = null,
    val direction: String? = null,
    val contentReviewStatus: String? = null,
    val cardActivityStatus: String? = null,
    val hasContentChanges: Boolean = false,
    val createdAt: String? = null,
    val updatedAt: Long = 0L,
)

@Entity(
    tableName = "cached_lists",
    indices = [Index(value = ["profileId"], name = "index_cached_lists_profileId")],
)
data class CachedListEntity(
    @PrimaryKey val id: String,
    val profileId: String,
    val name: String,
    val isSystem: Boolean = false,
    val isPendingInbox: Boolean = false,
    val wordCount: Int = 0,
    val createdAt: String? = null,
    val updatedAt: Long = 0L,
    /** True dopóki lista istnieje tylko lokalnie (ID `local:<uuid>`), przed remapem na server ID. */
    @ColumnInfo(defaultValue = "0") val isLocalOnly: Boolean = false,
    /** Optimistic hide — lista usunięta lokalnie, kasowanie czeka w outboxie. */
    @ColumnInfo(defaultValue = "0") val pendingDelete: Boolean = false,
)

/**
 * Ujednolicony, uporządkowany (FIFO po [seq]) log operacji offline dla mutacji „posiadanych”
 * danych użytkownika (ustawienia, listy, usuwanie kart). Realizowany w tle przez istniejące,
 * idempotentne endpointy REST. Oceny/ruchy/undo zachowują własne tabele pending (mają
 * osobną idempotencję server-side: ReviewLog.client_id, AppliedSyncMove).
 */
@Entity(tableName = "outbox_ops")
data class OutboxOpEntity(
    @PrimaryKey(autoGenerate = true) val seq: Long = 0,
    val clientOpId: String,
    val type: String,
    val payloadJson: String,
    val createdAt: Long,
    val attempts: Int = 0,
    val status: String = "pending",
    val lastError: String? = null,
)

@Entity(tableName = "pending_reviews")
data class PendingReviewEntity(
    @PrimaryKey val clientId: String,
    val cardId: String,
    val grade: String,
    val mode: String,
    val direction: String,
    val correct: Boolean,
    val answer: String?,
    val createdAt: Long,
    /** Przyczyna z ACK serwera; wiersz czeka na decyzję użytkownika i nie jest wysyłany ponownie. */
    val blockedReason: String? = null,
)

@Entity(tableName = "pending_moves")
data class PendingMoveEntity(
    @PrimaryKey val clientId: String,
    val cardId: String,
    /** Null = system Learning list (deck_id NULL on server). */
    val targetListId: String?,
    val movedAt: Long,
    val blockedReason: String? = null,
)

@Entity(tableName = "pending_lookups")
data class PendingLookupEntity(
    @PrimaryKey val clientId: String,
    val profileId: String,
    val listId: String,
    val lemma: String,
    val createdAt: Long,
    // "queued" = czeka na flush; "needs_review" = flush nie znalazł pewnego dopasowania.
    val status: String = "queued",
    // Zserializowana lista LookupCandidate (propozycje „czy chodziło Ci o…").
    val suggestionsJson: String? = null,
)

@Entity(tableName = "pending_undos")
data class PendingUndoEntity(
    @PrimaryKey val clientId: String,
    val srsJson: String,
    val blockedReason: String? = null,
)

@Entity(tableName = "local_settings")
data class LocalSettingsEntity(
    @PrimaryKey val userKey: String = "me",
    val practiceInputPref: String = "flashcard",
    val practiceDirection: String = "l2_to_l1",
    val typingTolerance: String = "tolerate",
    val newCardsPerDay: Int = 20,
    val theme: String = "system",
    val jsonBlob: String = "{}",
)

@Entity(tableName = "sync_meta")
data class SyncMetaEntity(
    @PrimaryKey val profileId: String,
    val lastPulledAt: String? = null,
    val lastSyncedAt: Long = 0L,
    /** Kursor serwera; przesuwany wyłącznie w transakcji zastosowania całego pull. */
    val cursor: String? = null,
    val lastAttemptAt: Long? = null,
    /** Tylko pełny udany zakres profilu (push + outbox + pull). */
    val lastSuccessAt: Long? = null,
    val lastError: String? = null,
)

/** Cached active language profile for offline practice. */
@Entity(tableName = "cached_profile")
data class CachedProfileEntity(
    @PrimaryKey val id: String,
    val nativeLang: String,
    val learningLang: String,
    val cefrLevel: String = "A2",
    val selectedTensesJson: String = "[]",
    val isActive: Boolean = true,
    val jsonBlob: String = "{}",
)

/**
 * Jedyny rekord właściciela lokalnej bazy (E-001/F-003/T-002). Nie jest kasowany przy logout;
 * generation rośnie przy każdym loginie/reauth/logout, więc stary kontekst nie pasuje ponownie.
 */
@Entity(tableName = "session_owner")
data class SessionOwnerEntity(
    @PrimaryKey val id: Int = 0,
    val ownerUserId: String? = null,
    val generation: Long = 0,
    val phase: String = OwnerPhase.SIGNED_OUT,
    val transitionId: String? = null,
    /** Zgoda zapisana razem z `logging_out`; recovery nie wywodzi jej z samej fazy. */
    val logoutDisposition: String? = null,
    /** Fingerprint kolejek, których utratę użytkownik potwierdził (tylko `discard_confirmed`). */
    val acceptedUnsentFingerprint: String? = null,
)

object LogoutDisposition {
    const val REQUIRE_EMPTY = "require_empty"
    const val DISCARD_CONFIRMED = "discard_confirmed"
}

object OwnerPhase {
    const val SIGNED_OUT = "signed_out"
    const val INSTALLING = "installing"
    const val ACTIVE = "active"
    const val LOGGING_OUT = "logging_out"
    const val LEGACY_UNCLAIMED = "legacy_unclaimed"
}

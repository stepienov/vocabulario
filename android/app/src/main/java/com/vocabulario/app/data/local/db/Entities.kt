package com.vocabulario.app.data.local.db

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "cached_cards")
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
    val updatedAt: Long = 0L,
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
)

@Entity(tableName = "local_settings")
data class LocalSettingsEntity(
    @PrimaryKey val userKey: String = "me",
    val practiceInputPref: String = "choice",
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
)

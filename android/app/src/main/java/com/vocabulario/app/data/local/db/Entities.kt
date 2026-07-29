package com.vocabulario.app.data.local.db

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "cached_cards")
data class CachedCardEntity(
    @PrimaryKey val id: String,
    val profileId: String,
    val lemmaL2: String,
    val glossPrimary: String?,
    val pos: String?,
    val contentJson: String,
    val status: String,
    val nextReviewAt: Long?,
    val direction: String?,
)

@Entity(tableName = "pending_reviews")
data class PendingReviewEntity(
    @PrimaryKey(autoGenerate = true) val localId: Long = 0,
    val cardId: String,
    val grade: String,
    val mode: String,
    val direction: String,
    val correct: Boolean,
    val answer: String?,
    val createdAt: Long,
)

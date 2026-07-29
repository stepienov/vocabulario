package com.vocabulario.app.data.local

import android.content.Context
import androidx.room.Room
import com.vocabulario.app.data.local.db.AppDatabase
import com.vocabulario.app.data.local.db.CachedCardEntity
import com.vocabulario.app.data.local.db.PendingReviewEntity
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class OfflineStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val db = Room.databaseBuilder(context, AppDatabase::class.java, "vocabulario.db").build()
    private val cardDao = db.cachedCardDao()
    private val reviewDao = db.pendingReviewDao()
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun cacheQueue(
        profileId: String,
        items: List<Triple<String, String?, JsonObject>>,
        statuses: Map<String, Pair<String, Long?>>,
        directions: Map<String, String?>,
    ) {
        cardDao.clearProfile(profileId)
        val entities = items.map { (cardId, gloss, content) ->
            val srs = statuses[cardId]
            CachedCardEntity(
                id = cardId,
                profileId = profileId,
                lemmaL2 = content["lemma"]?.toString()?.trim('"') ?: "",
                glossPrimary = gloss,
                pos = content["pos"]?.toString()?.trim('"'),
                contentJson = Json.encodeToString(JsonObject.serializer(), content),
                status = srs?.first ?: "new",
                nextReviewAt = srs?.second,
                direction = directions[cardId],
            )
        }
        cardDao.upsertAll(entities)
    }

    suspend fun localQueue(profileId: String, newLimit: Int): List<CachedCardEntity> {
        val now = System.currentTimeMillis()
        val all = cardDao.forProfile(profileId)
        val due = all.filter { card ->
            when (card.status) {
                "new" -> false
                else -> card.nextReviewAt == null || card.nextReviewAt <= now
            }
        }.sortedBy { it.nextReviewAt ?: 0L }
        val newCards = all.filter { it.status == "new" }
            .let { if (newLimit > 0) it.take(newLimit) else it }
        return due + newCards
    }

    suspend fun cacheCardsFromList(profileId: String, cards: List<com.vocabulario.app.data.api.CardResponse>) {
        val entities = cards.map { card ->
            CachedCardEntity(
                id = card.id,
                profileId = profileId,
                lemmaL2 = card.lemma_l2,
                glossPrimary = card.gloss_primary,
                pos = card.pos,
                contentJson = Json.encodeToString(JsonObject.serializer(), card.content),
                status = "new",
                nextReviewAt = null,
                direction = null,
            )
        }
        cardDao.upsertAll(entities)
    }

    suspend fun enqueueReview(review: PendingReviewEntity) {
        reviewDao.insert(review)
    }

    suspend fun pendingReviews(): List<PendingReviewEntity> = reviewDao.all()

    suspend fun removePendingReview(id: Long) = reviewDao.delete(id)

    fun parseContent(raw: String): JsonObject =
        runCatching { json.parseToJsonElement(raw) as JsonObject }.getOrElse { buildJsonObject { } }
}

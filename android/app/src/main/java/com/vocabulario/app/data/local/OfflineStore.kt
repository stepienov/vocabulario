package com.vocabulario.app.data.local

import android.content.Context
import androidx.room.Room
import com.vocabulario.app.data.api.SyncCardItem
import com.vocabulario.app.data.api.SyncPullResponse
import com.vocabulario.app.data.api.SyncSrsState
import com.vocabulario.app.data.api.UserSettingsResponse
import com.vocabulario.app.data.local.db.AppDatabase
import com.vocabulario.app.data.local.db.CachedCardEntity
import com.vocabulario.app.data.local.db.LocalSettingsEntity
import com.vocabulario.app.data.local.db.PendingReviewEntity
import com.vocabulario.app.data.local.db.SyncMetaEntity
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class OfflineStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val db = Room.databaseBuilder(context, AppDatabase::class.java, "vocabulario.db")
        .fallbackToDestructiveMigration()
        .build()
    private val cardDao = db.cachedCardDao()
    private val reviewDao = db.pendingReviewDao()
    private val settingsDao = db.localSettingsDao()
    private val syncMetaDao = db.syncMetaDao()
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun applyPull(profileId: String, pull: SyncPullResponse, fullReplace: Boolean) {
        saveSettings(pull.settings)
        if (fullReplace) {
            cardDao.clearProfile(profileId)
        }
        if (pull.deleted_card_ids.isNotEmpty()) {
            cardDao.deleteIds(pull.deleted_card_ids)
        }
        val entities = pull.cards.map { it.toEntity() }
        if (entities.isNotEmpty()) {
            cardDao.upsertAll(entities)
        }
        syncMetaDao.upsert(
            SyncMetaEntity(
                profileId = profileId,
                lastPulledAt = pull.server_time,
                lastSyncedAt = System.currentTimeMillis(),
            ),
        )
    }

    suspend fun lastPulledAt(profileId: String): String? =
        syncMetaDao.get(profileId)?.lastPulledAt

    suspend fun saveSettings(settings: UserSettingsResponse) {
        settingsDao.upsert(
            LocalSettingsEntity(
                practiceInputPref = settings.practice_input_pref,
                practiceDirection = settings.practice_direction,
                typingTolerance = settings.typing_tolerance,
                newCardsPerDay = settings.new_cards_per_day,
                theme = settings.theme,
                jsonBlob = json.encodeToString(UserSettingsResponse.serializer(), settings),
            ),
        )
    }

    suspend fun localSettings(): LocalSettingsEntity? = settingsDao.get()

    suspend fun localUserSettings(): UserSettingsResponse? {
        val raw = settingsDao.get()?.jsonBlob ?: return null
        return runCatching { json.decodeFromString(UserSettingsResponse.serializer(), raw) }.getOrNull()
    }

    suspend fun learningCards(profileId: String): List<CachedCardEntity> =
        cardDao.learningCards(profileId)

    suspend fun cardById(id: String): CachedCardEntity? = cardDao.byId(id)

    suspend fun localQueue(profileId: String, newLimit: Int): List<CachedCardEntity> {
        val now = System.currentTimeMillis()
        val all = cardDao.learningCards(profileId)
        val due = all.filter { card ->
            card.status != "new" && (card.nextReviewAt == null || card.nextReviewAt <= now)
        }.sortedBy { it.nextReviewAt ?: 0L }
        val newCards = all.filter { it.status == "new" }
            .let { if (newLimit > 0) it.take(newLimit) else it }
        return due + newCards
    }

    suspend fun applyReviewLocally(
        cardId: String,
        grade: String,
        correct: Boolean,
        nowMs: Long = System.currentTimeMillis(),
    ): CachedCardEntity? {
        val card = cardDao.byId(cardId) ?: return null
        val updated = LocalFsrs.apply(card, grade, correct, nowMs)
        cardDao.update(updated)
        return updated
    }

    suspend fun applyServerSrs(states: List<SyncSrsState>) {
        for (srs in states) {
            val card = cardDao.byId(srs.card_id) ?: continue
            cardDao.update(card.withSrs(srs))
        }
    }

    suspend fun enqueueReview(review: PendingReviewEntity) {
        reviewDao.insert(review)
    }

    suspend fun pendingReviews(): List<PendingReviewEntity> = reviewDao.all()

    suspend fun removePendingReviews(clientIds: List<String>) {
        if (clientIds.isNotEmpty()) reviewDao.deleteIds(clientIds)
    }

    suspend fun pendingCount(): Int = reviewDao.count()

    suspend fun cacheCardsFromList(
        profileId: String,
        cards: List<com.vocabulario.app.data.api.CardResponse>,
    ) {
        val entities = cards.map { card ->
            CachedCardEntity(
                id = card.id,
                profileId = profileId,
                lemmaL2 = card.lemma_l2,
                glossPrimary = card.gloss_primary,
                pos = card.pos,
                contentJson = Json.encodeToString(JsonObject.serializer(), card.content),
                enrichmentStatus = card.enrichment_status,
                status = card.srs_status ?: "new",
                nextReviewAt = null,
                intervalDays = card.srs_interval_days ?: 0.0,
            )
        }
        cardDao.upsertAll(entities)
    }

    fun parseContent(raw: String): JsonObject =
        runCatching { json.parseToJsonElement(raw) as JsonObject }.getOrElse { buildJsonObject { } }

    private fun SyncCardItem.toEntity(): CachedCardEntity {
        val srs = this.srs
        return CachedCardEntity(
            id = id,
            profileId = profile_id,
            deckId = deck_id,
            lemmaL2 = lemma_l2,
            glossPrimary = gloss_primary,
            pos = pos,
            contentJson = Json.encodeToString(JsonObject.serializer(), content),
            enrichmentStatus = enrichment_status,
            status = srs?.status ?: "new",
            nextReviewAt = srs?.next_review_at?.toEpochMillis(),
            lastReviewedAt = srs?.last_reviewed_at?.toEpochMillis(),
            intervalDays = srs?.interval_days ?: 0.0,
            ease = srs?.ease ?: 2.5,
            repetitions = srs?.repetitions ?: 0,
            lapses = srs?.lapses ?: 0,
            stability = srs?.stability,
            difficulty = srs?.difficulty,
            fsrsStep = srs?.fsrs_step,
            lastGrade = srs?.last_grade,
            updatedAt = updated_at?.toEpochMillis() ?: System.currentTimeMillis(),
        )
    }

    private fun CachedCardEntity.withSrs(srs: SyncSrsState): CachedCardEntity = copy(
        status = srs.status,
        nextReviewAt = srs.next_review_at?.toEpochMillis(),
        lastReviewedAt = srs.last_reviewed_at?.toEpochMillis(),
        intervalDays = srs.interval_days,
        ease = srs.ease,
        repetitions = srs.repetitions,
        lapses = srs.lapses,
        stability = srs.stability,
        difficulty = srs.difficulty,
        fsrsStep = srs.fsrs_step,
        lastGrade = srs.last_grade,
        updatedAt = System.currentTimeMillis(),
    )

    private fun String.toEpochMillis(): Long? =
        runCatching { Instant.parse(this).toEpochMilli() }.getOrNull()
}

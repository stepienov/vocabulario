package com.vocabulario.app.data

import com.vocabulario.app.data.api.CardCreateRequest
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.CheckAnswerResponse
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.DistractorsRequest
import com.vocabulario.app.data.api.DistractorsResponse
import com.vocabulario.app.data.api.FavoriteCreate
import com.vocabulario.app.data.api.FavoriteResponse
import com.vocabulario.app.data.api.LanguageProfileCreate
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.LanguageProfileUpdate
import com.vocabulario.app.data.api.LookupRequest
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.ReviewRequest
import com.vocabulario.app.data.api.SrsQueueResponse
import com.vocabulario.app.data.api.UserSettingsResponse
import com.vocabulario.app.data.api.UserSettingsUpdate
import com.vocabulario.app.data.api.UserUpdate
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.local.db.PendingReviewEntity
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LearningRepository @Inject constructor(
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
    private val offlineStore: OfflineStore,
) {
    private val json = Json { ignoreUnknownKeys = true }
    suspend fun activeProfileId(): String =
        tokenStore.activeProfileId.first() ?: error("Brak aktywnego profilu językowego")

    suspend fun lookup(text: String): LookupResponse {
        val profileId = activeProfileId()
        return api.lookup(LookupRequest(text = text, profile_id = profileId))
    }

    suspend fun createCard(
        lemma: String,
        pos: String?,
        gloss: String?,
        lexicalEntryId: String?,
    ): CardResponse {
        val profileId = activeProfileId()
        return api.createCard(
            CardCreateRequest(
                lemma = lemma,
                pos = pos,
                gloss = gloss,
                profile_id = profileId,
                lexical_entry_id = lexicalEntryId,
            )
        )
    }

    suspend fun listCards(): List<CardResponse> {
        val profileId = activeProfileId()
        return runCatching { api.listCards(profileId) }
            .onSuccess { offlineStore.cacheCardsFromList(profileId, it) }
            .getOrElse {
                offlineStore.localQueue(profileId, newLimit = Int.MAX_VALUE).map { local ->
                    CardResponse(
                        id = local.id,
                        lemma_l2 = local.lemmaL2,
                        pos = local.pos,
                        gloss_primary = local.glossPrimary,
                        content = offlineStore.parseContent(local.contentJson),
                        lexical_entry_id = null,
                        created_at = "",
                        enrichment_status = "ready",
                    )
                }
            }
    }

    suspend fun addFavorite(lemma: String, pos: String?, gloss: String?) {
        val profileId = activeProfileId()
        api.addFavorite(
            FavoriteCreate(
                lemma = lemma,
                pos = pos,
                gloss = gloss,
                profile_id = profileId,
            )
        )
    }

    suspend fun listFavorites(): List<FavoriteResponse> {
        val profileId = activeProfileId()
        return api.listFavorites(profileId)
    }

    suspend fun getQueue(): SrsQueueResponse {
        val profileId = activeProfileId()
        val settings = runCatching { getSettings() }.getOrNull()
        val newLimit = settings?.new_cards_per_day ?: 20
        return runCatching { api.srsQueue(profileId) }
            .onSuccess { response ->
                val allItems = response.due + response.newCards
                offlineStore.cacheQueue(
                    profileId = profileId,
                    items = allItems.map { Triple(it.card_id, it.gloss_primary, it.content) },
                    statuses = allItems.associate { it.card_id to (it.status to null as Long?) },
                    directions = allItems.associate { it.card_id to it.direction },
                )
            }
            .getOrElse {
                val local = offlineStore.localQueue(profileId, newLimit)
                val due = local.filter { it.status != "new" }.map { it.toQueueItem() }
                val newCards = local.filter { it.status == "new" }.map { it.toQueueItem() }
                SrsQueueResponse(due = due, newCards = newCards, practice_direction = settings?.practice_direction ?: "l2_to_l1")
            }
    }

    private fun com.vocabulario.app.data.local.db.CachedCardEntity.toQueueItem() =
        com.vocabulario.app.data.api.SrsQueueItem(
            card_id = id,
            lemma_l2 = lemmaL2,
            gloss_primary = glossPrimary,
            content = offlineStore.parseContent(contentJson),
            status = status,
            direction = direction,
        )

    suspend fun getDistractors(cardId: String, direction: String): DistractorsResponse {
        val profileId = activeProfileId()
        return api.srsDistractors(
            DistractorsRequest(card_id = cardId, profile_id = profileId, direction = direction),
        )
    }

    suspend fun submitReview(
        cardId: String,
        grade: String,
        mode: String,
        direction: String,
        correct: Boolean,
        answer: String? = null,
    ) {
        val request = ReviewRequest(
            card_id = cardId,
            grade = grade,
            mode = mode,
            direction = direction,
            correct = correct,
            answer = answer,
        )
        runCatching { api.srsReview(request) }
            .onFailure {
                offlineStore.enqueueReview(
                    PendingReviewEntity(
                        cardId = cardId,
                        grade = grade,
                        mode = mode,
                        direction = direction,
                        correct = correct,
                        answer = answer,
                        createdAt = System.currentTimeMillis(),
                    )
                )
            }
    }

    suspend fun syncPendingReviews() {
        for (pending in offlineStore.pendingReviews()) {
            runCatching {
                api.srsReview(
                    ReviewRequest(
                        card_id = pending.cardId,
                        grade = pending.grade,
                        mode = pending.mode,
                        direction = pending.direction,
                        correct = pending.correct,
                        answer = pending.answer,
                    )
                )
            }.onSuccess { offlineStore.removePendingReview(pending.localId) }
        }
    }

    suspend fun checkAnswer(cardId: String, answer: String, direction: String): CheckAnswerResponse =
        api.checkAnswer(
            com.vocabulario.app.data.api.CheckAnswerRequest(cardId, answer, direction)
        )

    suspend fun getSettings(): UserSettingsResponse = api.getSettings()

    suspend fun updateSettings(update: UserSettingsUpdate): UserSettingsResponse {
        val result = api.updateSettings(update)
        update.theme?.let { tokenStore.saveTheme(it) }
        return result
    }

    suspend fun listProfiles(): List<LanguageProfileResponse> = api.listProfiles()

    suspend fun getActiveProfile(): LanguageProfileResponse? {
        val profiles = listProfiles()
        return profiles.firstOrNull { it.is_active } ?: profiles.firstOrNull()
    }

    suspend fun createProfile(
        native: String,
        learning: String,
        cefr: String,
        tenses: List<String>,
    ): LanguageProfileResponse {
        val profile = api.createProfile(
            LanguageProfileCreate(
                native_lang = native,
                learning_lang = learning,
                cefr_level = cefr,
                selected_tenses = tenses,
            )
        )
        tokenStore.saveActiveProfile(profile.id)
        return profile
    }

    suspend fun activateProfile(profileId: String): LanguageProfileResponse {
        val profile = api.activateProfile(profileId)
        tokenStore.saveActiveProfile(profile.id)
        return profile
    }

    suspend fun updateProfile(
        cefr: String? = null,
        tenses: List<String>? = null,
    ): LanguageProfileResponse {
        val profileId = activeProfileId()
        return api.updateProfile(
            profileId,
            LanguageProfileUpdate(cefr_level = cefr, selected_tenses = tenses),
        )
    }

    suspend fun updateUiLang(lang: String) {
        api.updateMe(UserUpdate(ui_lang = lang))
    }

    suspend fun getMe() = api.me()

    suspend fun hasProfile(): Boolean = listProfiles().isNotEmpty()

    suspend fun syncThemeFromSettings() {
        val settings = getSettings()
        tokenStore.saveTheme(settings.theme)
    }
}

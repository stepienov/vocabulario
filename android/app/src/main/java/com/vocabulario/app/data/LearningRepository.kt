package com.vocabulario.app.data

import com.vocabulario.app.data.api.CardCreateRequest
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.CheckAnswerResponse
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.api.DistractorsRequest
import com.vocabulario.app.data.api.DistractorsResponse
import com.vocabulario.app.data.api.FavoriteCreate
import com.vocabulario.app.data.api.FavoriteResponse
import com.vocabulario.app.data.api.LanguageProfileCreate
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.LanguageProfileUpdate
import com.vocabulario.app.data.api.LookupRequest
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.SrsQueueItem
import com.vocabulario.app.data.api.SrsQueueResponse
import com.vocabulario.app.data.api.SyncPushRequest
import com.vocabulario.app.data.api.SyncReviewItem
import com.vocabulario.app.data.api.UserSettingsResponse
import com.vocabulario.app.data.api.UserSettingsUpdate
import com.vocabulario.app.data.api.UserUpdate
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.api.WordListAddWordRequest
import com.vocabulario.app.data.api.WordListCreate
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.api.WordListUpdate
import com.vocabulario.app.data.api.WordMoveRequest
import com.vocabulario.app.data.local.LocalAnswerCheck
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.local.db.PendingReviewEntity
import com.vocabulario.app.data.sync.SyncScheduler
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.coroutines.flow.first
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LearningRepository @Inject constructor(
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
    private val offlineStore: OfflineStore,
    private val syncScheduler: SyncScheduler,
) {
    private val json = Json { ignoreUnknownKeys = true }
    suspend fun activeProfileId(): String =
        tokenStore.activeProfileId.first() ?: error("Brak aktywnego profilu językowego")

    suspend fun hasSyncableSession(): Boolean {
        val token = tokenStore.peekAccessToken()
        val profile = tokenStore.activeProfileId.first()
        return !token.isNullOrBlank() && !profile.isNullOrBlank()
    }

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
        val created = api.createCard(
            CardCreateRequest(
                lemma = lemma,
                pos = pos,
                gloss = gloss,
                profile_id = profileId,
                lexical_entry_id = lexicalEntryId,
            )
        )
        runCatching { syncNow(fullReplace = true) }
        return created
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

    suspend fun listWordLists(): List<WordListResponse> {
        val profileId = activeProfileId()
        return api.listWordLists(profileId)
    }

    suspend fun createWordList(name: String): WordListResponse {
        val profileId = activeProfileId()
        return api.createWordList(WordListCreate(name = name, profile_id = profileId))
    }

    suspend fun listWords(listId: String): List<CardResponse> {
        val profileId = activeProfileId()
        return api.listWords(listId, profileId)
    }

    suspend fun addWordToList(
        listId: String,
        lemma: String,
        pos: String?,
        gloss: String?,
        lexicalEntryId: String?,
    ): CardResponse {
        val profileId = activeProfileId()
        return api.addWordToList(
            listId,
            WordListAddWordRequest(
                lemma = lemma,
                pos = pos,
                gloss = gloss,
                lexical_entry_id = lexicalEntryId,
                profile_id = profileId,
            ),
        )
    }

    suspend fun renameWordList(listId: String, name: String): WordListResponse {
        val profileId = activeProfileId()
        return api.renameWordList(listId, profileId, WordListUpdate(name = name))
    }

    suspend fun deleteWordList(listId: String) {
        val profileId = activeProfileId()
        val response = api.deleteWordList(listId, profileId)
        if (!response.isSuccessful) {
            throw retrofit2.HttpException(response)
        }
    }

    suspend fun deleteCard(cardId: String) {
        val profileId = activeProfileId()
        val response = api.deleteCard(cardId, profileId)
        if (!response.isSuccessful) {
            throw retrofit2.HttpException(response)
        }
    }

    suspend fun moveCard(cardId: String, targetListId: String): CardResponse {
        val profileId = activeProfileId()
        return api.moveCard(cardId, WordMoveRequest(target_list_id = targetListId, profile_id = profileId))
    }

    suspend fun dashboardStats(days: Int = 7): DashboardStatsResponse {
        val profileId = activeProfileId()
        return api.dashboardStats(profileId, days)
    }

    suspend fun getQueue(): SrsQueueResponse {
        val profileId = activeProfileId()
        // Odśwież mirror gdy jest net; kolejka zawsze z Room (local-first).
        runCatching { syncNow(fullReplace = true) }
        val settings = runCatching { getSettings() }.getOrNull()
        val newLimit = settings?.new_cards_per_day ?: 20
        val directionPref = settings?.practice_direction ?: "l2_to_l1"
        val local = offlineStore.localQueue(profileId, newLimit)
        if (local.isNotEmpty()) {
            val due = local.filter { it.status != "new" }.map { it.toQueueItem(directionPref) }
            val newCards = local.filter { it.status == "new" }.map { it.toQueueItem(directionPref) }
            return SrsQueueResponse(
                due = due,
                newCards = newCards,
                practice_direction = if (directionPref == "random") "l2_to_l1" else directionPref,
            )
        }
        // Fallback: stare API kolejki (pierwsze uruchomienie / pusty Room)
        return runCatching { api.srsQueue(profileId) }.getOrElse {
            SrsQueueResponse(due = emptyList(), newCards = emptyList(), practice_direction = "l2_to_l1")
        }
    }

    private fun com.vocabulario.app.data.local.db.CachedCardEntity.toQueueItem(
        directionPref: String,
    ): SrsQueueItem {
        val dir = when (directionPref) {
            "random" -> if (kotlin.random.Random.nextBoolean()) "l2_to_l1" else "l1_to_l2"
            else -> directionPref
        }
        return SrsQueueItem(
            card_id = id,
            lemma_l2 = lemmaL2,
            gloss_primary = glossPrimary,
            content = offlineStore.parseContent(contentJson),
            status = status,
            direction = direction ?: dir,
        )
    }

    suspend fun getDistractors(cardId: String, direction: String): DistractorsResponse {
        val profileId = activeProfileId()
        return runCatching {
            api.srsDistractors(
                DistractorsRequest(card_id = cardId, profile_id = profileId, direction = direction),
            )
        }.getOrElse { localDistractors(profileId, cardId, direction) }
    }

    private suspend fun localDistractors(
        profileId: String,
        cardId: String,
        direction: String,
    ): DistractorsResponse {
        val card = offlineStore.cardById(cardId) ?: error("Brak karty offline")
        val content = offlineStore.parseContent(card.contentJson)
        val correctText = if (direction == "l2_to_l1") {
            card.glossPrimary ?: LocalAnswerCheck.collectAnswers(content, direction).firstOrNull().orEmpty()
        } else {
            card.lemmaL2
        }
        val others = offlineStore.learningCards(profileId)
            .filter { it.id != cardId }
            .shuffled()
            .take(7)
        val options = buildList {
            add(
                ChoiceOption(
                    text = correctText,
                    lemma_l2 = card.lemmaL2,
                    gloss = card.glossPrimary,
                    pos = card.pos,
                    card_id = card.id,
                    in_learning = true,
                    is_correct = true,
                ),
            )
            others.forEach { o ->
                val text = if (direction == "l2_to_l1") {
                    o.glossPrimary ?: o.lemmaL2
                } else {
                    o.lemmaL2
                }
                add(
                    ChoiceOption(
                        text = text,
                        lemma_l2 = o.lemmaL2,
                        gloss = o.glossPrimary,
                        pos = o.pos,
                        card_id = o.id,
                        in_learning = true,
                        is_correct = false,
                    ),
                )
            }
        }.shuffled()
        return DistractorsResponse(options = options, direction = direction)
    }

    suspend fun submitReview(
        cardId: String,
        grade: String,
        mode: String,
        direction: String,
        correct: Boolean,
        answer: String? = null,
    ) {
        val clientId = UUID.randomUUID().toString()
        val nowMs = System.currentTimeMillis()
        offlineStore.applyReviewLocally(cardId, grade, correct, nowMs)
        offlineStore.enqueueReview(
            PendingReviewEntity(
                clientId = clientId,
                cardId = cardId,
                grade = grade,
                mode = mode,
                direction = direction,
                correct = correct,
                answer = answer,
                createdAt = nowMs,
            ),
        )
        runCatching { pushOutbox() }
        // Jak netu nie ma / push padł — WorkManager dogra w tle po CONNECTED
        syncScheduler.requestNow()
    }

    /**
     * Push outbox, potem pull.
     * Jeśli push się nie uda — nie robimy pull (żeby nie nadpisać lokalnego postępu).
     */
    suspend fun syncNow(fullReplace: Boolean = true) {
        pushOutbox()
        val profileId = activeProfileId()
        val pull = api.syncPull(profileId, since = null)
        offlineStore.applyPull(profileId, pull, fullReplace = fullReplace)
        tokenStore.saveTheme(pull.settings.theme)
    }

    suspend fun syncPendingReviews() {
        runCatching { syncNow(fullReplace = true) }
    }

    private suspend fun pushOutbox() {
        val pending = offlineStore.pendingReviews()
        if (pending.isEmpty()) return
        val body = SyncPushRequest(
            reviews = pending.map {
                SyncReviewItem(
                    client_id = it.clientId,
                    card_id = it.cardId,
                    grade = it.grade,
                    mode = it.mode,
                    direction = it.direction,
                    correct = it.correct,
                    answer = it.answer,
                    reviewed_at = Instant.ofEpochMilli(it.createdAt).toString(),
                )
            },
        )
        val result = api.syncPush(body)
        offlineStore.removePendingReviews(pending.map { it.clientId })
        offlineStore.applyServerSrs(result.srs)
    }

    suspend fun checkAnswer(cardId: String, answer: String, direction: String): CheckAnswerResponse =
        runCatching {
            api.checkAnswer(
                com.vocabulario.app.data.api.CheckAnswerRequest(cardId, answer, direction),
            )
        }.getOrElse {
            val card = offlineStore.cardById(cardId) ?: error("Brak karty offline")
            val content = offlineStore.parseContent(card.contentJson)
            val (ok, expected, typo) = LocalAnswerCheck.check(answer, content, direction)
            CheckAnswerResponse(correct = ok, expected = expected, accepted_as_typo = typo)
        }

    suspend fun getSettings(): UserSettingsResponse =
        runCatching {
            api.getSettings().also { offlineStore.saveSettings(it) }
        }.getOrElse {
            offlineStore.localUserSettings() ?: error("Brak ustawień offline")
        }

    suspend fun updateSettings(update: UserSettingsUpdate): UserSettingsResponse {
        val result = api.updateSettings(update)
        offlineStore.saveSettings(result)
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

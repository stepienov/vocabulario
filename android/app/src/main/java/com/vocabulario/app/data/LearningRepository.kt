package com.vocabulario.app.data

import com.vocabulario.app.data.api.CardCorrectionCreate
import com.vocabulario.app.data.api.CardCorrectionCreateResponse
import com.vocabulario.app.data.api.CardCorrectionResponse
import com.vocabulario.app.data.api.CorrectionQuotaResponse
import com.vocabulario.app.data.api.CardCreateRequest
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.CardHistoryResponse
import com.vocabulario.app.data.api.CardRestoreRequest
import com.vocabulario.app.data.api.CardSelfEditRequest
import com.vocabulario.app.data.api.SelfEditValidateResponse
import com.vocabulario.app.data.api.CheckAnswerResponse
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.api.DistractorsResponse
import com.vocabulario.app.data.api.DeviceRegisterRequest
import com.vocabulario.app.data.api.ImportDisplayCard
import com.vocabulario.app.data.api.ImportDisplayCommitRequest
import com.vocabulario.app.data.api.ImportDisplayCommitResponse
import com.vocabulario.app.data.api.ImportDisplayResponse
import com.vocabulario.app.data.api.ImportIngestRequest
import com.vocabulario.app.data.api.ImportJobCreateRequest
import com.vocabulario.app.data.api.ImportJobProgressResponse
import com.vocabulario.app.data.api.ImportValidateRequest
import com.vocabulario.app.data.api.ImportValidateResponse
import com.vocabulario.app.data.api.LanguageProfileCreate
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.LanguageProfileUpdate
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupRequest
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.SrsQueueItem
import com.vocabulario.app.data.api.SrsQueueResponse
import com.vocabulario.app.data.api.SyncMoveItem
import com.vocabulario.app.data.api.SyncPushRequest
import com.vocabulario.app.data.api.SyncReviewItem
import com.vocabulario.app.data.api.SrsUndoRequest
import com.vocabulario.app.data.api.SyncSrsState
import com.vocabulario.app.data.api.UserSettingsResponse
import com.vocabulario.app.data.api.UserSettingsUpdate
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.api.WordListAddWordRequest
import com.vocabulario.app.data.api.WordListCreate
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.api.WordListUpdate
import com.vocabulario.app.data.SYSTEM_LIST_NAME
import com.vocabulario.app.data.local.LocalAnswerCheck
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.local.db.PendingReviewEntity
import com.vocabulario.app.data.sync.SyncScheduler
import com.vocabulario.app.notifications.NotificationScheduler
import com.vocabulario.app.notifications.ReadyBatchTracker
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import okhttp3.MediaType.Companion.toMediaType
import retrofit2.HttpException
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
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
    private val networkMonitor: NetworkMonitor,
    private val readyBatchTracker: ReadyBatchTracker,
    private val notificationScheduler: NotificationScheduler,
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val outboxMutex = Mutex()
    private val hydratedEmptyLists = mutableSetOf<String>()

    // Serializuje opróżnianie kolejki Oczekujących. Bez tego równoległe flushe (sync + wejście
    // na listę + polling) tworzyły wiele kart z jednego stuba i paliły tokeny LLM.
    private val pendingFlushMutex = Mutex()

    private companion object {
        const val API_FAST_TIMEOUT_MS = 8_000L
        const val API_SYNC_TIMEOUT_MS = 12_000L
        const val FLUSH_LOOKUPS_TIMEOUT_MS = 30_000L

        const val OP_SETTINGS_UPDATE = "settings_update"
        const val OP_CARD_DELETE = "card_delete"
        const val OP_LIST_CREATE = "list_create"
        const val OP_LIST_RENAME = "list_rename"
        const val OP_LIST_DELETE = "list_delete"
    }

    private suspend fun <T> apiTry(
        timeoutMs: Long = API_FAST_TIMEOUT_MS,
        block: suspend () -> T,
    ): Result<T> = runCatching { withTimeout(timeoutMs) { block() } }

    private fun defaultSettings(): UserSettingsResponse = UserSettingsResponse(
        practice_input_pref = "choice",
        practice_direction = "l2_to_l1",
        typing_tolerance = "moderate",
        typo_modal_enabled = true,
        new_cards_per_day = 20,
        theme = "system",
    )

    suspend fun cachedWordLists(): List<WordListResponse> =
        offlineWordLists(activeProfileId())

    suspend fun cachedListWords(listId: String): List<CardResponse> {
        val profileId = activeProfileId()
        val lists = offlineStore.localLists(profileId)
        val meta = lists.find { it.id == listId }
            ?: lists.find { it.is_pending_inbox && listId.startsWith("local-pending-inbox-") }
        val isSystem = meta?.is_system == true || listId == "local-system-learning"
        return offlineStore.localWords(profileId, listId, isSystem = isSystem)
    }

    /**
     * Dociąga słowa listy z API i upsertuje enrichment/treść w Room.
     * Tylko do polla pending → ready; nie czyści SRS.
     */
    suspend fun refreshListWordsFromServer(listId: String): List<CardResponse> {
        if (!networkMonitor.isCurrentlyOnline() || isLocalOnlyListId(listId)) {
            return cachedListWords(listId)
        }
        val profileId = activeProfileId()
        val lists = offlineStore.localLists(profileId)
        val meta = lists.find { it.id == listId }
            ?: lists.find { it.is_pending_inbox && listId.startsWith("local-pending-inbox-") }
        val isSystem = meta?.is_system == true || listId == "local-system-learning"
        val serverListId = when {
            isSystem -> lists.find { it.is_system && !isLocalOnlyListId(it.id) }?.id
            else -> meta?.id?.takeUnless { isLocalOnlyListId(it) }
        } ?: return cachedListWords(listId)
        apiTry(timeoutMs = API_SYNC_TIMEOUT_MS) { api.listWords(serverListId, profileId) }
            .getOrNull()
            ?.let { words ->
                offlineStore.upsertCards(
                    profileId,
                    words,
                    deckId = if (isSystem) null else serverListId,
                )
            }
        return cachedListWords(listId)
    }

    private suspend fun offlineWordLists(profileId: String): List<WordListResponse> {
        val cached = offlineStore.localLists(profileId)
        if (cached.isNotEmpty()) {
            return offlineStore.withComputedWordCounts(profileId, cached)
        }
        val count = offlineStore.learningCards(profileId).size
        if (count == 0) return emptyList()
        return listOf(
            WordListResponse(
                id = "local-system-learning",
                name = SYSTEM_LIST_NAME,
                is_system = true,
                word_count = count,
            ),
        )
    }

    suspend fun activeProfileId(): String {
        tokenStore.activeProfileId.first()?.takeIf { it.isNotBlank() }?.let { return it }
        offlineStore.cachedActiveProfile()?.id?.takeIf { it.isNotBlank() }?.let { return it }
        return getActiveProfile()?.id ?: error("no_active_profile")
    }

    suspend fun hasSyncableSession(): Boolean {
        val token = tokenStore.peekAccessToken()
        val profile = tokenStore.activeProfileId.first()
        return !token.isNullOrBlank() && !profile.isNullOrBlank()
    }

    suspend fun lookup(text: String): LookupResponse {
        val profileId = activeProfileId()
        return api.lookup(LookupRequest(text = text, profile_id = profileId))
    }

    suspend fun validateImport(words: List<String>): ImportValidateResponse {
        val profileId = activeProfileId()
        return api.validateImport(ImportValidateRequest(words = words, profile_id = profileId))
    }

    /** Wklejka: tekst albo URL Quizlet / AnkiWeb. */
    suspend fun ingestImport(text: String, mode: String = "vocabulario"): ImportValidateResponse {
        val profileId = activeProfileId()
        return api.ingestImport(ImportIngestRequest(text = text, profile_id = profileId, mode = mode))
    }

    suspend fun ingestImportPreserve(text: String): ImportDisplayResponse {
        val profileId = activeProfileId()
        return api.ingestImportPreserve(
            ImportIngestRequest(text = text, profile_id = profileId, mode = "preserve"),
        )
    }

    /** Plik: CSV/TSV/TXT albo Anki .apkg / .colpkg. */
    suspend fun ingestImportFile(
        bytes: ByteArray,
        filename: String,
        mode: String = "vocabulario",
    ): ImportValidateResponse {
        val profileId = activeProfileId()
        val body = bytes.toRequestBody("application/octet-stream".toMediaType())
        val part = MultipartBody.Part.createFormData("file", filename, body)
        val profilePart = profileId.toRequestBody("text/plain".toMediaType())
        val modePart = mode.toRequestBody("text/plain".toMediaType())
        return api.ingestImportFile(part, profilePart, modePart)
    }

    suspend fun ingestImportFilePreserve(bytes: ByteArray, filename: String): ImportDisplayResponse {
        val profileId = activeProfileId()
        val body = bytes.toRequestBody("application/octet-stream".toMediaType())
        val part = MultipartBody.Part.createFormData("file", filename, body)
        val profilePart = profileId.toRequestBody("text/plain".toMediaType())
        val modePart = "preserve".toRequestBody("text/plain".toMediaType())
        return api.ingestImportFilePreserve(part, profilePart, modePart)
    }

    suspend fun createImportJob(text: String, listId: String, mode: String): ImportJobProgressResponse {
        val profileId = activeProfileId()
        return api.createImportJob(
            ImportJobCreateRequest(
                profile_id = profileId,
                list_id = listId,
                mode = mode,
                text = text,
            ),
        )
    }

    suspend fun createImportJobFile(
        bytes: ByteArray,
        filename: String,
        listId: String,
        mode: String,
    ): ImportJobProgressResponse {
        val profileId = activeProfileId()
        val body = bytes.toRequestBody("application/octet-stream".toMediaType())
        val part = MultipartBody.Part.createFormData("file", filename, body)
        return api.createImportJobFile(
            part,
            profileId.toRequestBody("text/plain".toMediaType()),
            listId.toRequestBody("text/plain".toMediaType()),
            mode.toRequestBody("text/plain".toMediaType()),
        )
    }

    suspend fun getActiveImportJob(): ImportJobProgressResponse? {
        val profileId = activeProfileId()
        return runCatching { api.getActiveImportJob(profileId) }.getOrNull()
    }

    suspend fun getImportJobProgress(jobId: String): ImportJobProgressResponse =
        api.getImportJobProgress(jobId)

    suspend fun getImportJob(jobId: String, includeItems: Boolean = true): ImportJobProgressResponse =
        api.getImportJob(jobId, includeItems)

    suspend fun commitImportJob(jobId: String): ImportJobProgressResponse =
        api.commitImportJob(jobId)

    suspend fun cancelImportJob(jobId: String): ImportJobProgressResponse =
        api.cancelImportJob(jobId)

    suspend fun commitImportDisplay(listId: String, cards: List<ImportDisplayCard>): ImportDisplayCommitResponse {
        val profileId = activeProfileId()
        val result = api.commitImportDisplay(
            ImportDisplayCommitRequest(profile_id = profileId, list_id = listId, cards = cards),
        )
        runCatching { refreshLocalAfterImport(listId) }
        return result
    }

    /**
     * Import commit pisze karty na serwerze. UI czyta tylko Room — bez tego import
     * wygląda jak pusta lista, a kolejna analiza zgłasza fałszywe duplikaty.
     */
    suspend fun refreshLocalAfterImport(listId: String?) {
        if (!networkMonitor.isCurrentlyOnline()) return
        val profileId = activeProfileId()
        apiTry { api.listWordLists(profileId) }.getOrNull()?.let { remote ->
            offlineStore.cacheLists(profileId, remote)
        }
        val lists = offlineStore.localLists(profileId)
        for (id in importRefreshListIds(listId, lists)) {
            val meta = lists.find { it.id == id } ?: continue
            val deckId = if (meta.is_system) null else id
            apiTry(timeoutMs = API_SYNC_TIMEOUT_MS) { api.listWords(id, profileId) }
                .getOrNull()
                ?.let { words ->
                    offlineStore.cacheCardsFromList(profileId, words, deckId = deckId)
                }
        }
        syncNow(fullReplace = false)
    }

    /**
     * Odzyskanie po desyncu: pusta lista online = dociągnij raz z serwera.
     * Nie rusza list lokalnych (`local-` / `local:`) i nie powtarza w tej sesji.
     */
    suspend fun hydrateListIfEmpty(listId: String): List<CardResponse> {
        val local = cachedListWords(listId)
        if (local.isNotEmpty()) return local
        if (!networkMonitor.isCurrentlyOnline() || isLocalOnlyListId(listId)) return local
        if (!hydratedEmptyLists.add(listId)) return local
        val ok = runCatching { refreshLocalAfterImport(listId) }.isSuccess
        if (!ok) hydratedEmptyLists.remove(listId)
        return cachedListWords(listId)
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
        offlineStore.upsertCards(profileId, listOf(created), deckId = null)
        watchOfflineIfPending(created)
        syncScheduler.requestNow()
        return created
    }

    suspend fun learningLemmaSet(): Set<String> {
        val profileId = activeProfileId()
        return offlineStore.learningCards(profileId)
            .flatMap { lemmaKeys(it.lemmaL2) }
            .toSet()
    }

    suspend fun isLemmaOnLearningList(lemma: String): Boolean =
        learningLemmaSet().containsLemma(lemma)

    suspend fun listCards(): List<CardResponse> {
        val profileId = activeProfileId()
        return offlineStore.localWords(profileId, listId = "", isSystem = true)
    }

    suspend fun listWordLists(): List<WordListResponse> {
        val profileId = activeProfileId()
        return offlineWordLists(profileId)
    }

    /**
     * Local-first: tworzy listę w Room (ID `local:<uuid>`) + operację outboxu. Online od razu
     * drenuje outbox (create na serwerze + remap ID), więc dalsze akcje dostają server ID.
     */
    suspend fun createWordList(name: String): WordListResponse {
        val profileId = activeProfileId()
        val trimmed = name.trim()
        if (trimmed.isEmpty()) error("empty_list_name")
        if (offlineStore.listNameClashes(profileId, trimmed)) error("list_name_exists")
        val local = offlineStore.createLocalList(profileId, trimmed)
        offlineStore.enqueueOp(
            OP_LIST_CREATE,
            buildJsonObject {
                put("localId", local.id)
                put("profileId", profileId)
                put("name", trimmed)
            }.toString(),
        )
        if (networkMonitor.isCurrentlyOnline()) {
            runCatching { drainOutboxOps() }
            offlineStore.localListByName(profileId, trimmed)?.let { return it }
        } else {
            syncScheduler.requestNow()
        }
        return offlineStore.localListById(local.id)
            ?: WordListResponse(id = local.id, name = trimmed, is_system = false)
    }

    suspend fun listWords(listId: String): List<CardResponse> = cachedListWords(listId)

    suspend fun addWordToList(
        listId: String,
        lemma: String,
        pos: String?,
        gloss: String?,
        lexicalEntryId: String?,
        entryKind: String = "lemma",
        baseLemma: String? = null,
        pattern: String? = null,
    ): CardResponse {
        val profileId = activeProfileId()
        val created = api.addWordToList(
            listId,
            WordListAddWordRequest(
                lemma = lemma,
                pos = pos,
                gloss = gloss,
                lexical_entry_id = lexicalEntryId,
                profile_id = profileId,
                entry_kind = entryKind,
                base_lemma = baseLemma,
                pattern = pattern,
            ),
        )
        val deckId = offlineStore.localLists(profileId).find { it.id == listId && it.is_system }?.let { null }
            ?: listId.takeUnless { it.startsWith("local-") }
        offlineStore.upsertCards(profileId, listOf(created), deckId = deckId)
        watchOfflineIfPending(created)
        syncScheduler.requestNow()
        return created
    }

    /** Local-first rename: Room + operacja outboxu, drenaż online. */
    suspend fun renameWordList(listId: String, name: String): WordListResponse {
        val profileId = activeProfileId()
        val trimmed = name.trim()
        if (trimmed.isEmpty()) error("empty_list_name")
        offlineStore.renameListLocally(listId, trimmed)
        offlineStore.enqueueOp(
            OP_LIST_RENAME,
            buildJsonObject {
                put("listId", listId)
                put("profileId", profileId)
                put("name", trimmed)
            }.toString(),
        )
        if (networkMonitor.isCurrentlyOnline()) runCatching { drainOutboxOps() } else syncScheduler.requestNow()
        return offlineStore.localListById(listId)
            ?: WordListResponse(id = listId, name = trimmed, is_system = false)
    }

    /** Local-first delete listy wraz z kartami + operacja outboxu, drenaż online. */
    suspend fun deleteWordList(listId: String) {
        val profileId = activeProfileId()
        val lists = offlineStore.localLists(profileId)
        if (lists.any { it.id == listId && it.is_pending_inbox }) {
            error("pending_inbox_not_deletable")
        }
        if (listId.startsWith("local-pending-inbox-")) {
            offlineStore.clearPendingLookupsForList(listId)
            return
        }
        // Lista utworzona offline (jeszcze nie na serwerze) → anuluj create, skasuj lokalnie, koniec.
        if (listId.startsWith("local:")) {
            offlineStore.removeOpsReferencing(listId)
            offlineStore.deleteListLocally(listId)
            return
        }
        val deletedCardIds = offlineStore.deleteListLocally(listId)
        for (cardId in deletedCardIds) {
            offlineStore.enqueueOp(
                OP_CARD_DELETE,
                buildJsonObject {
                    put("cardId", cardId)
                    put("profileId", profileId)
                }.toString(),
            )
        }
        offlineStore.enqueueOp(
            OP_LIST_DELETE,
            buildJsonObject {
                put("listId", listId)
                put("profileId", profileId)
            }.toString(),
        )
        if (networkMonitor.isCurrentlyOnline()) runCatching { drainOutboxOps() } else syncScheduler.requestNow()
    }

    suspend fun clearPendingInbox(listId: String) = pendingFlushMutex.withLock {
        // Pod mutexem flushu → żaden równoległy flush nie odtworzy kart podczas czyszczenia.
        val profileId = activeProfileId()
        // 1. Najpierw skasuj stuby — od tej chwili flush nie ma już czego dodać.
        offlineStore.clearPendingLookupsOnly(profileId)

        val serverInboxId = if (networkMonitor.isCurrentlyOnline()) {
            runCatching {
                api.listWordLists(profileId).find { it.is_pending_inbox }?.id
            }.getOrNull()
        } else {
            null
        }
        val inboxDeckIds = offlineStore.allPendingInboxDeckIds(profileId)
        val apiDeckIds = (inboxDeckIds + listOfNotNull(serverInboxId))
            .filter { !it.startsWith("local-pending-inbox-") }
            .distinct()

        val cardIdsToDelete = linkedSetOf<String>()
        offlineStore.pendingInboxCards(profileId).forEach { cardIdsToDelete.add(it.id) }
        if (networkMonitor.isCurrentlyOnline()) {
            for (deckId in apiDeckIds) {
                runCatching { api.listWords(deckId, profileId) }
                    .getOrNull()
                    .orEmpty()
                    .forEach { cardIdsToDelete.add(it.id) }
            }
        }

        if (networkMonitor.isCurrentlyOnline()) {
            var failed = 0
            for (cardId in cardIdsToDelete) {
                if (cardId.startsWith("pending-lookup-")) continue
                val resp = runCatching { api.deleteCard(cardId, profileId) }.getOrNull()
                val ok = resp != null && (resp.isSuccessful || resp.code() == 404)
                if (!ok) failed++
            }
            offlineStore.clearPendingInboxLocally(profileId)
            for (deckId in apiDeckIds) {
                offlineStore.cacheCardsFromList(profileId, emptyList(), deckId = deckId)
            }
            // Bez syncNow/syncPull — pull przywracał karty, których delete jeszcze nie był w tombstonach.
            if (failed > 0) error("pending_inbox_clear_incomplete")
            return@withLock
        }

        offlineStore.clearPendingInboxLocally(profileId)
        for (cardId in cardIdsToDelete) {
            if (cardId.startsWith("pending-lookup-")) continue
            offlineStore.deleteCardLocally(cardId)
            offlineStore.enqueueOp(
                OP_CARD_DELETE,
                buildJsonObject {
                    put("cardId", cardId)
                    put("profileId", profileId)
                }.toString(),
            )
        }
        syncScheduler.requestNow()
    }

    suspend fun removePendingLookupStub(cardId: String) {
        val clientId = cardId.removePrefix("pending-lookup-")
        if (clientId == cardId) return
        offlineStore.removePendingLookup(clientId)
    }

    /** Local-first delete karty: Room + operacja outboxu, drenaż online. Stuby lookupu — lokalnie. */
    suspend fun deleteCard(cardId: String) = deleteCards(listOf(cardId))

    suspend fun deleteCards(cardIds: List<String>) {
        if (cardIds.isEmpty()) return
        val profileId = activeProfileId()
        val stubs = cardIds.filter { it.startsWith("pending-lookup-") }
        val realIds = cardIds.filterNot { it.startsWith("pending-") }
        for (stub in stubs) removePendingLookupStub(stub)
        if (realIds.isNotEmpty()) {
            offlineStore.deleteCardsLocally(realIds)
            for (cardId in realIds) {
                offlineStore.enqueueOp(
                    OP_CARD_DELETE,
                    buildJsonObject {
                        put("cardId", cardId)
                        put("profileId", profileId)
                    }.toString(),
                )
            }
        }
        syncScheduler.requestNow()
    }

    suspend fun moveCard(cardId: String, targetListId: String): CardResponse {
        moveCards(listOf(cardId), targetListId)
        return localMovedCard(cardId)
    }

    suspend fun moveCards(cardIds: List<String>, targetListId: String) {
        val ready = cardIds.filterNot { it.startsWith("pending-") }
        if (ready.isEmpty()) return
        val profileId = activeProfileId()
        val lists = offlineStore.localLists(profileId).ifEmpty {
            runCatching { listWordLists() }.getOrElse { offlineStore.localLists(profileId) }
        }
        val systemId = lists.find { it.is_system }?.id
        offlineStore.moveCardsLocally(
            cardIds = ready,
            targetListId = targetListId,
            systemListId = systemId,
        )
        syncScheduler.requestNow()
    }

    private suspend fun localMovedCard(cardId: String): CardResponse {
        val local = offlineStore.cardById(cardId)
        return CardResponse(
            id = cardId,
            lemma_l2 = local?.lemmaL2.orEmpty(),
            pos = local?.pos,
            gloss_primary = local?.glossPrimary,
            content = local?.let { offlineStore.parseContent(it.contentJson) }
                ?: kotlinx.serialization.json.buildJsonObject { },
            created_at = "",
            enrichment_status = local?.enrichmentStatus ?: "ready",
            srs_status = local?.status,
            srs_interval_days = local?.intervalDays,
        )
    }

    /** Offline search: queue lemma on Pending inbox. Returns false if duplicate. */
    suspend fun enqueueOfflineLookup(lemma: String): Boolean {
        val profileId = activeProfileId()
        return offlineStore.enqueueOfflineLookup(profileId, lemma) != null
    }

    suspend fun dashboardStats(days: Int = 7): DashboardStatsResponse {
        val profileId = activeProfileId()
        val settings = getSettings()
        return offlineStore.buildDashboardStats(profileId, settings.new_cards_per_day, days)
    }

    fun requestBackgroundSync() {
        syncScheduler.requestNow()
    }

    suspend fun getQueue(): SrsQueueResponse {
        val profileId = activeProfileId()
        val settings = getSettings()
        val newLimit = settings.new_cards_per_day
        val directionPref = settings.practice_direction
        val local = offlineStore.localQueue(profileId, newLimit)
        if (local.isNotEmpty()) {
            if (networkMonitor.isCurrentlyOnline()) syncScheduler.requestNow()
            return buildSrsQueue(local, directionPref)
        }
        if (networkMonitor.isCurrentlyOnline()) {
            syncScheduler.requestNow()
        }
        return SrsQueueResponse(
            due = emptyList(),
            newCards = emptyList(),
            practice_direction = if (directionPref == "random") "l2_to_l1" else directionPref,
        )
    }

    private fun buildSrsQueue(
        local: List<com.vocabulario.app.data.local.db.CachedCardEntity>,
        directionPref: String,
    ): SrsQueueResponse {
        val due = local.filter { it.status != "new" }.map { it.toQueueItem(directionPref) }
        val newCards = local.filter { it.status == "new" }.map { it.toQueueItem(directionPref) }
        return SrsQueueResponse(
            due = due,
            newCards = newCards,
            practice_direction = if (directionPref == "random") "l2_to_l1" else directionPref,
        )
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
        return localDistractors(profileId, cardId, direction)
    }

    private suspend fun localDistractors(
        profileId: String,
        cardId: String,
        direction: String,
    ): DistractorsResponse {
        val card = offlineStore.cardById(cardId) ?: error("offline_card")
        val content = offlineStore.parseContent(card.contentJson)
        val correctText = if (direction == "l2_to_l1") {
            card.glossPrimary ?: LocalAnswerCheck.collectAnswers(content, direction).firstOrNull().orEmpty()
        } else {
            card.lemmaL2
        }
        val others = offlineStore.allCards(profileId).filter { it.id != cardId }
        fun findLearning(lemma: String?) =
            lemmaKeys(lemma).takeIf { it.isNotEmpty() }?.let { keys ->
                others.firstOrNull { lemmaKeys(it.lemmaL2).any { key -> key in keys } }
            }
        data class DistSeed(val text: String, val lemmaL2: String?, val gloss: String?, val pos: String?)
        val seeds = linkedMapOf<String, DistSeed>()
        fun maybeAdd(text: String?, lemmaL2: String?, gloss: String?, pos: String?) {
            val t = text?.trim().orEmpty()
            if (t.isBlank() || !isValidPracticeDistractor(t)) return
            if (t.equals(correctText, ignoreCase = true)) return
            seeds.putIfAbsent(t.lowercase(), DistSeed(t, lemmaL2, gloss, pos))
        }
        others.forEach { o ->
            val text = if (direction == "l2_to_l1") o.glossPrimary ?: o.lemmaL2 else o.lemmaL2
            maybeAdd(text, o.lemmaL2, o.glossPrimary, o.pos)
        }
        content["similar_words"].asJsonArray()?.forEach { el ->
            val lemma = when (el) {
                is kotlinx.serialization.json.JsonObject -> el["lemma"].asJsonString()
                is kotlinx.serialization.json.JsonPrimitive -> el.content
                else -> null
            }
            val gloss = (el as? kotlinx.serialization.json.JsonObject)?.get("gloss_l1")?.asJsonString()
            val pos = (el as? kotlinx.serialization.json.JsonObject)?.get("pos")?.asJsonString()
            val text = if (direction == "l2_to_l1") {
                gloss?.takeIf { it.isNotBlank() } ?: lemma
            } else {
                lemma
            }
            maybeAdd(text, lemma, gloss, pos)
        }
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
            val used = mutableSetOf(correctText.lowercase())
            for (seed in seeds.values) {
                if (size >= 8) break
                if (!used.add(seed.text.lowercase())) continue
                val source = findLearning(seed.lemmaL2)
                add(
                    ChoiceOption(
                        text = seed.text,
                        lemma_l2 = source?.lemmaL2 ?: seed.lemmaL2 ?: seed.text,
                        gloss = seed.gloss ?: source?.glossPrimary,
                        pos = seed.pos ?: source?.pos,
                        card_id = source?.id,
                        in_learning = source != null,
                        is_correct = false,
                    ),
                )
            }
            for (o in others.shuffled()) {
                if (size >= 8) break
                val text = if (direction == "l2_to_l1") {
                    o.glossPrimary ?: o.lemmaL2
                } else {
                    o.lemmaL2
                }
                if (text.isBlank() || !isValidPracticeDistractor(text) || !used.add(text.lowercase())) continue
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

    suspend fun cardSrsSnapshot(cardId: String): SyncSrsState? =
        offlineStore.cardSrsSnapshot(cardId)

    suspend fun undoReview(clientId: String, previous: SyncSrsState) {
        offlineStore.undoReviewLocally(clientId, previous)
        runCatching {
            api.srsUndo(SrsUndoRequest(client_id = clientId, previous_srs = previous))
        }.onFailure {
            offlineStore.enqueuePendingUndo(clientId, previous)
        }
        syncScheduler.requestNow()
    }

    suspend fun submitReview(
        cardId: String,
        grade: String,
        mode: String,
        direction: String,
        correct: Boolean,
        answer: String? = null,
    ): String {
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
        syncScheduler.requestNow()
        return clientId
    }

    /**
     * Push moves + reviews, flush offline lookups, then pull.
     * Flush jest osobno i **pierwszy** — zatruty outbox nie może blokować opróżniania Oczekujących.
     */
    private val syncMutex = Mutex()

    suspend fun syncNow(fullReplace: Boolean = false) {
        if (!networkMonitor.isCurrentlyOnline()) return
        if (!syncMutex.tryLock()) return
        try {
            runCatching { withTimeout(FLUSH_LOOKUPS_TIMEOUT_MS) { flushPendingLookups() } }
            runCatching { withTimeout(API_SYNC_TIMEOUT_MS) { pushOutbox() } }
            runCatching {
                withTimeout(API_SYNC_TIMEOUT_MS) {
                    val profileId = activeProfileId()
                    val lastPulled = offlineStore.lastPulledAt(profileId)
                    val doFull = fullReplace || lastPulled == null
                    val since = if (doFull) null else lastPulled
                    val pull = api.syncPull(profileId, since = since)
                    offlineStore.applyPull(profileId, pull, fullReplace = doFull)
                    offlineStore.localUserSettings()?.theme?.let { tokenStore.saveTheme(it) }
                    val needProfiles = doFull || offlineStore.cachedProfiles().isEmpty()
                    if (needProfiles) {
                        runCatching { api.listProfiles() }.getOrNull()?.let { applyRemoteProfiles(it) }
                    }
                }
            }
            evaluateReadyBatches()
        } finally {
            syncMutex.unlock()
        }
    }

    suspend fun evaluateReadyBatches() {
        val settings = runCatching { getSettings() }.getOrNull() ?: return
        val on = settings.study_reminder_enabled || settings.cards_ready_push_enabled
        val profileId = runCatching { activeProfileId() }.getOrNull() ?: return
        val statusById = offlineStore.allCards(profileId).associate { it.id to it.enrichmentStatus }
        readyBatchTracker.evaluate(statusById, on)
        if (readyBatchTracker.hasWatches()) notificationScheduler.scheduleEnrichmentSoon()
    }

    fun watchImportCards(ids: Collection<String>) {
        readyBatchTracker.watchImport(ids)
        if (ids.any { it.isNotBlank() }) notificationScheduler.scheduleEnrichmentSoon()
    }

    private fun watchOfflineIfPending(card: CardResponse) {
        if (card.enrichment_status == "pending" || card.enrichment_status == "awaiting_network") {
            readyBatchTracker.watchOffline(listOf(card.id))
            notificationScheduler.scheduleEnrichmentSoon()
        }
    }

    /** Opróżnia kolejkę offline lookupów (Oczekujące) — można wołać niezależnie od sync/outboxu. */
    suspend fun flushPendingLookupsIfNeeded() {
        if (!networkMonitor.isCurrentlyOnline()) return
        flushPendingLookups()
    }

    suspend fun hasPendingLookups(): Boolean = offlineStore.pendingLookups().isNotEmpty()

    /** Czy są słowa czekające na flush (bez tych już oznaczonych „wymaga sprawdzenia"). */
    suspend fun hasQueuedLookups(): Boolean = offlineStore.queuedPendingLookups().isNotEmpty()

    suspend fun syncPendingReviews() {
        runCatching { syncNow() }
    }

    // ---- Reaktywne strumienie (Room jako źródło prawdy dla UI) ----

    @OptIn(FlowPreview::class)
    /** Emituje przy realnej zmianie list (debounce chroni przed lawiną przy sync / toggle sieci). */
    fun listsChanges(profileId: String): Flow<Unit> =
        offlineStore.listsSignature(profileId)
            .debounce(400)
            .distinctUntilChanged()
            .map { }

    @OptIn(FlowPreview::class)
    /** Emituje przy realnej zmianie kart profilu (id+deckId, bez updatedAt). */
    fun cardsChanges(profileId: String): Flow<Unit> =
        offlineStore.cardsSignature(profileId)
            .debounce(400)
            .distinctUntilChanged()
            .map { }

    /** Ustawienia jako strumień — odzwierciedla zmiany lokalne i te dociągnięte z sync. */
    fun observeSettings(): Flow<UserSettingsResponse?> =
        offlineStore.observeSettings().distinctUntilChanged()

    private suspend fun flushPendingUndos() {
        for (item in offlineStore.pendingUndos()) {
            val srs = runCatching {
                json.decodeFromString(SyncSrsState.serializer(), item.srsJson)
            }.getOrNull() ?: continue
            runCatching {
                api.srsUndo(SrsUndoRequest(client_id = item.clientId, previous_srs = srs))
            }.onSuccess {
                offlineStore.removePendingUndo(item.clientId)
            }
        }
    }

    /**
     * Drenaż ujednoliconego outboxu (mutacje Z3) przez istniejące, idempotentne endpointy REST.
     * FIFO: zatrzymuje się na pierwszym twardym błędzie, by nie wyprzedzić zależności
     * (np. rename/delete listy przed jej create). Offline = no-op (bez naliczania prób).
     */
    private suspend fun drainOutboxOps() {
        if (!networkMonitor.isCurrentlyOnline()) return
        outboxMutex.withLock {
            offlineStore.unparkAuthFailures()
            for (op in offlineStore.pendingOps()) {
                try {
                    applyOutboxOp(op)
                    offlineStore.removeOp(op)
                } catch (io: java.io.IOException) {
                    // Utrata sieci w trakcie — nie naliczaj próby, spróbuj przy następnym syncu.
                    break
                } catch (http: retrofit2.HttpException) {
                    // 401/5xx: token albo BE. Nie parkuj — Authenticator odświeży, kolejny sync dociągnie.
                    if (http.code() == 401 || http.code() == 408 || http.code() >= 500) break
                    offlineStore.markOpFailed(op, http.message)
                    break
                } catch (e: Exception) {
                    offlineStore.markOpFailed(op, e.message)
                    break
                }
            }
        }
    }

    private suspend fun applyOutboxOp(op: com.vocabulario.app.data.local.db.OutboxOpEntity) {
        when (op.type) {
            OP_SETTINGS_UPDATE -> {
                val update = json.decodeFromString(UserSettingsUpdate.serializer(), op.payloadJson)
                api.updateSettings(update)
                // Lokalny Room jest źródłem prawdy — echo z PUT może być starsze niż kolejny tap.
            }
            OP_CARD_DELETE -> {
                val p = json.parseToJsonElement(op.payloadJson).jsonObject
                val cardId = p["cardId"]?.jsonPrimitive?.content ?: return
                val profileId = p["profileId"]?.jsonPrimitive?.content ?: activeProfileId()
                val resp = api.deleteCard(cardId, profileId)
                if (!resp.isSuccessful && resp.code() != 404) throw retrofit2.HttpException(resp)
            }
            OP_LIST_RENAME -> {
                val p = json.parseToJsonElement(op.payloadJson).jsonObject
                val listId = p["listId"]?.jsonPrimitive?.content ?: return
                if (listId.startsWith("local:")) return // create jeszcze nie zremapował — poczekaj
                val profileId = p["profileId"]?.jsonPrimitive?.content ?: activeProfileId()
                val name = p["name"]?.jsonPrimitive?.content ?: return
                try {
                    api.renameWordList(listId, profileId, WordListUpdate(name = name))
                } catch (e: retrofit2.HttpException) {
                    if (e.code() != 404) throw e // 404 = lista już nie istnieje → uznaj za zrobione
                }
            }
            OP_LIST_CREATE -> {
                val p = json.parseToJsonElement(op.payloadJson).jsonObject
                val localId = p["localId"]?.jsonPrimitive?.content ?: return
                if (!localId.startsWith("local:")) return // już zremapowane
                val profileId = p["profileId"]?.jsonPrimitive?.content ?: activeProfileId()
                val name = p["name"]?.jsonPrimitive?.content ?: return
                val created = try {
                    api.createWordList(WordListCreate(name = name, profile_id = profileId))
                } catch (e: retrofit2.HttpException) {
                    if (e.code() == 409) {
                        api.listWordLists(profileId).firstOrNull { it.name.equals(name, ignoreCase = true) }
                            ?: throw e
                    } else {
                        throw e
                    }
                }
                offlineStore.remapLocalListId(localId, created.id)
            }
            OP_LIST_DELETE -> {
                val p = json.parseToJsonElement(op.payloadJson).jsonObject
                val listId = p["listId"]?.jsonPrimitive?.content ?: return
                if (listId.startsWith("local:")) return // nigdy nie było na serwerze
                val profileId = p["profileId"]?.jsonPrimitive?.content ?: activeProfileId()
                val resp = api.deleteWordList(listId, profileId)
                if (!resp.isSuccessful && resp.code() != 404) throw retrofit2.HttpException(resp)
            }
            else -> Unit // nieznany typ — porzuć (removeOp w drainOutboxOps)
        }
    }

    private suspend fun pushOutbox() {
        drainOutboxOps()
        flushPendingUndos()
        val moves = offlineStore.pendingMoves()
        val pending = offlineStore.pendingReviews()
        if (moves.isEmpty() && pending.isEmpty()) return
        val body = SyncPushRequest(
            moves = moves.map {
                SyncMoveItem(
                    client_id = it.clientId,
                    card_id = it.cardId,
                    target_list_id = it.targetListId,
                    moved_at = Instant.ofEpochMilli(it.movedAt).toString(),
                )
            },
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
        if (moves.isNotEmpty()) {
            offlineStore.removePendingMoves(moves.map { it.clientId })
        }
        if (pending.isNotEmpty()) {
            offlineStore.removePendingReviews(pending.map { it.clientId })
            offlineStore.applyServerSrs(result.srs)
        }
    }

    /**
     * Opróżnia kolejkę offline-lookupów. SERIALIZOWANE mutexem — nigdy dwa flushe naraz,
     * bo to tworzyło duplikaty kart (różne kandydaty z tego samego stuba) i paliło tokeny.
     * Każdy stub kasowany JEDNORAZOWO tuż po udanym dodaniu; jeśli w międzyczasie ktoś
     * wyczyścił skrzynkę (stub zniknął), pomijamy go — brak zmartwychwstania kart.
     */
    private suspend fun flushPendingLookups() {
        pendingFlushMutex.withLock {
            if (!networkMonitor.isCurrentlyOnline()) return
            // Tylko stuby czekające — te z „wymaga sprawdzenia" pomijamy (zero kolejnych lookupów).
            val pending = offlineStore.queuedPendingLookups()
            if (pending.isEmpty()) return
            val profileId = activeProfileId()
            val inbox = runCatching {
                api.listWordLists(profileId).find { it.is_pending_inbox }
                    ?: api.ensurePendingInbox(profileId)
            }.getOrNull() ?: return
            val inboxId = inbox.id
            offlineStore.cacheLists(profileId, listOf(inbox))
            var anyDone = false
            for (item in pending) {
                // Stub mógł zostać usunięty (np. „Usuń listę”) między snapshotem a teraz — pomiń.
                if (!offlineStore.pendingLookupExists(item.clientId)) continue
                val rawLemma = item.lemma.trim()
                var resp = runCatching {
                    api.lookup(LookupRequest(text = rawLemma, profile_id = profileId))
                }.getOrNull()
                // Powtórka na lowercase gdy pierwszy strzał nie był pewny (np. „FIRANKA”).
                if (resp?.confident != true && rawLemma != rawLemma.lowercase()) {
                    val lower = runCatching {
                        api.lookup(LookupRequest(text = rawLemma.lowercase(), profile_id = profileId))
                    }.getOrNull()
                    if (lower != null && (lower.confident || resp == null)) resp = lower
                }
                // Ponowne sprawdzenie po (wolnym) lookupie — czyszczenie mogło wejść w tym czasie.
                if (!offlineStore.pendingLookupExists(item.clientId)) continue

                // Brak odpowiedzi z API (błąd sieci) → zostaw w kolejce, spróbujemy później.
                if (resp == null) continue

                // Poważne wątpliwości: nie tworzymy karty, nie palimy enrichmentu.
                if (!resp.confident) {
                    val suggestionsJson = runCatching {
                        json.encodeToString(
                            ListSerializer(LookupCandidate.serializer()),
                            resp.candidates,
                        )
                    }.getOrNull()
                    offlineStore.markLookupNeedsReview(item.clientId, suggestionsJson)
                    continue
                }

                val resolved = resp.candidates.firstOrNull()
                val lemma = resolved?.lemma?.takeIf { it.isNotBlank() } ?: rawLemma
                var added = runCatching {
                    api.addWordToList(
                        inboxId,
                        WordListAddWordRequest(
                            lemma = lemma,
                            pos = resolved?.pos,
                            gloss = resolved?.gloss?.takeIf { it.isNotBlank() },
                            lexical_entry_id = resolved?.lexical_entry_id,
                            profile_id = profileId,
                        ),
                    )
                }
                if (added.isFailure && (added.exceptionOrNull() as? retrofit2.HttpException)?.code() != 409) {
                    added = runCatching {
                        api.addWordToList(
                            inboxId,
                            WordListAddWordRequest(lemma = rawLemma, profile_id = profileId),
                        )
                    }
                }
                val ok = added.isSuccess ||
                    (added.exceptionOrNull() as? retrofit2.HttpException)?.code() == 409
                if (ok) {
                    // Kasuj stub NATYCHMIAST — żaden kolejny flush nie doda go ponownie.
                    offlineStore.removePendingLookup(item.clientId)
                    added.getOrNull()?.let { card ->
                        offlineStore.upsertCards(profileId, listOf(card), deckId = inboxId)
                        watchOfflineIfPending(card)
                    }
                    anyDone = true
                }
            }
            if (anyDone) {
                runCatching {
                    val words = api.listWords(inboxId, profileId)
                    offlineStore.cacheCardsFromList(profileId, words, deckId = inboxId)
                }
            }
        }
    }

    /** Propozycje zapisane przy stubie „wymaga sprawdzenia". */
    suspend fun pendingReviewSuggestions(cardId: String): List<LookupCandidate> {
        val clientId = cardId.removePrefix("pending-lookup-")
        val stub = offlineStore.pendingLookupById(clientId) ?: return emptyList()
        val raw = stub.suggestionsJson ?: return emptyList()
        return runCatching {
            json.decodeFromString(ListSerializer(LookupCandidate.serializer()), raw)
        }.getOrDefault(emptyList())
    }

    /** Oryginalne słowo wpisane offline (do prefillu „Szukaj ponownie"). */
    suspend fun pendingReviewWord(cardId: String): String? {
        val clientId = cardId.removePrefix("pending-lookup-")
        return offlineStore.pendingLookupById(clientId)?.lemma
    }

    /** Odrzuca słowo „wymaga sprawdzenia" — kasuje stub całkowicie. */
    suspend fun rejectPendingReview(cardId: String) {
        removePendingLookupStub(cardId)
    }

    /**
     * Zatwierdza wybraną propozycję: dodaje ją do skrzynki Oczekujące (karta → enrichment),
     * kasuje stub „wymaga sprawdzenia". Wymaga trybu online. Zwraca utworzoną kartę.
     */
    suspend fun approvePendingReview(cardId: String, candidate: LookupCandidate): CardResponse? {
        // BEZ pendingFlushMutex — słowo jest „needs_review", więc flush i tak je pomija (brak wyścigu).
        // Trzymanie muteksu blokowało zatwierdzenie na czas trwającego flushu (użytkownik widział ~10 s).
        if (!networkMonitor.isCurrentlyOnline()) error("offline")
        val clientId = cardId.removePrefix("pending-lookup-")
        val profileId = activeProfileId()
        val inbox = runCatching {
            api.listWordLists(profileId).find { it.is_pending_inbox }
                ?: api.ensurePendingInbox(profileId)
        }.getOrNull() ?: error("no_inbox")
        offlineStore.cacheLists(profileId, listOf(inbox))
        val added = runCatching {
            api.addWordToList(
                inbox.id,
                WordListAddWordRequest(
                    lemma = candidate.lemma,
                    pos = candidate.pos,
                    gloss = candidate.gloss.takeIf { it.isNotBlank() },
                    lexical_entry_id = candidate.lexical_entry_id,
                    profile_id = profileId,
                ),
            )
        }
        val ok = added.isSuccess ||
            (added.exceptionOrNull() as? retrofit2.HttpException)?.code() == 409
        if (!ok) (added.exceptionOrNull() ?: error("add_failed")).let { throw it }
        // Kasuj stub „needs_review" i od razu zcache'uj nową kartę (spinner „Tworzę kartę").
        offlineStore.removePendingLookup(clientId)
        val card = added.getOrNull()
        card?.let {
            offlineStore.upsertCards(profileId, listOf(it), deckId = inbox.id)
            watchOfflineIfPending(it)
        }
        return card
    }

    /** Serwerowy UUID skrzynki Oczekujące (nie lokalny local-pending-inbox-*). */
    private suspend fun resolvePendingInboxApiId(profileId: String, listId: String): String {
        if (!listId.startsWith("local-pending-inbox-")) return listId
        return runCatching {
            api.listWordLists(profileId).find { it.is_pending_inbox }?.id
        }.getOrNull()
            ?: offlineStore.localLists(profileId)
                .firstOrNull { it.is_pending_inbox && !it.id.startsWith("local-pending-inbox-") }
                ?.id
            ?: listId
    }

    suspend fun checkAnswer(cardId: String, answer: String, direction: String): CheckAnswerResponse {
        val card = offlineStore.cardById(cardId) ?: error("offline_card")
        val content = offlineStore.parseContent(card.contentJson)
        val (ok, expected, typo) = LocalAnswerCheck.check(answer, content, direction)
        return CheckAnswerResponse(correct = ok, expected = expected, accepted_as_typo = typo)
    }

    suspend fun getSettings(): UserSettingsResponse =
        offlineStore.localUserSettings() ?: defaultSettings()

    /** Local-first: zapisuje ustawienia w Room + operacja outboxu; online drenuje od razu. */
    suspend fun updateSettings(update: UserSettingsUpdate): UserSettingsResponse {
        val current = offlineStore.localUserSettings() ?: defaultSettings()
        val merged = current.mergedWith(update)
        offlineStore.saveSettings(merged)
        update.theme?.let { tokenStore.saveTheme(it) }
        offlineStore.replaceSettingsOp(
            json.encodeToString(UserSettingsUpdate.serializer(), merged.toUpdate()),
        )
        if (networkMonitor.isCurrentlyOnline()) runCatching { drainOutboxOps() } else syncScheduler.requestNow()
        return offlineStore.localUserSettings() ?: merged
    }

    private fun UserSettingsResponse.mergedWith(u: UserSettingsUpdate): UserSettingsResponse = copy(
        practice_input_pref = u.practice_input_pref ?: practice_input_pref,
        practice_direction = u.practice_direction ?: practice_direction,
        typing_tolerance = u.typing_tolerance ?: typing_tolerance,
        typo_modal_enabled = u.typo_modal_enabled ?: typo_modal_enabled,
        new_cards_per_day = u.new_cards_per_day ?: new_cards_per_day,
        theme = u.theme ?: theme,
        show_usages = u.show_usages ?: show_usages,
        show_synonyms_antonyms = u.show_synonyms_antonyms ?: show_synonyms_antonyms,
        show_synonyms = u.show_synonyms ?: show_synonyms,
        show_antonyms = u.show_antonyms ?: show_antonyms,
        show_word_family = u.show_word_family ?: show_word_family,
        show_periphrases = u.show_periphrases ?: show_periphrases,
        show_conjugation = u.show_conjugation ?: show_conjugation,
        conjugation_expanded_default = u.conjugation_expanded_default ?: conjugation_expanded_default,
        show_example_sentences = u.show_example_sentences ?: show_example_sentences,
        related_words_expanded_default = u.related_words_expanded_default ?: related_words_expanded_default,
        study_reminder_enabled = u.study_reminder_enabled ?: study_reminder_enabled,
        cards_ready_push_enabled = u.cards_ready_push_enabled ?: cards_ready_push_enabled,
        reminder_hour = u.reminder_hour ?: reminder_hour,
    )

    private fun UserSettingsResponse.toUpdate(): UserSettingsUpdate = UserSettingsUpdate(
        practice_input_pref = practice_input_pref,
        practice_direction = practice_direction,
        typing_tolerance = typing_tolerance,
        typo_modal_enabled = typo_modal_enabled,
        new_cards_per_day = new_cards_per_day,
        theme = theme,
        show_usages = show_usages,
        show_synonyms_antonyms = show_synonyms_antonyms,
        show_synonyms = show_synonyms,
        show_antonyms = show_antonyms,
        show_word_family = show_word_family,
        show_periphrases = show_periphrases,
        show_conjugation = show_conjugation,
        conjugation_expanded_default = conjugation_expanded_default,
        show_example_sentences = show_example_sentences,
        related_words_expanded_default = related_words_expanded_default,
        study_reminder_enabled = study_reminder_enabled,
        cards_ready_push_enabled = cards_ready_push_enabled,
        reminder_hour = reminder_hour,
    )

    suspend fun listProfiles(): List<LanguageProfileResponse> {
        val cached = offlineStore.cachedProfiles()
        if (cached.isNotEmpty()) return cached
        return offlineStore.cachedActiveProfile()?.let { listOf(it) } ?: emptyList()
    }

    suspend fun refreshProfilesFromNetwork(): List<LanguageProfileResponse> {
        if (!networkMonitor.isCurrentlyOnline()) return listProfiles()
        return apiTry { api.listProfiles() }
            .onSuccess { applyRemoteProfiles(it) }
            .getOrElse { listProfiles() }
    }

    private suspend fun applyRemoteProfiles(profiles: List<LanguageProfileResponse>) {
        val localActive = offlineStore.cachedActiveProfile()
        val merged = profiles.map { remote ->
            if (localActive != null && remote.id == localActive.id) {
                // GET /profiles nie może cofać czasów / CEFR zapisanych lokalnie.
                remote.copy(
                    selected_tenses = localActive.selected_tenses,
                    cefr_level = localActive.cefr_level,
                    tense_label_lang = localActive.tense_label_lang,
                )
            } else {
                remote
            }
        }
        offlineStore.cacheProfiles(merged)
        val chosen = resolveActiveProfile(tokenStore.activeProfileId.value, merged) ?: return
        syncActiveProfileToLocal(chosen)
    }

    suspend fun getActiveProfile(): LanguageProfileResponse? =
        offlineStore.cachedActiveProfile()

    suspend fun hasCachedProfile(): Boolean = offlineStore.cachedActiveProfile() != null

    private suspend fun syncActiveProfileToLocal(
        profile: LanguageProfileResponse,
        overwriteLang: Boolean = false,
    ) {
        tokenStore.saveActiveProfile(profile.id)
        if (overwriteLang || tokenStore.peekAppLang().isBlank()) {
            tokenStore.saveAppLang(profile.app_lang)
        }
        offlineStore.cacheProfile(profile)
    }

    /** Apply UI locale. TokenStore is the source of truth (survives Activity recreate). */
    suspend fun applyAppLocaleFromActiveProfile(): String {
        val stored = tokenStore.peekAppLang().trim().lowercase()
        val fromProfile = offlineStore.cachedActiveProfile()?.app_lang?.trim()?.lowercase().orEmpty()
        val appLang = stored.ifBlank { fromProfile }.ifBlank { "en" }
        com.vocabulario.app.i18n.AppLocale.applyIfChanged(appLang)
        return appLang
    }

    suspend fun createProfile(
        appLang: String,
        learning: String,
        cefr: String,
        tenses: List<String>,
        tenseLabelLang: String = "app_lang",
    ): LanguageProfileResponse {
        val profile = api.createProfile(
            LanguageProfileCreate(
                app_lang = appLang,
                learning_lang = learning,
                cefr_level = cefr,
                selected_tenses = tenses,
                tense_label_lang = tenseLabelLang,
            )
        )
        tokenStore.saveActiveProfile(profile.id)
        tokenStore.saveAppLang(profile.app_lang)
        offlineStore.cacheProfile(profile)
        return profile
    }

    suspend fun activateProfile(profileId: String): LanguageProfileResponse {
        val profile = api.activateProfile(profileId)
        syncActiveProfileToLocal(profile, overwriteLang = true)
        return profile
    }

    suspend fun updateProfile(
        cefr: String? = null,
        tenses: List<String>? = null,
        tenseLabelLang: String? = null,
        appLang: String? = null,
    ): LanguageProfileResponse {
        val current = offlineStore.cachedActiveProfile() ?: error("no_active_profile")
        val optimistic = current.copy(
            cefr_level = cefr ?: current.cefr_level,
            selected_tenses = tenses ?: current.selected_tenses,
            tense_label_lang = tenseLabelLang ?: current.tense_label_lang,
            app_lang = appLang ?: current.app_lang,
            native_lang = appLang ?: current.native_lang,
        )
        syncActiveProfileToLocal(optimistic, overwriteLang = appLang != null)
        val body = LanguageProfileUpdate(
            cefr_level = cefr,
            selected_tenses = tenses,
            tense_label_lang = tenseLabelLang,
            app_lang = appLang,
        )
        val profile = try {
            api.updateProfile(activeProfileId(), body)
        } catch (e: HttpException) {
            if (e.code() != 404) return optimistic
            applyRemoteProfiles(api.listProfiles())
            api.updateProfile(activeProfileId(), body)
        }
        syncActiveProfileToLocal(profile, overwriteLang = true)
        return profile
    }

    suspend fun switchToLangPair(
        appLang: String,
        learningLang: String,
        cefr: String,
    ): LanguageProfileResponse {
        val app = appLang.trim().lowercase()
        val learning = learningLang.trim().lowercase()
        val remote = refreshProfilesFromNetwork()
        val existing = findLangPair(remote, app, learning)
        val profile = when (val action = langPairSwitch(existing, tokenStore.activeProfileId.value)) {
            LangPairSwitch.Keep -> existing!!
            is LangPairSwitch.Activate -> activateProfile(action.profileId)
            LangPairSwitch.Create -> try {
                createProfile(
                    appLang = app,
                    learning = learning,
                    cefr = cefr,
                    tenses = LanguagePacks.defaultSelectedTenses(learning),
                )
            } catch (e: HttpException) {
                if (e.code() != 409) throw e
                val again = refreshProfilesFromNetwork()
                val found = findLangPair(again, app, learning) ?: throw e
                activateProfile(found.id)
            }
        }
        tokenStore.saveAppLang(profile.app_lang)
        requestBackgroundSync()
        return profile
    }

    suspend fun getMe() = api.me()

    suspend fun hasProfile(): Boolean {
        if (offlineStore.cachedActiveProfile() != null) return true
        if (offlineStore.cachedProfiles().isNotEmpty()) return true
        if (!networkMonitor.isCurrentlyOnline()) return false
        return apiTry { api.listProfiles() }
            .onSuccess { applyRemoteProfiles(it) }
            .getOrElse { emptyList() }
            .isNotEmpty()
    }

    suspend fun syncThemeFromSettings() {
        val settings = getSettings()
        tokenStore.saveTheme(settings.theme)
    }

    suspend fun correctionQuota(): CorrectionQuotaResponse = api.correctionQuota()

    suspend fun submitCardCorrection(cardId: String, sections: List<String>, note: String): CardCorrectionCreateResponse {
        val profileId = activeProfileId()
        return api.createCardCorrection(
            cardId,
            profileId,
            CardCorrectionCreate(sections = sections, note = note.ifBlank { null }),
        )
    }

    suspend fun latestCardCorrection(cardId: String): CardCorrectionResponse? {
        return api.latestCardCorrection(cardId, activeProfileId())
    }

    suspend fun validateSelfEdit(
        cardId: String,
        content: kotlinx.serialization.json.JsonObject,
    ): SelfEditValidateResponse {
        return api.validateSelfEdit(
            cardId,
            activeProfileId(),
            CardSelfEditRequest(content = content),
        )
    }

    suspend fun selfEditCard(cardId: String, content: kotlinx.serialization.json.JsonObject): CardResponse {
        val updated = api.selfEditCard(
            cardId,
            activeProfileId(),
            CardSelfEditRequest(content = content),
        )
        offlineStore.upsertCards(activeProfileId(), listOf(updated))
        syncScheduler.requestNow()
        return updated
    }

    suspend fun getCardHistory(cardId: String): CardHistoryResponse {
        return api.getCardHistory(cardId, activeProfileId())
    }

    suspend fun restoreCard(cardId: String, historyEventId: String): CardResponse {
        val updated = api.restoreCard(
            cardId,
            activeProfileId(),
            CardRestoreRequest(history_event_id = historyEventId),
        )
        offlineStore.upsertCards(activeProfileId(), listOf(updated))
        syncScheduler.requestNow()
        return updated
    }

    suspend fun registerDeviceToken(token: String) {
        if (!hasSyncableSession()) return
        runCatching { api.registerDevice(DeviceRegisterRequest(token = token)) }
    }

    suspend fun unregisterDeviceToken(token: String) {
        runCatching { api.unregisterDevice(token) }
    }
}

internal fun isLocalOnlyListId(id: String): Boolean =
    id.startsWith("local-") || id.startsWith("local:")

/** Listy, które trzeba dociągnąć do Room po commicie importu (cel + system + inbox). */
internal fun importRefreshListIds(
    requestedListId: String?,
    lists: List<WordListResponse>,
): List<String> {
    val targets = LinkedHashSet<String>()
    requestedListId?.takeUnless { isLocalOnlyListId(it) }?.let { id ->
        if (lists.any { it.id == id }) targets.add(id)
    }
    for (list in lists) {
        if ((list.is_system || list.is_pending_inbox) && !isLocalOnlyListId(list.id)) {
            targets.add(list.id)
        }
    }
    return targets.toList()
}

package com.vocabulario.app.data

import com.vocabulario.app.data.api.CardCorrectionCreate
import com.vocabulario.app.data.api.CardCorrectionCreateResponse
import com.vocabulario.app.data.api.CardCorrectionResponse
import com.vocabulario.app.data.api.CorrectionEscalateResponse
import com.vocabulario.app.data.api.CorrectionQuotaResponse
import com.vocabulario.app.data.api.CardCreateRequest
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.CardHistoryResponse
import com.vocabulario.app.data.api.CheckAnswerResponse
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.api.DistractorsRequest
import com.vocabulario.app.data.api.DistractorsResponse
import com.vocabulario.app.data.api.DeviceRegisterRequest
import com.vocabulario.app.data.api.ImportIngestRequest
import com.vocabulario.app.data.api.ImportJobCommitRequest
import com.vocabulario.app.data.api.ImportJobCreateRequest
import com.vocabulario.app.data.api.ImportJobProgressResponse
import com.vocabulario.app.data.api.ImportValidateRequest
import com.vocabulario.app.data.api.ImportValidateResponse
import com.vocabulario.app.data.api.LanguageProfileCreate
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.LanguageProfileUpdate
import com.vocabulario.app.data.api.appLang
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
import com.vocabulario.app.data.api.apiErrorCode
import com.vocabulario.app.data.local.LocalAnswerCheck
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.local.db.PendingReviewEntity
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionState
import com.vocabulario.app.data.session.OwnerContext
import com.vocabulario.app.data.session.SupersededException
import com.vocabulario.app.data.session.ensureOwner
import com.vocabulario.app.data.session.runAsOwner
import com.vocabulario.app.data.api.SyncPullRequest
import com.vocabulario.app.data.sync.AckDecision
import com.vocabulario.app.data.sync.BlockedItem
import com.vocabulario.app.data.sync.BlockedKind
import com.vocabulario.app.data.sync.FailureKind
import com.vocabulario.app.data.sync.OpAck
import com.vocabulario.app.data.sync.OutboxStep
import com.vocabulario.app.data.sync.PhaseOutcome
import com.vocabulario.app.data.sync.QueueSnapshot
import com.vocabulario.app.data.sync.SyncFailure
import com.vocabulario.app.data.sync.SyncPhase
import com.vocabulario.app.data.sync.SyncReport
import com.vocabulario.app.data.sync.SyncResult
import com.vocabulario.app.data.sync.SyncScope
import com.vocabulario.app.data.sync.classifyFailure
import com.vocabulario.app.data.sync.evaluateSyncResult
import com.vocabulario.app.data.sync.interpretAck
import com.vocabulario.app.data.sync.toSyncFailure
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
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
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
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
    private val dailyNewCounter: com.vocabulario.app.data.local.DailyNewCounter,
    private val sessionCoordinator: SessionCoordinator,
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
        const val API_FULL_PULL_TIMEOUT_MS = 90_000L
        const val FLUSH_LOOKUPS_TIMEOUT_MS = 30_000L

        const val OP_SETTINGS_UPDATE = "settings_update"
        const val OP_CARD_DELETE = "card_delete"
        const val OP_LIST_CREATE = "list_create"
        const val OP_LIST_RENAME = "list_rename"
        const val OP_LIST_DELETE = "list_delete"
        val OUTBOX_PAYLOAD_TYPES = setOf(OP_CARD_DELETE, OP_LIST_CREATE, OP_LIST_RENAME, OP_LIST_DELETE)
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
     * Dociąga pojedyncze karty (pending/learnable) i upsertuje treść w Room.
     * Zamiast GET całej listy przy pollu enrichment.
     */
    suspend fun refreshCardsFromServer(cardIds: Collection<String>): List<CardResponse> {
        if (!networkMonitor.isCurrentlyOnline() || cardIds.isEmpty()) return emptyList()
        val profileId = activeProfileId()
        val fetched = mutableListOf<CardResponse>()
        coroutineScope {
            cardIds
                .map { it.trim() }
                .filter { it.isNotEmpty() && !it.startsWith("pending-") && !it.startsWith("local:") }
                .distinct()
                .map { id ->
                    async {
                        apiTry(timeoutMs = API_FAST_TIMEOUT_MS) { api.getCard(id, profileId) }.getOrNull()
                    }
                }
                .forEach { deferred ->
                    deferred.await()?.let { fetched.add(it) }
                }
        }
        if (fetched.isNotEmpty()) {
            offlineStore.upsertCards(profileId, fetched)
        }
        return fetched
    }

    /**
     * Dociąga słowa listy z API i upsertuje enrichment/treść w Room.
     * Pełna lista — przy otwarciu listy, nie przy pollu pojedynczej karty.
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
        val lists = offlineStore.completeLocalWordLists(profileId)
        return offlineStore.withComputedWordCounts(profileId, lists)
    }

    suspend fun activeProfileId(): String {
        tokenStore.activeProfileId.first()?.takeIf { it.isNotBlank() }?.let { return it }
        offlineStore.cachedActiveProfile()?.id?.takeIf { it.isNotBlank() }?.let { return it }
        return getActiveProfile()?.id ?: error("no_active_profile")
    }

    suspend fun hasSyncableSession(): Boolean {
        if (sessionCoordinator.awaitLoaded() !is SessionState.Active) return false
        val profile = tokenStore.activeProfileId.first()
        return !profile.isNullOrBlank()
    }

    /** Sesja do pracy w tle i właściciel danych w fazie ACTIVE (przed powiadomieniem konta). */
    suspend fun hasActiveOwner(): Boolean =
        hasSyncableSession() && offlineStore.activeOwnerContext() != null

    /**
     * Praca w tle jako właściciel przechwycony na starcie; zapisy w Room po HTTP sprawdzają go
     * w tej samej transakcji. Null, gdy nie ma aktywnego właściciela albo wynik został zastąpiony.
     */
    suspend fun <T> asCurrentOwner(block: suspend () -> T): T? =
        runAsOwner({ offlineStore.activeOwnerContext() }, block)

    /** Kontrola po HTTP; w zakresie [asCurrentOwner] przerywa pracę innego właściciela lub generacji. */
    suspend fun ensureOwnerCurrent() = ensureOwner { offlineStore.activeOwnerContext() }

    suspend fun lookup(text: String): LookupResponse {
        val profileId = activeProfileId()
        return api.lookup(LookupRequest(text = text, profile_id = profileId))
    }

    suspend fun lookupCached(text: String): LookupResponse {
        val profileId = activeProfileId()
        return api.lookupCached(
            LookupRequest(text = text, profile_id = profileId, local_membership = true),
        )
    }

    suspend fun lookupExpand(
        text: String,
        more: Boolean = false,
        operationId: String? = null,
    ): LookupResponse {
        val profileId = activeProfileId()
        return api.lookupExpand(
            LookupRequest(
                text = text,
                profile_id = profileId,
                local_membership = true,
                more = more,
                operation_id = operationId,
            ),
        )
    }

    fun observeMembershipRows(profileId: String) = offlineStore.observeMembershipRows(profileId)

    fun observeLastPulledAt(profileId: String) = offlineStore.observeLastPulledAt(profileId)

    suspend fun lookupCategoryCached(text: String): LookupResponse {
        val profileId = activeProfileId()
        return api.lookupCategoryCached(
            LookupRequest(text = text, profile_id = profileId, local_membership = true),
        )
    }

    suspend fun lookupCategoryExpand(text: String, round: Int): LookupResponse {
        val profileId = activeProfileId()
        try {
            return api.lookupCategoryExpand(
                LookupRequest(text = text, profile_id = profileId, round = round),
            )
        } catch (error: retrofit2.HttpException) {
            if (error.code() == 409) throw com.vocabulario.app.data.lookup.AssocRoundNotReady()
            throw error
        }
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

    suspend fun commitImportJob(
        jobId: String,
        itemIds: List<String>? = null,
    ): ImportJobProgressResponse =
        api.commitImportJob(jobId, ImportJobCommitRequest(item_ids = itemIds))

    suspend fun cancelImportJob(jobId: String): ImportJobProgressResponse =
        api.cancelImportJob(jobId)

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
        sourceCardId: String? = null,
    ): CardResponse {
        val profileId = activeProfileId()
        val created = api.createCard(
            CardCreateRequest(
                lemma = lemma,
                pos = pos,
                gloss = gloss,
                profile_id = profileId,
                lexical_entry_id = lexicalEntryId,
                source_card_id = sourceCardId,
            )
        )
        offlineStore.upsertCards(profileId, listOf(created), deckId = null, overwriteDeckId = true)
        watchOfflineIfPending(created)
        // POST już zapisał PG. Pełny pull tu nie wypełnia karty — może ją wyciąć
        // (fullReplace gdy lastPulled == null). Enrichment = GET /cards/{id} → Room.
        return created
    }

    suspend fun learningLemmaSet(): Set<String> {
        val profileId = activeProfileId()
        return offlineStore.learningCards(profileId)
            .flatMap { lemmaKeys(it.lemmaL2) }
            .toSet()
    }

    suspend fun relatedMembershipIndex(): RelatedMembershipIndex {
        val profileId = activeProfileId()
        return buildRelatedMembershipIndex(
            offlineStore.allCards(profileId),
            offlineStore.localLists(profileId),
        )
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
        sourceCardId: String? = null,
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
                source_card_id = sourceCardId,
            ),
        )
        val lists = offlineStore.localLists(profileId)
        val isSystem = isSystemListForRoom(listId, lists)
        offlineStore.upsertCards(
            profileId,
            listOf(created),
            deckId = roomDeckIdForList(listId, isSystem),
            overwriteDeckId = true,
        )
        watchOfflineIfPending(created)
        // POST już zapisał PG. Nie wołaj pełnego pulla: karta ma być w Room od razu,
        // a syncNow(fullReplace gdy lastPulled == null) czyści profil i może ją zgubić.
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
        if (offlineStore.countStartedWithoutDue(profileId) >= 5) {
            syncNow(fullReplace = true)
        }
        val settings = getSettings()
        val newDone = dailyNewCounter.get(profileId)
        return offlineStore.buildDashboardStats(profileId, settings.new_cards_per_day, days, newDone)
    }

    fun requestBackgroundSync() {
        syncScheduler.requestNow()
    }

    suspend fun getQueue(): SrsQueueResponse {
        val profileId = activeProfileId()
        val settings = getSettings()
        val newLimit = settings.new_cards_per_day
        val directionPref = settings.practice_direction
        val newDone = dailyNewCounter.get(profileId)
        val local = offlineStore.localQueue(profileId, newLimit, newDone)
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

    data class DistractorsPick(
        val response: DistractorsResponse,
        val usedListKeys: List<String>,
        val unusedPoolWasEmpty: Boolean,
    )

    suspend fun getDistractors(
        cardId: String,
        direction: String,
        usedKeys: Set<String> = emptySet(),
    ): DistractorsPick {
        val profileId = activeProfileId()
        val local = localDistractors(profileId, cardId, direction, usedKeys)
        if (local.response.options.size >= 8 || !networkMonitor.isCurrentlyOnline()) {
            return local
        }
        val remote = apiTry(timeoutMs = 25_000L) {
            api.srsDistractors(
                DistractorsRequest(
                    card_id = cardId,
                    profile_id = profileId,
                    direction = direction,
                ),
            )
        }.getOrNull()
        if (remote != null && remote.options.size >= 8) {
            return DistractorsPick(
                response = remote,
                usedListKeys = emptyList(),
                unusedPoolWasEmpty = false,
            )
        }
        return local
    }

    private suspend fun localDistractors(
        profileId: String,
        cardId: String,
        direction: String,
        usedKeys: Set<String>,
    ): DistractorsPick {
        val card = offlineStore.cardById(cardId) ?: error("offline_card")
        val content = offlineStore.parseContent(card.contentJson)
        val correctText = if (direction == "l2_to_l1") {
            card.glossPrimary ?: LocalAnswerCheck.collectAnswers(content, direction).firstOrNull().orEmpty()
        } else {
            card.lemmaL2
        }
        val listCards = offlineStore.learningCards(profileId)
            .filter { it.id != cardId }
            .map { DistractorCard(it.id, it.lemmaL2, it.glossPrimary, it.pos) }
        val similar = buildList {
            content["similar_words"].asJsonArray()?.forEach { el ->
                val obj = el as? kotlinx.serialization.json.JsonObject
                val lemma = when (el) {
                    is kotlinx.serialization.json.JsonObject -> el["lemma"].asJsonString()
                    is kotlinx.serialization.json.JsonPrimitive -> el.content
                    else -> null
                }?.trim().orEmpty()
                if (lemma.isEmpty()) return@forEach
                add(
                    SimilarWordSeed(
                        lemma = lemma,
                        glossL1 = obj?.get("gloss_l1")?.asJsonString(),
                        pos = obj?.get("pos")?.asJsonString(),
                    ),
                )
            }
        }
        val picked = pickChoiceDistractors(
            direction = direction,
            correctText = correctText,
            correctLemmaL2 = card.lemmaL2,
            correctGloss = card.glossPrimary,
            correctPos = card.pos,
            correctCardId = card.id,
            listCards = listCards,
            similar = similar,
            usedKeys = usedKeys,
        )
        return DistractorsPick(
            response = DistractorsResponse(options = picked.options, direction = direction),
            usedListKeys = picked.usedListKeys,
            unusedPoolWasEmpty = picked.unusedPoolWasEmpty,
        )
    }

    suspend fun cardSrsSnapshot(cardId: String): SyncSrsState? =
        offlineStore.cardSrsSnapshot(cardId)

    suspend fun undoReview(clientId: String, previous: SyncSrsState) {
        val nowMs = System.currentTimeMillis()
        offlineStore.recordUndoLocally(clientId, previous)
        if (previous.status == "new") {
            runCatching { dailyNewCounter.decrement(activeProfileId(), nowMs) }
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
        val wasNew = offlineStore.cardSrsSnapshot(cardId)?.status == "new"
        offlineStore.recordReviewLocally(
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
        if (wasNew) {
            runCatching { dailyNewCounter.increment(activeProfileId(), nowMs) }
        }
        // Nie czekaj na sieć — ocena musi od razu odsłonić kolejną kartę.
        // Outbox + WorkManager dociągają review w tle (timeout / mutex syncu nie blokują UI).
        syncScheduler.requestNow()
        return clientId
    }

    /**
     * Push moves + reviews, flush offline lookups, then pull.
     * Flush jest osobno i **pierwszy** — zatruty outbox nie może blokować opróżniania Oczekujących.
     */
    private val syncMutex = Mutex()

    private class SyncTally {
        var sent = 0
        var confirmed = 0
    }

    /** Wyjątek → Result bez połykania anulowania rodzica; timeout własnego `withTimeout` to zwykła awaria. */
    private suspend fun <T> attempt(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (e: SupersededException) {
        throw e
    } catch (e: TimeoutCancellationException) {
        currentCoroutineContext().ensureActive()
        Result.failure(e)
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        Result.failure(e)
    }

    /** Awarie, po których dalsze żądania nie mają sensu (sesja, weryfikacja, zgody, brak sieci, limit). */
    private fun SyncFailure.stopsSync(): Boolean = kind == FailureKind.AUTH ||
        kind == FailureKind.VERIFICATION ||
        kind == FailureKind.LEGAL ||
        kind == FailureKind.OFFLINE ||
        kind == FailureKind.RATE_LIMITED

    /**
     * Push zmian, flush lookupów, pull. Wynik wynika z raportu faz i stanu kolejek, nie z braku wyjątku.
     * Flush lookupów jest pierwszy — zatruty outbox nie może blokować opróżniania Oczekujących.
     */
    suspend fun syncNow(
        fullReplace: Boolean = false,
        awaitLock: Boolean = false,
        scope: SyncScope = SyncScope.ACTIVE_PROFILE,
    ): SyncResult {
        if (awaitLock) syncMutex.lock() else if (!syncMutex.tryLock()) return SyncResult.Busy
        try {
            val startedAt = System.currentTimeMillis()
            val owner = offlineStore.activeOwnerContext() ?: return SyncResult.Superseded
            if (!networkMonitor.isCurrentlyOnline()) {
                val phases = SyncPhase.values().associateWith<SyncPhase, PhaseOutcome> { PhaseOutcome.NotRun("offline") }
                return SyncResult.Offline(
                    SyncReport(owner, scope, startedAt, System.currentTimeMillis(), phases, emptyMap(), 0, 0, offlineStore.queueSnapshot()),
                )
            }
            return asCurrentOwner { syncAsOwner(owner, fullReplace, scope, startedAt) } ?: SyncResult.Superseded
        } finally {
            syncMutex.unlock()
        }
    }

    /** Kroki syncu jednego właściciela; zmiana właściciela lub generacji kończy go przed kolejnym HTTP. */
    private suspend fun syncAsOwner(
        owner: OwnerContext,
        fullReplace: Boolean,
        scope: SyncScope,
        startedAt: Long,
    ): SyncResult {
        val phases = linkedMapOf<SyncPhase, PhaseOutcome>()
        val pulls = linkedMapOf<String, PhaseOutcome>()
        val tally = SyncTally()
        var stopReason: String? = null

        suspend fun runPhase(phase: SyncPhase, block: suspend () -> SyncFailure?) {
            val stopped = stopReason
            if (stopped != null) {
                phases[phase] = PhaseOutcome.NotRun(stopped)
                return
            }
            val failure = attempt { block() }.getOrElse { error ->
                // Wolny lookup (LLM) to awaria serwera, nie dowód braku sieci.
                if (phase == SyncPhase.LOOKUPS && error is TimeoutCancellationException) {
                    SyncFailure(FailureKind.SERVER, "lookups_timeout", retryable = true)
                } else {
                    error.toSyncFailure()
                }
            }
            ensureOwnerCurrent()
            if (failure == null) {
                phases[phase] = PhaseOutcome.Ok
            } else {
                phases[phase] = PhaseOutcome.Failed(failure)
                if (failure.stopsSync()) stopReason = failure.code
            }
        }

        runPhase(SyncPhase.LOOKUPS) { withTimeout(FLUSH_LOOKUPS_TIMEOUT_MS) { flushPendingLookups(tally) } }
        runPhase(SyncPhase.OUTBOX) { withTimeout(API_SYNC_TIMEOUT_MS) { drainOutboxOps(tally) } }
        runPhase(SyncPhase.PUSH) {
            withTimeout(API_SYNC_TIMEOUT_MS) { flushPendingUndos(tally) ?: pushOutbox(tally) }
        }

        val stopped = stopReason
        if (stopped != null) {
            phases[SyncPhase.PROFILES] = PhaseOutcome.NotRun(stopped)
            phases[SyncPhase.PULL] = PhaseOutcome.NotRun(stopped)
        } else {
            pullPhase(fullReplace, scope, phases, pulls)
        }

        ensureOwnerCurrent()
        evaluateReadyBatches()
        // Pierwszy pull po logowaniu przynosi ustawienia konta; wtedy dopiero włączamy alarm.
        runCatching { restoreStudyReminders(onlyIfChanged = true) }
        val report = SyncReport(
            owner = owner,
            scope = scope,
            startedAt = startedAt,
            finishedAt = System.currentTimeMillis(),
            phases = phases,
            pullByProfile = pulls,
            sent = tally.sent,
            confirmed = tally.confirmed,
            queue = offlineStore.queueSnapshot(),
        )
        return evaluateSyncResult(report)
    }

    private suspend fun pullPhase(
        fullReplace: Boolean,
        scope: SyncScope,
        phases: MutableMap<SyncPhase, PhaseOutcome>,
        pulls: MutableMap<String, PhaseOutcome>,
    ) {
        val activeId = attempt { activeProfileId() }.getOrElse { error ->
            val failure = error.toSyncFailure()
            phases[SyncPhase.PROFILES] = PhaseOutcome.NotRun(failure.code)
            phases[SyncPhase.PULL] = PhaseOutcome.Failed(failure)
            return
        }
        val ids = linkedSetOf(activeId)
        if (scope == SyncScope.ALL_PENDING_PROFILES) ids += offlineStore.profilesWithPendingWork()

        var needProfiles = false
        var stopReason: String? = null
        for (profileId in ids) {
            val stopped = stopReason
            if (stopped != null) {
                pulls[profileId] = PhaseOutcome.NotRun(stopped)
                continue
            }
            val (outcome, full) = pullProfile(profileId, forceFull = fullReplace && profileId == activeId)
            pulls[profileId] = outcome
            if (profileId == activeId && (full || offlineStore.cachedProfiles().isEmpty())) needProfiles = true
            if (outcome is PhaseOutcome.Failed && outcome.failure.stopsSync()) stopReason = outcome.failure.code
            ensureOwnerCurrent()
        }
        phases[SyncPhase.PULL] = pulls.values.firstOrNull { it !is PhaseOutcome.Ok } ?: PhaseOutcome.Ok
        phases[SyncPhase.PROFILES] = when {
            !needProfiles -> PhaseOutcome.NotNeeded
            pulls[activeId] !is PhaseOutcome.Ok -> PhaseOutcome.NotRun("pull_failed")
            else -> {
                val failure = attempt {
                    withTimeout(API_SYNC_TIMEOUT_MS) { applyRemoteProfiles(api.listProfiles()) }
                }.exceptionOrNull()?.toSyncFailure()
                ensureOwnerCurrent()
                if (failure == null) PhaseOutcome.Ok else PhaseOutcome.Failed(failure)
            }
        }
    }

    /** Pull jednego profilu z kursorem; zwraca wynik i informację, czy był pełny. */
    private suspend fun pullProfile(profileId: String, forceFull: Boolean): Pair<PhaseOutcome, Boolean> {
        var cursor = if (forceFull) null else offlineStore.pullCursor(profileId)
        var result = requestPull(profileId, cursor)
        var failure = result.exceptionOrNull()?.toSyncFailure()
        if (failure != null && cursor != null) {
            if (failure.kind == FailureKind.CURSOR_EXPIRED) {
                offlineStore.resetPullCursor(profileId)
                cursor = null
                result = requestPull(profileId, null)
                failure = result.exceptionOrNull()?.toSyncFailure()
            } else if (failure.code == "invalid_sync_cursor") {
                offlineStore.resetPullCursor(profileId)
            }
        }
        val full = cursor == null
        if (failure != null) {
            offlineStore.recordSyncAttempt(profileId, success = false, error = failure.code)
            return PhaseOutcome.Failed(failure) to full
        }
        val pull = result.getOrThrow()
        if (pull.cursor.isNullOrBlank()) {
            val missing = SyncFailure(FailureKind.PROTOCOL, "cursor_missing", retryable = false)
            offlineStore.recordSyncAttempt(profileId, success = false, error = missing.code)
            return PhaseOutcome.Failed(missing) to full
        }
        val applied = attempt {
            offlineStore.guardedWrite {
                offlineStore.applyPull(profileId, pull, fullReplace = full)
                offlineStore.localUserSettings()?.theme?.let { tokenStore.saveTheme(it) }
            }
        }
        val applyFailure = applied.exceptionOrNull()?.toSyncFailure()
        offlineStore.recordSyncAttempt(profileId, success = applyFailure == null, error = applyFailure?.code)
        return (if (applyFailure == null) PhaseOutcome.Ok else PhaseOutcome.Failed(applyFailure)) to full
    }

    private suspend fun requestPull(profileId: String, cursor: String?): Result<com.vocabulario.app.data.api.SyncPullResponse> =
        attempt {
            withTimeout(if (cursor == null) API_FULL_PULL_TIMEOUT_MS else API_SYNC_TIMEOUT_MS) {
                api.syncPull(SyncPullRequest(profile_id = profileId, cursor = cursor))
            }
        }

    suspend fun blockedItems(): List<BlockedItem> = offlineStore.blockedItems()

    suspend fun discardBlocked(kind: BlockedKind, id: String) = offlineStore.discardBlocked(kind, id)

    suspend fun queueSnapshot(): QueueSnapshot = offlineStore.queueSnapshot()

    suspend fun evaluateReadyBatches() {
        asCurrentOwner {
            val settings = runCatching { getSettings() }.getOrNull() ?: return@asCurrentOwner
            val on = settings.study_reminder_enabled || settings.cards_ready_push_enabled
            val profileId = runCatching { activeProfileId() }.getOrNull() ?: return@asCurrentOwner
            val statusById = offlineStore.allCards(profileId).associate { it.id to it.enrichmentStatus }
            // Powiadomienie i zdjęcie obserwacji tylko dla właściciela, który je zlecił.
            offlineStore.guardedWrite { readyBatchTracker.evaluate(statusById, on) }
            if (readyBatchTracker.hasWatches()) notificationScheduler.scheduleEnrichmentSoon()
        }
    }

    fun watchImportCards(ids: Collection<String>) {
        readyBatchTracker.watchImport(ids)
        if (ids.any { it.isNotBlank() }) notificationScheduler.scheduleEnrichmentSoon()
    }

    private fun watchOfflineIfPending(card: CardResponse) {
        if (card.enrichment_status == "pending" || card.enrichment_status == "preparing" || card.enrichment_status == "awaiting_network") {
            readyBatchTracker.watchOffline(listOf(card.id))
            notificationScheduler.scheduleEnrichmentSoon()
        }
    }

    /** Opróżnia kolejkę offline lookupów (Oczekujące) — można wołać niezależnie od sync/outboxu. */
    suspend fun flushPendingLookupsIfNeeded() {
        if (!networkMonitor.isCurrentlyOnline()) return
        flushPendingLookups(null)
    }

    suspend fun hasPendingLookups(): Boolean = offlineStore.pendingLookups().isNotEmpty()

    /** Czy są słowa czekające na flush (bez tych już oznaczonych „wymaga sprawdzenia"). */
    suspend fun hasQueuedLookups(): Boolean = offlineStore.queuedPendingLookups().isNotEmpty()

    suspend fun syncPendingReviews(): SyncResult = syncNow()

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

    /** Otwarta karta z Room — treść sekcji podmienia się przy zapisie polla bez osobnego refresh. */
    fun observeCard(cardId: String): Flow<CardResponse?> =
        offlineStore.observeCardById(cardId).distinctUntilChanged()

    private suspend fun flushPendingUndos(tally: SyncTally?): SyncFailure? {
        for (item in offlineStore.sendableUndos()) {
            val srs = runCatching {
                json.decodeFromString(SyncSrsState.serializer(), item.srsJson)
            }.getOrNull()
            if (srs == null) {
                offlineStore.blockPendingUndo(item.clientId, "invalid_payload")
                continue
            }
            tally?.let { it.sent++ }
            val failure = attempt {
                api.srsUndo(SrsUndoRequest(client_id = item.clientId, previous_srs = srs))
            }.exceptionOrNull()?.toSyncFailure()
            if (failure == null) {
                offlineStore.removePendingUndo(item.clientId)
                tally?.let { it.confirmed++ }
            } else if (failure.kind == FailureKind.CLIENT) {
                // 409 undo_conflict / operation_id_conflict, 404 karty: ponawianie nic nie zmieni.
                offlineStore.blockPendingUndo(item.clientId, failure.code)
            } else {
                return failure
            }
        }
        return null
    }

    /**
     * Drenaż ujednoliconego outboxu (mutacje Z3) przez idempotentne endpointy REST.
     * Zablokowana operacja nie zatrzymuje reszty; błąd przejściowy kończy fazę, żeby nie wyprzedzić
     * zależności (np. rename listy przed jej create). Zwraca pierwszą awarię albo null.
     */
    private suspend fun drainOutboxOps(tally: SyncTally? = null): SyncFailure? {
        if (!networkMonitor.isCurrentlyOnline()) return classifyFailure(null, null, transport = true)
        return outboxMutex.withLock {
            offlineStore.unparkAuthFailures()
            var firstFailure: SyncFailure? = null
            val blockedLocalLists = mutableSetOf<String>()
            for (op in offlineStore.pendingOps()) {
                val dependsOnBlocked = blockedLocalLists.firstOrNull { op.payloadJson.contains(it) }
                if (dependsOnBlocked != null) {
                    offlineStore.markOpBlocked(op, "target_unavailable")
                    continue
                }
                tally?.let { it.sent++ }
                val step = attempt { applyOutboxOp(op) }
                val failure = step.exceptionOrNull()?.toSyncFailure()
                if (failure != null) {
                    if (firstFailure == null) firstFailure = failure
                    if (failure.kind == FailureKind.CLIENT) {
                        offlineStore.markOpFailed(op, failure.code)
                        continue
                    }
                    // 401/5xx/sieć/weryfikacja: operacja zostaje nietknięta, bez naliczania prób.
                    break
                }
                when (val outcome = step.getOrThrow()) {
                    OutboxStep.Applied, OutboxStep.AlreadyApplied -> {
                        offlineStore.removeOp(op)
                        tally?.let { it.confirmed++ }
                    }
                    is OutboxStep.Deferred -> Unit
                    is OutboxStep.Blocked -> {
                        offlineStore.markOpBlocked(op, outcome.code)
                        if (op.type == OP_LIST_CREATE) {
                            runCatching { json.parseToJsonElement(op.payloadJson).jsonObject["localId"]?.jsonPrimitive?.content }
                                .getOrNull()?.let { blockedLocalLists += it }
                        }
                    }
                }
            }
            firstFailure
        }
    }

    private suspend fun applyOutboxOp(op: com.vocabulario.app.data.local.db.OutboxOpEntity): OutboxStep {
        if (op.type == OP_SETTINGS_UPDATE) {
            val update = runCatching { json.decodeFromString(UserSettingsUpdate.serializer(), op.payloadJson) }
                .getOrNull() ?: return OutboxStep.Blocked("invalid_payload")
            api.updateSettings(update)
            // Lokalny Room jest źródłem prawdy — echo z PUT może być starsze niż kolejny tap.
            return OutboxStep.Applied
        }
        if (op.type !in OUTBOX_PAYLOAD_TYPES) return OutboxStep.Blocked("unsupported_operation")
        val p = runCatching { json.parseToJsonElement(op.payloadJson).jsonObject }.getOrNull()
            ?: return OutboxStep.Blocked("invalid_payload")
        val profileId = p["profileId"]?.jsonPrimitive?.content ?: activeProfileId()
        when (op.type) {
            OP_CARD_DELETE -> {
                val cardId = p["cardId"]?.jsonPrimitive?.content ?: return OutboxStep.Blocked("invalid_payload")
                val resp = api.deleteCard(cardId, profileId)
                if (resp.isSuccessful) return OutboxStep.Applied
                if (resp.code() == 404) return OutboxStep.AlreadyApplied
                throw HttpException(resp)
            }
            OP_LIST_RENAME -> {
                val listId = p["listId"]?.jsonPrimitive?.content ?: return OutboxStep.Blocked("invalid_payload")
                val name = p["name"]?.jsonPrimitive?.content ?: return OutboxStep.Blocked("invalid_payload")
                if (listId.startsWith("local:")) return OutboxStep.Deferred(OP_LIST_CREATE)
                try {
                    api.renameWordList(listId, profileId, WordListUpdate(name = name))
                } catch (e: HttpException) {
                    // Lista zniknęła z serwera: zmiana nazwy nie została zastosowana, więc nie jest ACK.
                    if (e.code() == 404) return OutboxStep.Blocked("target_unavailable")
                    throw e
                }
                return OutboxStep.Applied
            }
            OP_LIST_CREATE -> {
                val localId = p["localId"]?.jsonPrimitive?.content ?: return OutboxStep.Blocked("invalid_payload")
                val name = p["name"]?.jsonPrimitive?.content ?: return OutboxStep.Blocked("invalid_payload")
                if (!localId.startsWith("local:")) return OutboxStep.AlreadyApplied
                val created = try {
                    api.createWordList(WordListCreate(name = name, profile_id = profileId, client_op_id = op.clientOpId))
                } catch (e: HttpException) {
                    val code = e.apiErrorCode()
                    if (e.code() == 410 && code == "list_already_deleted") {
                        offlineStore.blockDependentsOfLocalList(localId)
                        return OutboxStep.AlreadyApplied
                    }
                    if (e.code() == 409 && code == "operation_id_conflict") return OutboxStep.Blocked(code)
                    if (e.code() != 409) throw e
                    // Inna lista o tej nazwie już istnieje (nie ta sama operacja): użyj jej.
                    api.listWordLists(profileId).firstOrNull { it.name.equals(name, ignoreCase = true) }
                        ?: return OutboxStep.Blocked("list_name_conflict")
                }
                offlineStore.remapLocalListId(localId, created.id)
                return OutboxStep.Applied
            }
            OP_LIST_DELETE -> {
                val listId = p["listId"]?.jsonPrimitive?.content ?: return OutboxStep.Blocked("invalid_payload")
                if (listId.startsWith("local:")) return OutboxStep.AlreadyApplied // nigdy nie było na serwerze
                val resp = api.deleteWordList(listId, profileId)
                if (resp.isSuccessful) return OutboxStep.Applied
                if (resp.code() == 404) return OutboxStep.AlreadyApplied
                throw HttpException(resp)
            }
            else -> return OutboxStep.Blocked("unsupported_operation")
        }
    }

    private suspend fun pushOutbox(tally: SyncTally?): SyncFailure? {
        val moves = offlineStore.sendableMoves()
        val pending = offlineStore.sendableReviews()
        if (moves.isEmpty() && pending.isEmpty()) return null
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
        tally?.let { it.sent += moves.size + pending.size }
        val result = attempt { api.syncPush(body) }.getOrElse { return it.toSyncFailure() }
        val reviewAck = interpretAck(
            pending.map { it.clientId },
            result.review_results?.map { OpAck(it.client_id, it.outcome, it.reason) },
        )
        val moveAck = interpretAck(
            moves.map { it.clientId },
            result.move_results?.map { OpAck(it.client_id, it.outcome, it.reason) },
        )
        val reviews = reviewAck as? AckDecision.Valid
        val movesDecision = moveAck as? AckDecision.Valid
        // Każdy typ operacji jest oceniany osobno; błąd protokołu jednego nie cofa drugiego.
        offlineStore.applyPushAck(
            confirmedReviews = reviews?.confirmed.orEmpty(),
            blockedReviews = reviews?.blocked.orEmpty(),
            confirmedMoves = movesDecision?.confirmed.orEmpty(),
            blockedMoves = movesDecision?.blocked.orEmpty(),
            srs = if (reviews != null) result.srs else emptyList(),
        )
        tally?.let { it.confirmed += reviews?.confirmed.orEmpty().size + movesDecision?.confirmed.orEmpty().size }
        val protocol = (reviewAck as? AckDecision.ProtocolError) ?: (moveAck as? AckDecision.ProtocolError)
        return protocol?.let { SyncFailure(FailureKind.PROTOCOL, it.code, retryable = false) }
    }

    /**
     * Opróżnia kolejkę offline-lookupów. SERIALIZOWANE mutexem — nigdy dwa flushe naraz,
     * bo to tworzyło duplikaty kart (różne kandydaty z tego samego stuba) i paliło tokeny.
     * Każdy stub kasowany JEDNORAZOWO tuż po udanym dodaniu; jeśli w międzyczasie ktoś
     * wyczyścił skrzynkę (stub zniknął), pomijamy go — brak zmartwychwstania kart.
     */
    private suspend fun flushPendingLookups(tally: SyncTally?): SyncFailure? = pendingFlushMutex.withLock {
        if (!networkMonitor.isCurrentlyOnline()) return@withLock classifyFailure(null, null, transport = true)
        // Tylko stuby czekające — te z „wymaga sprawdzenia" pomijamy (zero kolejnych lookupów).
        val pending = offlineStore.queuedPendingLookups()
        var firstFailure: SyncFailure? = null
        // Stub należy do własnego profilu, niezależnie od tego, który profil jest teraz aktywny.
        for ((profileId, items) in pending.groupBy { it.profileId }) {
            val inboxResult = attempt {
                api.listWordLists(profileId).find { it.is_pending_inbox } ?: api.ensurePendingInbox(profileId)
            }
            val inboxFailure = inboxResult.exceptionOrNull()?.toSyncFailure()
            if (inboxFailure != null) {
                if (inboxFailure.stopsSync()) return@withLock inboxFailure
                if (firstFailure == null) firstFailure = inboxFailure
                continue
            }
            val inbox = inboxResult.getOrThrow()
            val inboxId = inbox.id
            offlineStore.upsertLists(profileId, listOf(inbox))
            var anyDone = false
            for (item in items) {
                // Stub mógł zostać usunięty (np. „Usuń listę”) między snapshotem a teraz — pomiń.
                if (!offlineStore.pendingLookupExists(item.clientId)) continue
                tally?.let { it.sent++ }
                val rawLemma = item.lemma.trim()
                var lookup = attempt { api.lookup(LookupRequest(text = rawLemma, profile_id = profileId)) }
                // Powtórka na lowercase gdy pierwszy strzał nie był pewny (np. „FIRANKA”).
                if (lookup.getOrNull()?.confident != true && rawLemma != rawLemma.lowercase()) {
                    val lower = attempt { api.lookup(LookupRequest(text = rawLemma.lowercase(), profile_id = profileId)) }
                    if (lower.getOrNull() != null && (lower.getOrThrow().confident || lookup.isFailure)) lookup = lower
                }
                // Ponowne sprawdzenie po (wolnym) lookupie — czyszczenie mogło wejść w tym czasie.
                if (!offlineStore.pendingLookupExists(item.clientId)) continue

                val resp = lookup.getOrNull()
                if (resp == null) {
                    val failure = lookup.exceptionOrNull()!!.toSyncFailure()
                    if (failure.stopsSync()) return@withLock failure
                    if (firstFailure == null) firstFailure = failure
                    continue
                }

                // Poważne wątpliwości: nie tworzymy karty, nie palimy enrichmentu.
                if (!resp.confident) {
                    val suggestionsJson = runCatching {
                        json.encodeToString(ListSerializer(LookupCandidate.serializer()), resp.candidates)
                    }.getOrNull()
                    offlineStore.markLookupNeedsReview(item.clientId, suggestionsJson)
                    continue
                }

                val resolved = resp.candidates.firstOrNull()
                val lemma = resolved?.lemma?.takeIf { it.isNotBlank() } ?: rawLemma
                var added = attempt {
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
                var addFailure = added.exceptionOrNull()?.toSyncFailure()
                var http = added.exceptionOrNull() as? HttpException
                // Wariant z surowym słowem tylko po odrzuceniu 4xx; błąd sieci/5xx i 409 to nie powód do zmiany payloadu.
                if (addFailure != null && addFailure.kind == FailureKind.CLIENT && http?.code() != 409 && lemma != rawLemma) {
                    added = attempt {
                        api.addWordToList(inboxId, WordListAddWordRequest(lemma = rawLemma, profile_id = profileId))
                    }
                    addFailure = added.exceptionOrNull()?.toSyncFailure()
                    http = added.exceptionOrNull() as? HttpException
                }
                val alreadyOnList = http?.code() == 409 &&
                    attempt { api.listWords(inboxId, profileId) }.getOrNull().orEmpty().any {
                        it.lemma_l2.equals(lemma, ignoreCase = true) || it.lemma_l2.equals(rawLemma, ignoreCase = true)
                    }
                if (addFailure == null || alreadyOnList) {
                    // Kasuj stub NATYCHMIAST — żaden kolejny flush nie doda go ponownie.
                    offlineStore.removePendingLookup(item.clientId)
                    added.getOrNull()?.let { card ->
                        offlineStore.upsertCards(profileId, listOf(card), deckId = inboxId)
                        watchOfflineIfPending(card)
                    }
                    tally?.let { it.confirmed++ }
                    anyDone = true
                } else {
                    if (addFailure.stopsSync()) return@withLock addFailure
                    if (firstFailure == null) firstFailure = addFailure
                }
            }
            if (anyDone) {
                attempt {
                    val words = api.listWords(inboxId, profileId)
                    offlineStore.cacheCardsFromList(profileId, words, deckId = inboxId)
                }
            }
        }
        firstFailure
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
        offlineStore.upsertLists(profileId, listOf(inbox))
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
        val result = LocalAnswerCheck.check(answer, content, direction)
        return CheckAnswerResponse(
            correct = result.correct,
            expected = result.expected,
            accepted_as_typo = result.acceptedAsTypo,
            accepted_as_synonym = result.acceptedAsSynonym,
        )
    }

    suspend fun getSettings(): UserSettingsResponse =
        offlineStore.localUserSettings() ?: defaultSettings()

    /**
     * Alarm przypomnienia tylko dla aktywnego właściciela z zapisanymi ustawieniami.
     * Domyślne ustawienia mają przypomnienia włączone, więc bez konta nie wolno ich użyć.
     * [onlyIfChanged] pomija ponowne ustawianie alarmu po każdym syncu.
     */
    suspend fun restoreStudyReminders(onlyIfChanged: Boolean = false) {
        val settings = if (hasActiveOwner()) offlineStore.localUserSettings() else null
        val enabled = settings != null &&
            (settings.study_reminder_enabled || settings.cards_ready_push_enabled)
        val hour = settings?.reminder_hour ?: notificationScheduler.reminderHour()
        if (onlyIfChanged &&
            enabled == notificationScheduler.reminderEnabled() &&
            (!enabled || hour == notificationScheduler.reminderHour())
        ) {
            return
        }
        notificationScheduler.scheduleStudyReminder(
            hour = hour,
            enabled = enabled,
            minute = notificationScheduler.reminderMinute(),
        )
    }

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
        show_associations = u.show_associations ?: show_associations,
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
        show_associations = show_associations,
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

    suspend fun cardCountsByProfile(): Map<String, Int> = offlineStore.cardCountsByProfile()

    /** Przełącza parę języków w Room. PUT /activate dogania PG, gdy jest sieć. */
    suspend fun activateLocalProfile(profileId: String): LanguageProfileResponse {
        val profiles = offlineStore.cachedProfiles()
        val target = profiles.firstOrNull { it.id == profileId }
            ?: offlineStore.cachedActiveProfile()?.takeIf { it.id == profileId }
            ?: error("no_profile")
        val updated = profiles.map { it.copy(is_active = it.id == profileId) }
            .ifEmpty { listOf(target.copy(is_active = true)) }
        offlineStore.cacheProfiles(updated)
        val active = target.copy(is_active = true)
        syncActiveProfileToLocal(active)
        if (networkMonitor.isCurrentlyOnline()) {
            runCatching { api.activateProfile(profileId) }
        }
        requestBackgroundSync()
        return active
    }

    suspend fun refreshProfilesFromNetwork(): List<LanguageProfileResponse> {
        if (!networkMonitor.isCurrentlyOnline()) return listProfiles()
        apiTry { api.listProfiles() }
            .onSuccess { applyRemoteProfiles(it) }
        return listProfiles()
    }

    private suspend fun applyRemoteProfiles(profiles: List<LanguageProfileResponse>): Unit = offlineStore.guardedWrite {
        val localActive = offlineStore.cachedActiveProfile()
        val chosenId = tokenStore.activeProfileId.value ?: localActive?.id
        val merged = mergeRemoteProfiles(profiles, localActive, chosenId)
        offlineStore.cacheProfiles(merged)
        val chosen = merged.firstOrNull { it.is_active } ?: return@guardedWrite
        syncActiveProfileToLocal(chosen.copy(is_active = true))
    }

    suspend fun getActiveProfile(): LanguageProfileResponse? =
        offlineStore.cachedActiveProfile()

    suspend fun hasCachedProfile(): Boolean = offlineStore.cachedActiveProfile() != null

    private suspend fun syncActiveProfileToLocal(profile: LanguageProfileResponse) {
        tokenStore.saveActiveProfile(profile.id)
        tokenStore.saveAppLang(profile.app_lang)
        offlineStore.cacheProfile(profile)
    }

    /** Room profile is UI locale source of truth; TokenStore mirrors it for early boot. */
    suspend fun applyAppLocaleFromActiveProfile(): String {
        val fromProfile = offlineStore.cachedActiveProfile()?.appLang?.trim()?.lowercase().orEmpty()
        val stored = tokenStore.peekAppLang().trim().lowercase()
        val appLang = fromProfile.ifBlank { stored }.ifBlank { "en" }
        if (fromProfile.isNotBlank() && fromProfile != stored) {
            tokenStore.saveAppLang(fromProfile)
        }
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
        syncActiveProfileToLocal(profile.copy(is_active = true))
        return profile
    }

    suspend fun activateProfile(profileId: String): LanguageProfileResponse =
        activateLocalProfile(profileId)

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
        syncActiveProfileToLocal(optimistic)
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
        syncActiveProfileToLocal(profile)
        return profile
    }

    suspend fun switchToLangPair(
        appLang: String,
        learningLang: String,
        cefr: String,
    ): LanguageProfileResponse {
        val app = appLang.trim().lowercase()
        val learning = learningLang.trim().lowercase()
        val local = listProfiles()
        val existingLocal = findLangPair(local, app, learning)
        when (val action = langPairSwitch(existingLocal, tokenStore.activeProfileId.value)) {
            LangPairSwitch.Keep -> return activateLocalProfile(existingLocal!!.id)
            is LangPairSwitch.Activate -> return activateLocalProfile(action.profileId)
            LangPairSwitch.Create -> {
                val remote = refreshProfilesFromNetwork()
                val existing = findLangPair(remote, app, learning)
                val profile = when (val remoteAction = langPairSwitch(existing, tokenStore.activeProfileId.value)) {
                    LangPairSwitch.Keep -> activateLocalProfile(existing!!.id)
                    is LangPairSwitch.Activate -> activateLocalProfile(remoteAction.profileId)
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
                        activateLocalProfile(found.id)
                    }
                }
                tokenStore.saveAppLang(profile.app_lang)
                requestBackgroundSync()
                return profile
            }
        }
    }

    suspend fun getMe() = api.me()

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

    suspend fun escalateCardCorrection(cardId: String, correctionId: String): CorrectionEscalateResponse {
        return api.escalateCardCorrection(cardId, correctionId, activeProfileId())
    }

    suspend fun getCardHistory(cardId: String): CardHistoryResponse {
        return api.getCardHistory(cardId, activeProfileId())
    }

    suspend fun retryCardEnrichment(cardId: String): CardResponse {
        val updated = api.retryCardEnrichment(cardId, activeProfileId())
        offlineStore.upsertCards(activeProfileId(), listOf(updated))
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

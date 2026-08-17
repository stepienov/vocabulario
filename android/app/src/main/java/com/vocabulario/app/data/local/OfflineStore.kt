package com.vocabulario.app.data.local

import android.content.Context
import androidx.room.Room
import androidx.room.withTransaction
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.DashboardStatsResponse
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.SyncCardItem
import com.vocabulario.app.data.api.SyncListItem
import com.vocabulario.app.data.api.SyncPullResponse
import com.vocabulario.app.data.api.SyncSrsState
import com.vocabulario.app.data.api.UserSettingsResponse
import com.vocabulario.app.data.api.WordListResponse
import com.vocabulario.app.data.local.db.AppDatabase
import com.vocabulario.app.data.local.db.CachedCardEntity
import com.vocabulario.app.data.local.db.CachedListEntity
import com.vocabulario.app.data.local.db.CachedProfileEntity
import com.vocabulario.app.data.local.db.LocalSettingsEntity
import com.vocabulario.app.data.local.db.OutboxOpEntity
import com.vocabulario.app.data.local.db.PendingLookupEntity
import com.vocabulario.app.data.local.db.PendingMoveEntity
import com.vocabulario.app.data.local.db.PendingReviewEntity
import com.vocabulario.app.data.local.db.PendingUndoEntity
import com.vocabulario.app.data.local.db.SyncMetaEntity
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class OfflineStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val db = Room.databaseBuilder(context, AppDatabase::class.java, "vocabulario.db")
        .addMigrations(
            AppDatabase.MIGRATION_6_7,
            AppDatabase.MIGRATION_7_8,
            AppDatabase.MIGRATION_8_9,
        )
        // Zachowaj dane (w tym niewysłany outbox) przy aktualizacji z v6.
        // Twardy reset tylko dla prehistorycznych wersji, których w praktyce nie ma w terenie.
        .fallbackToDestructiveMigrationFrom(1, 2, 3, 4, 5)
        .build()
    private val cardDao = db.cachedCardDao()
    private val listDao = db.cachedListDao()
    private val reviewDao = db.pendingReviewDao()
    private val moveDao = db.pendingMoveDao()
    private val lookupDao = db.pendingLookupDao()
    private val undoDao = db.pendingUndoDao()
    private val settingsDao = db.localSettingsDao()
    private val syncMetaDao = db.syncMetaDao()
    private val profileDao = db.cachedProfileDao()
    private val outboxDao = db.outboxOpDao()
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun applyPull(profileId: String, pull: SyncPullResponse, fullReplace: Boolean) {
        db.withTransaction {
            applyPullLocked(profileId, pull, fullReplace)
        }
    }

    private suspend fun applyPullLocked(profileId: String, pull: SyncPullResponse, fullReplace: Boolean) {
        // Settings: telefon jest źródłem prawdy. Pull wkleja je tylko gdy Room jest pusty
        // (pierwszy login / reinstall). Inkrementalny sync i fullReplace przy zmianie
        // profilu NIE mogą cofać trybu / kierunku / układu karty.
        if (localUserSettings() == null) {
            saveSettings(pull.settings)
        }
        // Keep local Pending inbox + unflushed lookup stubs across full replace.
        val localInbox = listDao.pendingInbox(profileId)
        // Preserve offline-created lists (local:<uuid>) that haven't been pushed/remapped yet.
        val localOnlyLists = listDao.forProfile(profileId).filter { it.isLocalOnly }
        if (fullReplace) {
            cardDao.clearProfile(profileId)
            listDao.clearProfile(profileId)
        }
        if (pull.deleted_card_ids.isNotEmpty()) {
            cardDao.deleteIds(pull.deleted_card_ids)
        }
        // Tombstony list (inkrementalny pull): usuń listę i jej karty (nie wracają do „Uczę się”).
        for (deletedListId in pull.deleted_list_ids) {
            val deckCards = cardDao.cardsByDeckId(deletedListId)
            if (deckCards.isNotEmpty()) {
                cardDao.deleteIds(deckCards.map { it.id })
            }
            listDao.deleteById(deletedListId)
        }
        val listEntities = pull.lists.map { it.toEntity(profileId) }
        if (listEntities.isNotEmpty()) {
            listDao.upsertAll(listEntities)
        }
        consolidatePendingInboxes(profileId)
        if (localInbox != null &&
            lookupDao.forProfile(profileId).isNotEmpty() &&
            listDao.forProfile(profileId).none { it.isPendingInbox }
        ) {
            listDao.upsertAll(listOf(localInbox))
        }
        val entities = pull.cards.map { it.toEntity() }
        if (entities.isNotEmpty()) {
            cardDao.upsertAll(entities)
        }
        if (fullReplace && localOnlyLists.isNotEmpty()) {
            val present = listDao.forProfile(profileId).map { it.id }.toSet()
            val restore = localOnlyLists.filter { it.id !in present }
            if (restore.isNotEmpty()) listDao.upsertAll(restore)
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

    suspend fun cacheProfile(profile: LanguageProfileResponse) {
        if (profile.is_active) {
            profileDao.deactivateOthers(profile.id)
        }
        profileDao.upsert(
            CachedProfileEntity(
                id = profile.id,
                nativeLang = profile.appLang,
                learningLang = profile.learning_lang,
                cefrLevel = profile.cefr_level,
                selectedTensesJson = json.encodeToString(
                    kotlinx.serialization.builtins.ListSerializer(kotlinx.serialization.serializer<String>()),
                    profile.selected_tenses,
                ),
                isActive = profile.is_active,
                jsonBlob = json.encodeToString(LanguageProfileResponse.serializer(), profile),
            ),
        )
    }

    suspend fun cachedActiveProfile(): LanguageProfileResponse? {
        val raw = profileDao.active()?.jsonBlob ?: return null
        return runCatching { json.decodeFromString(LanguageProfileResponse.serializer(), raw) }.getOrNull()
    }

    suspend fun cachedProfiles(): List<LanguageProfileResponse> =
        profileDao.all().mapNotNull { entity ->
            runCatching {
                json.decodeFromString(LanguageProfileResponse.serializer(), entity.jsonBlob)
            }.getOrNull()
        }

    suspend fun cacheProfiles(profiles: List<LanguageProfileResponse>) {
        db.withTransaction {
            if (profiles.isEmpty()) {
                profileDao.deleteAll()
            } else {
                profileDao.deleteNotIn(profiles.map { it.id })
                profiles.forEach { cacheProfile(it) }
            }
        }
    }

    suspend fun buildDashboardStats(profileId: String, newLimit: Int, days: Int = 7): DashboardStatsResponse =
        LocalDashboard.build(
            learningCards = cardDao.systemListCards(profileId),
            newLimit = newLimit,
            nowMs = System.currentTimeMillis(),
            periodDays = days,
        )

    /**
     * Dopisuje karty bez kasowania reszty decku. [cacheCardsFromList] robi replace
     * i nie wolno go wołać z jedną kartą.
     */
    suspend fun upsertCards(
        profileId: String,
        cards: List<CardResponse>,
        deckId: String? = null,
    ) {
        if (cards.isEmpty()) return
        val entities = cards.map { card ->
            val existing = cardDao.byId(card.id)
            CachedCardEntity(
                id = card.id,
                profileId = profileId,
                deckId = deckId ?: existing?.deckId,
                lemmaL2 = card.lemma_l2,
                glossPrimary = card.gloss_primary,
                pos = card.pos,
                contentJson = Json.encodeToString(JsonObject.serializer(), card.content),
                enrichmentStatus = card.enrichment_status,
                contentReviewStatus = card.content_review_status,
                cardActivityStatus = card.card_activity_status,
                hasContentChanges = card.has_content_changes,
                status = card.srs_status?.takeIf { it.isNotBlank() } ?: existing?.status ?: "new",
                nextReviewAt = existing?.nextReviewAt,
                lastReviewedAt = existing?.lastReviewedAt,
                intervalDays = card.srs_interval_days ?: existing?.intervalDays ?: 0.0,
                ease = existing?.ease ?: 2.5,
                repetitions = existing?.repetitions ?: 0,
                lapses = existing?.lapses ?: 0,
                stability = existing?.stability,
                difficulty = existing?.difficulty,
                fsrsStep = existing?.fsrsStep,
                lastGrade = existing?.lastGrade,
                updatedAt = System.currentTimeMillis(),
            )
        }
        cardDao.upsertAll(entities)
    }

    suspend fun localSettings(): LocalSettingsEntity? = settingsDao.get()

    suspend fun localUserSettings(): UserSettingsResponse? {
        val raw = settingsDao.get()?.jsonBlob ?: return null
        return runCatching { json.decodeFromString(UserSettingsResponse.serializer(), raw) }.getOrNull()
    }

    // ---- Reaktywne odczyty (Room jako źródło zmian) ----

    /**
     * Sygnatura list — bez wordCount (licznik jest przeliczany przy odczycie, zapis nie może
     * ponownie wyzwalać obserwatora → pętla loadLists → applyPendingInboxCounts → zapis).
     */
    fun listsSignature(profileId: String): Flow<String> =
        listDao.observeForProfile(profileId).map { rows ->
            rows.sortedBy { it.id }.joinToString(";") {
                "${it.id}|${it.name}|${it.isSystem}|${it.isPendingInbox}|${it.pendingDelete}|${it.isLocalOnly}"
            }
        }

    /** Sygnatura kart — id+deck+enrichment+activity (bez content/updatedAt). */
    fun cardsSignature(profileId: String): Flow<String> =
        cardDao.observeForProfile(profileId).map { rows ->
            rows.sortedBy { it.id }.joinToString(";") {
                "${it.id}|${it.deckId.orEmpty()}|${it.enrichmentStatus}|${it.cardActivityStatus.orEmpty()}"
            }
        }

    /** Liczba słów widocznych na liście — zgodna z [localWords] / [listWords]. */
    suspend fun countWordsOnList(profileId: String, list: WordListResponse): Int {
        return when {
            list.is_pending_inbox -> {
                val stubs = lookupDao.forProfile(profileId).map { it.toStubCard() }
                val cards = pendingInboxCards(profileId).map { it.toCardResponse() }
                mergePendingInboxDisplay(stubs, cards).size
            }
            list.is_system -> cardDao.systemListCards(profileId).size
            else -> cardDao.cardsForDeck(profileId, list.id).size
        }
    }

    suspend fun withComputedWordCounts(
        profileId: String,
        lists: List<WordListResponse>,
    ): List<WordListResponse> = lists.map { list ->
        list.copy(word_count = countWordsOnList(profileId, list))
    }

    fun observeSettings(): Flow<UserSettingsResponse?> =
        settingsDao.observe().map { entity ->
            entity?.jsonBlob?.let {
                runCatching { json.decodeFromString(UserSettingsResponse.serializer(), it) }.getOrNull()
            }
        }

    suspend fun learningCards(profileId: String): List<CachedCardEntity> =
        cardDao.learningCards(profileId)

    suspend fun allCards(profileId: String): List<CachedCardEntity> =
        cardDao.forProfile(profileId)

    suspend fun cardById(id: String): CachedCardEntity? = cardDao.byId(id)

    suspend fun localLists(profileId: String): List<WordListResponse> {
        consolidatePendingInboxes(profileId)
        return listDao.forProfile(profileId).map { it.toResponse() }
    }

    /** One pending inbox per profile — drop local duplicate when server inbox exists. */
    suspend fun consolidatePendingInboxes(profileId: String): CachedListEntity? {
        val pending = listDao.forProfile(profileId).filter { it.isPendingInbox }
        if (pending.isEmpty()) return null
        if (pending.size == 1) return pending.first()
        val canonical = pending.firstOrNull { !it.id.startsWith("local-pending-inbox-") }
            ?: pending.maxBy { it.updatedAt }
        for (duplicate in pending) {
            if (duplicate.id == canonical.id) continue
            lookupDao.migrateLookupListId(duplicate.id, canonical.id)
            cardDao.migrateDeckId(duplicate.id, canonical.id)
            listDao.deleteById(duplicate.id)
        }
        return canonical
    }

    /** Wszystkie karty na skrzynce Oczekujące (lokalny + serwerowy deckId). */
    suspend fun pendingInboxCards(profileId: String): List<CachedCardEntity> {
        consolidatePendingInboxes(profileId)
        val inboxIds = listDao.forProfile(profileId).filter { it.isPendingInbox }.map { it.id }
        return inboxIds.flatMap { cardDao.cardsForDeck(profileId, it) }.distinctBy { it.id }
    }

    /**
     * Jeden kafelek na lemma: stub znika gdy istnieje karta serwerowa o tym samym słowie.
     * Kolejność: czekanie/tworzenie → gotowe.
     */
    fun mergePendingInboxDisplay(
        stubs: List<CardResponse>,
        cards: List<CardResponse>,
    ): List<CardResponse> = PendingInboxDisplay.merge(stubs, cards)

    /** Wszystkie deckId skrzynki Oczekujące (lokalny + serwerowy). */
    suspend fun allPendingInboxDeckIds(profileId: String): List<String> {
        consolidatePendingInboxes(profileId)
        return listDao.forProfile(profileId).filter { it.isPendingInbox }.map { it.id }
    }

    /** Czy stub o danym clientId nadal czeka w kolejce (guard przeciw zmartwychwstaniu kart). */
    suspend fun pendingLookupExists(clientId: String): Boolean =
        lookupDao.all().any { it.clientId == clientId }

    /** Kasuje same stuby lookupu profilu (bez ruszania kart) — pierwszy krok czyszczenia. */
    suspend fun clearPendingLookupsOnly(profileId: String) {
        val stubs = lookupDao.forProfile(profileId)
        if (stubs.isNotEmpty()) {
            lookupDao.deleteIds(stubs.map { it.clientId })
        }
    }

    /** Czyści skrzynkę Oczekujące w Room (stuby + karty na wszystkich deckId inbox). */
    suspend fun clearPendingInboxLocally(profileId: String) {
        consolidatePendingInboxes(profileId)
        val stubs = lookupDao.forProfile(profileId)
        if (stubs.isNotEmpty()) {
            lookupDao.deleteIds(stubs.map { it.clientId })
        }
        val cards = pendingInboxCards(profileId)
        if (cards.isNotEmpty()) {
            cardDao.deleteIds(cards.map { it.id })
        }
        syncPendingInboxWordCount(profileId)
    }

    suspend fun pendingLookupCount(profileId: String): Int =
        lookupDao.forProfile(profileId).size

    /** Pending inbox visibility/count follows pending_lookups, not server word_count alone. */
    suspend fun applyPendingInboxCounts(
        profileId: String,
        lists: List<WordListResponse>,
        online: Boolean,
    ): List<WordListResponse> {
        consolidatePendingInboxes(profileId)
        val stubCount = pendingLookupCount(profileId)
        var visible = lists.filter { !it.id.startsWith("local-pending-inbox-") }
        val pendingBoxes = visible.filter { it.is_pending_inbox }
        if (pendingBoxes.size > 1) {
            val keep = pendingBoxes.first()
            visible = visible.filter { !it.is_pending_inbox || it.id == keep.id }
        }
        // Gdy nie ma serwerowej skrzynki, a są stuby (offline) — dołóż lokalną, by była widoczna.
        if (visible.none { it.is_pending_inbox } && stubCount > 0) {
            visible = visible + ensureLocalPendingInbox(profileId).toResponse()
        }
        return visible.map { list ->
            if (!list.is_pending_inbox) {
                return@map list.copy(word_count = countWordsOnList(profileId, list))
            }
            // ZASADA: chip = dokładna liczba kafelków; widoczna wtw. > 0.
            val serverInbox = online && !list.id.startsWith("local-pending-inbox-")
            val count = if (serverInbox) {
                // Serwer = ŚWIEŻE źródło prawdy dla kart (maleje po usunięciu) + stuby offline
                // (needs_review / jeszcze niewysłane; stub kasujemy dokładnie gdy powstaje karta,
                // więc brak podwójnego liczenia). NIE czytamy nieprzyciętego cache Room.
                list.word_count + stubCount
            } else {
                // Offline: lokalna prawda (stuby + karty utworzone offline).
                countWordsOnList(profileId, list)
            }
            listDao.byId(list.id)?.let { entity ->
                if (entity.wordCount != count) {
                    listDao.upsertAll(listOf(entity.copy(wordCount = count)))
                }
            }
            list.copy(word_count = count)
        }
    }

    suspend fun cacheLists(profileId: String, lists: List<WordListResponse>) {
        consolidatePendingInboxes(profileId)
        val stubCount = pendingLookupCount(profileId)
        val serverLists = lists.filter { !it.id.startsWith("local-pending-inbox-") }
        val entities = serverLists.map { list ->
            val entity = list.toEntity(profileId)
            if (list.is_pending_inbox) {
                // Świeży licznik serwera + stuby offline. NIE mieszamy starej wartości z cache
                // (to utrwalało nieaktualne „(1)" po usunięciu wszystkich słów).
                entity.copy(wordCount = list.word_count + stubCount)
            } else {
                entity
            }
        }
        val serverIds = entities.map { it.id }.toSet()
        // Drop cached lists removed on server — offline was showing stale Room rows.
        listDao.forProfile(profileId).forEach { cached ->
            if (cached.id in serverIds) return@forEach
            // Never drop offline-created lists awaiting create/remap.
            if (cached.isLocalOnly) return@forEach
            if (cached.isPendingInbox && serverLists.any { it.is_pending_inbox }) {
                listDao.deleteById(cached.id)
                return@forEach
            }
            if (!cached.isPendingInbox) {
                listDao.deleteById(cached.id)
            }
        }
        listDao.upsertAll(entities)
        if (stubCount > 0 && entities.none { it.isPendingInbox }) {
            val inbox = ensureLocalPendingInbox(profileId)
            listDao.upsertAll(
                listOf(inbox.copy(wordCount = stubCount, updatedAt = System.currentTimeMillis())),
            )
        }
    }

    suspend fun ensureLocalPendingInbox(profileId: String): CachedListEntity {
        consolidatePendingInboxes(profileId)
        listDao.pendingInbox(profileId)?.let { return it }
        val entity = CachedListEntity(
            id = "local-pending-inbox-$profileId",
            profileId = profileId,
            name = "Pending",
            isSystem = false,
            isPendingInbox = true,
            wordCount = 0,
            createdAt = Instant.now().toString(),
            updatedAt = System.currentTimeMillis(),
        )
        listDao.upsertAll(listOf(entity))
        return entity
    }

    suspend fun localWords(profileId: String, listId: String, isSystem: Boolean): List<CardResponse> {
        val cards = if (isSystem) {
            cardDao.systemListCards(profileId)
        } else {
            cardDao.cardsForDeck(profileId, listId)
        }
        val mapped = cards.map { it.toCardResponse() }
        if (!isSystem) {
            val pendingInbox = listDao.byId(listId)?.isPendingInbox == true ||
                listDao.pendingInbox(profileId)?.id == listId
            if (pendingInbox) {
                val stubs = lookupDao.forProfile(profileId).map { it.toStubCard() }
                val inboxCards = pendingInboxCards(profileId).map { it.toCardResponse() }
                return mergePendingInboxDisplay(stubs, inboxCards)
            }
            val stubs = lookupDao.forList(listId).map { it.toStubCard() }
            return stubs + mapped
        }
        return mapped
    }

    suspend fun lookupStubsForList(listId: String): List<CardResponse> =
        lookupDao.forList(listId).map { it.toStubCard() }

    suspend fun lookupStubsForProfile(profileId: String): List<CardResponse> =
        lookupDao.forProfile(profileId).map { it.toStubCard() }

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

    suspend fun restoreCard(card: CachedCardEntity) {
        cardDao.update(card)
    }

    suspend fun applyServerSrs(states: List<SyncSrsState>) {
        for (srs in states) {
            val card = cardDao.byId(srs.card_id) ?: continue
            cardDao.update(card.withSrs(srs))
        }
    }

    suspend fun moveCardLocally(cardId: String, targetListId: String?, systemListId: String?): String {
        moveCardsLocally(listOf(cardId), targetListId, systemListId)
        return cardId
    }

    /** Jedna transakcja — jeden emit Room, bez liczenia w nawiasie po każdej karcie. */
    suspend fun moveCardsLocally(
        cardIds: List<String>,
        targetListId: String?,
        systemListId: String?,
    ) {
        if (cardIds.isEmpty()) return
        val newDeckId = when {
            targetListId == null -> null
            systemListId != null && targetListId == systemListId -> null
            else -> targetListId
        }
        val now = System.currentTimeMillis()
        db.withTransaction {
            for (cardId in cardIds) {
                val card = cardDao.byId(cardId) ?: continue
                cardDao.update(card.copy(deckId = newDeckId, updatedAt = now))
                moveDao.insert(
                    PendingMoveEntity(
                        clientId = UUID.randomUUID().toString(),
                        cardId = cardId,
                        targetListId = newDeckId,
                        movedAt = now,
                    ),
                )
            }
        }
    }

    suspend fun enqueueReview(review: PendingReviewEntity) {
        reviewDao.insert(review)
    }

    suspend fun pendingReviews(): List<PendingReviewEntity> = reviewDao.all()

    suspend fun removePendingReviews(clientIds: List<String>) {
        if (clientIds.isNotEmpty()) reviewDao.deleteIds(clientIds)
    }

    suspend fun removePendingReview(clientId: String) {
        reviewDao.delete(clientId)
    }

    suspend fun pendingMoves(): List<PendingMoveEntity> = moveDao.all()

    suspend fun removePendingMoves(clientIds: List<String>) {
        if (clientIds.isNotEmpty()) moveDao.deleteIds(clientIds)
    }

    suspend fun pendingCount(): Int = reviewDao.count()

    suspend fun enqueueOfflineLookup(profileId: String, lemma: String): PendingLookupEntity? {
        val trimmed = lemma.trim()
        if (trimmed.isEmpty()) return null
        lookupDao.findLemma(profileId, trimmed)?.let { return null }
        val inbox = ensureLocalPendingInbox(profileId)
        val entity = PendingLookupEntity(
            clientId = UUID.randomUUID().toString(),
            profileId = profileId,
            listId = inbox.id,
            lemma = trimmed,
            createdAt = System.currentTimeMillis(),
        )
        lookupDao.insert(entity)
        syncPendingInboxWordCount(profileId)
        return entity
    }

    suspend fun pendingLookups(): List<PendingLookupEntity> = lookupDao.all()

    /** Tylko stuby czekające na flush (bez tych z „wymaga sprawdzenia"). */
    suspend fun queuedPendingLookups(): List<PendingLookupEntity> =
        lookupDao.all().filter { it.status != "needs_review" }

    suspend fun pendingLookupById(clientId: String): PendingLookupEntity? =
        lookupDao.byId(clientId)

    /** Oznacza stub jako „wymaga sprawdzenia" i zapisuje propozycje. NIE tworzy karty na serwerze. */
    suspend fun markLookupNeedsReview(clientId: String, suggestionsJson: String?) {
        lookupDao.setStatus(clientId, "needs_review", suggestionsJson)
        lookupDao.byId(clientId)?.let { syncPendingInboxWordCount(it.profileId) }
    }

    suspend fun removePendingLookup(clientId: String) {
        val removed = lookupDao.all().firstOrNull { it.clientId == clientId }
        lookupDao.deleteIds(listOf(clientId))
        removed?.let { syncPendingInboxWordCount(it.profileId) }
    }

    private suspend fun syncPendingInboxWordCount(profileId: String) {
        val inbox = listDao.pendingInbox(profileId) ?: return
        val count = countWordsOnList(profileId, inbox.toResponse())
        if (inbox.wordCount != count) {
            listDao.upsertAll(listOf(inbox.copy(wordCount = count)))
        }
    }

    suspend fun clearPendingLookupsForList(listId: String) {
        val listMeta = listDao.byId(listId)
        val profileId = listMeta?.profileId
            ?: lookupDao.forList(listId).firstOrNull()?.profileId
        if (listMeta?.isPendingInbox == true && profileId != null) {
            val items = lookupDao.forProfile(profileId)
            if (items.isNotEmpty()) {
                lookupDao.deleteIds(items.map { it.clientId })
            }
            syncPendingInboxWordCount(profileId)
            return
        }
        val items = lookupDao.forList(listId)
        if (items.isNotEmpty()) {
            lookupDao.deleteIds(items.map { it.clientId })
        }
        if (profileId != null) {
            syncPendingInboxWordCount(profileId)
        } else {
            listDao.byId(listId)?.let { inbox ->
                listDao.upsertAll(
                    listOf(inbox.copy(wordCount = 0, updatedAt = System.currentTimeMillis())),
                )
            }
        }
    }

    suspend fun cardSrsSnapshot(cardId: String): SyncSrsState? {
        val card = cardDao.byId(cardId) ?: return null
        return card.toSyncSrsState()
    }

    suspend fun applySrsSnapshot(srs: SyncSrsState) {
        val card = cardDao.byId(srs.card_id) ?: return
        cardDao.update(card.withSrs(srs))
    }

    suspend fun enqueuePendingUndo(clientId: String, srs: SyncSrsState) {
        undoDao.insert(
            PendingUndoEntity(
                clientId = clientId,
                srsJson = json.encodeToString(SyncSrsState.serializer(), srs),
            ),
        )
    }

    suspend fun pendingUndos(): List<PendingUndoEntity> = undoDao.all()

    suspend fun removePendingUndo(clientId: String) {
        undoDao.delete(clientId)
    }

    suspend fun undoReviewLocally(clientId: String, srs: SyncSrsState) {
        removePendingReview(clientId)
        applySrsSnapshot(srs)
    }

    suspend fun removePendingLookups(clientIds: List<String>) {
        if (clientIds.isEmpty()) return
        val profileIds = lookupDao.all()
            .filter { it.clientId in clientIds }
            .map { it.profileId }
            .toSet()
        lookupDao.deleteIds(clientIds)
        profileIds.forEach { syncPendingInboxWordCount(it) }
    }

    // ---- Ujednolicony outbox (mutacje Z3: ustawienia, listy, usuwanie kart) ----

    companion object {
        /** Po tylu nieudanych próbach operacja jest „parkowana”, by nie blokować kolejki. */
        const val MAX_OP_ATTEMPTS = 5
    }

    suspend fun enqueueOp(type: String, payloadJson: String, clientOpId: String = UUID.randomUUID().toString()): String {
        outboxDao.insert(
            OutboxOpEntity(
                clientOpId = clientOpId,
                type = type,
                payloadJson = payloadJson,
                createdAt = System.currentTimeMillis(),
            ),
        )
        return clientOpId
    }

    suspend fun pendingOps(): List<OutboxOpEntity> = outboxDao.pending()

    suspend fun outboxPendingCount(): Int = outboxDao.pendingCount()

    /**
     * 401 na wygasłym tokenie parkowało settings_update i zmiana nigdy nie wylatywała.
     * Po udanym odświeżeniu sesji wracają do kolejki.
     */
    suspend fun unparkAuthFailures() {
        for (op in outboxDao.all()) {
            if (op.status != "parked") continue
            val err = op.lastError.orEmpty()
            if (err.contains("401") || err.contains("Unauthorized", ignoreCase = true)) {
                outboxDao.update(op.copy(status = "pending", attempts = 0, lastError = null))
            }
        }
    }

    suspend fun removeOp(op: OutboxOpEntity) {
        outboxDao.deleteBySeq(op.seq)
    }

    /** Zwiększa licznik prób; parkuje po [MAX_OP_ATTEMPTS], żeby poison-pill nie blokował reszty. */
    suspend fun markOpFailed(op: OutboxOpEntity, error: String?) {
        val attempts = op.attempts + 1
        outboxDao.update(
            op.copy(
                attempts = attempts,
                lastError = error,
                status = if (attempts >= MAX_OP_ATTEMPTS) "parked" else "pending",
            ),
        )
    }

    /** Remap ID listy lokalnej → server ID w cache, kartach, ruchach i payloadach operacji. */
    suspend fun remapLocalListId(localId: String, serverId: String) {
        listDao.byId(localId)?.let { entity ->
            listDao.deleteById(localId)
            listDao.upsertAll(listOf(entity.copy(id = serverId, isLocalOnly = false)))
        }
        cardDao.cardsByDeckId(localId).forEach { card ->
            cardDao.update(card.copy(deckId = serverId, updatedAt = System.currentTimeMillis()))
        }
        moveDao.remapTarget(localId, serverId)
        for (op in outboxDao.pending()) {
            if (!op.payloadJson.contains(localId)) continue
            outboxDao.update(op.copy(payloadJson = op.payloadJson.replace(localId, serverId)))
        }
    }

    // ---- Lokalne mutacje „posiadanych” danych (Room-first) ----

    suspend fun deleteCardLocally(cardId: String) {
        deleteCardsLocally(listOf(cardId))
    }

    suspend fun deleteCardsLocally(cardIds: List<String>) {
        val ids = cardIds.filterNot { it.startsWith("pending-") }
        if (ids.isEmpty()) return
        db.withTransaction { cardDao.deleteIds(ids) }
    }

    suspend fun renameListLocally(listId: String, name: String) {
        listDao.byId(listId)?.let {
            listDao.upsertAll(listOf(it.copy(name = name.trim(), updatedAt = System.currentTimeMillis())))
        }
    }

    /** Tworzy listę tylko lokalnie z ID `local:<uuid>` — remap na server ID po drenażu outboxu. */
    suspend fun createLocalList(profileId: String, name: String): CachedListEntity {
        val entity = CachedListEntity(
            id = "local:${UUID.randomUUID()}",
            profileId = profileId,
            name = name.trim(),
            isSystem = false,
            isPendingInbox = false,
            wordCount = 0,
            createdAt = Instant.now().toString(),
            updatedAt = System.currentTimeMillis(),
            isLocalOnly = true,
        )
        listDao.upsertAll(listOf(entity))
        return entity
    }

    /** Usuwa listę lokalnie wraz z kartami (nie wracają do „Uczę się”). Zwraca ID skasowanych kart. */
    suspend fun deleteListLocally(listId: String): List<String> {
        val deckCards = cardDao.cardsByDeckId(listId)
        val ids = deckCards.map { it.id }
        if (ids.isNotEmpty()) {
            cardDao.deleteIds(ids)
        }
        listDao.deleteById(listId)
        return ids
    }

    suspend fun listNameClashes(profileId: String, name: String): Boolean {
        val n = name.trim().lowercase()
        if (n.isEmpty()) return false
        return listDao.forProfile(profileId).any {
            !it.pendingDelete && it.name.trim().lowercase() == n
        }
    }

    suspend fun localListById(listId: String): WordListResponse? =
        listDao.byId(listId)?.toResponse()

    suspend fun localListByName(profileId: String, name: String): WordListResponse? {
        val n = name.trim().lowercase()
        return listDao.forProfile(profileId).firstOrNull {
            !it.isPendingInbox && it.name.trim().lowercase() == n
        }?.toResponse()
    }

    /** Kasuje niewysłane operacje outboxu odwołujące się do danego tokenu (np. anulowanie create). */
    suspend fun removeOpsReferencing(token: String) {
        outboxDao.pending().filter { it.payloadJson.contains(token) }
            .forEach { outboxDao.deleteBySeq(it.seq) }
    }

    suspend fun cacheCardsFromList(
        profileId: String,
        cards: List<CardResponse>,
        deckId: String? = null,
    ) {
        val newIds = cards.map { it.id }.toSet()
        val existing = if (deckId == null) {
            cardDao.systemListCards(profileId)
        } else {
            cardDao.cardsForDeck(profileId, deckId)
        }
        val stale = existing.filter { it.id !in newIds && !it.id.startsWith("pending-lookup-") }
        if (stale.isNotEmpty()) {
            cardDao.deleteIds(stale.map { it.id })
        }
        if (cards.isEmpty()) return
        val entities = cards.map { card ->
            CachedCardEntity(
                id = card.id,
                profileId = profileId,
                deckId = deckId,
                lemmaL2 = card.lemma_l2,
                glossPrimary = card.gloss_primary,
                pos = card.pos,
                contentJson = Json.encodeToString(JsonObject.serializer(), card.content),
                enrichmentStatus = card.enrichment_status,
                contentReviewStatus = card.content_review_status,
                cardActivityStatus = card.card_activity_status,
                hasContentChanges = card.has_content_changes,
                status = card.srs_status?.takeIf { it.isNotBlank() } ?: "",
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
            contentReviewStatus = content_review_status,
            cardActivityStatus = card_activity_status,
            hasContentChanges = has_content_changes,
            status = srs?.status?.takeIf { it.isNotBlank() } ?: "",
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

    private fun SyncListItem.toEntity(profileId: String) = CachedListEntity(
        id = id,
        profileId = profileId,
        name = name,
        isSystem = is_system,
        isPendingInbox = is_pending_inbox,
        wordCount = word_count,
        createdAt = created_at,
        updatedAt = System.currentTimeMillis(),
    )

    private fun WordListResponse.toEntity(profileId: String) = CachedListEntity(
        id = id,
        profileId = profileId,
        name = name,
        isSystem = is_system,
        isPendingInbox = is_pending_inbox,
        wordCount = word_count,
        createdAt = created_at,
        updatedAt = System.currentTimeMillis(),
    )

    private fun CachedListEntity.toResponse() = WordListResponse(
        id = id,
        name = name,
        is_system = isSystem,
        is_pending_inbox = isPendingInbox,
        word_count = wordCount,
        created_at = createdAt,
    )

    private fun CachedCardEntity.toCardResponse() = CardResponse(
        id = id,
        lemma_l2 = lemmaL2,
        pos = pos,
        gloss_primary = glossPrimary,
        content = parseContent(contentJson),
        lexical_entry_id = null,
        created_at = "",
        enrichment_status = enrichmentStatus,
        content_review_status = contentReviewStatus,
        card_activity_status = cardActivityStatus,
        has_content_changes = hasContentChanges,
        srs_status = status,
        srs_interval_days = intervalDays,
    )

    private fun PendingLookupEntity.toStubCard() = CardResponse(
        id = "pending-lookup-$clientId",
        lemma_l2 = lemma,
        pos = null,
        gloss_primary = null,
        content = buildJsonObject { },
        lexical_entry_id = null,
        created_at = Instant.ofEpochMilli(createdAt).toString(),
        enrichment_status = if (status == "needs_review") "needs_review" else "awaiting_network",
        srs_status = null,
        srs_interval_days = null,
    )

    private fun CachedCardEntity.toSyncSrsState(): SyncSrsState = SyncSrsState(
        card_id = id,
        status = status,
        ease = ease,
        interval_days = intervalDays,
        repetitions = repetitions,
        lapses = lapses,
        next_review_at = nextReviewAt?.let { Instant.ofEpochMilli(it).toString() },
        last_reviewed_at = lastReviewedAt?.let { Instant.ofEpochMilli(it).toString() },
        last_grade = lastGrade,
        stability = stability,
        difficulty = difficulty,
        fsrs_step = fsrsStep,
    )

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

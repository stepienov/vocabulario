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
import com.vocabulario.app.data.EnrichmentStatus
import com.vocabulario.app.data.SYSTEM_LIST_NAME
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
import com.vocabulario.app.data.local.db.OwnerPhase
import com.vocabulario.app.data.local.db.SessionOwnerEntity
import com.vocabulario.app.data.local.db.SyncMetaEntity
import com.vocabulario.app.data.session.LoginDecision
import com.vocabulario.app.data.session.LogoutConsent
import com.vocabulario.app.data.session.OwnerContext
import com.vocabulario.app.data.session.OwnerScope
import com.vocabulario.app.data.session.OwnerSnapshot
import com.vocabulario.app.data.session.SupersededException
import com.vocabulario.app.data.session.UnsentChangesException
import com.vocabulario.app.data.session.consentCovers
import com.vocabulario.app.data.session.ownerContextOf
import com.vocabulario.app.data.session.decideLogin
import com.vocabulario.app.data.sync.BlockedItem
import com.vocabulario.app.data.sync.BlockedKind
import com.vocabulario.app.data.sync.OP_CONTENT_REPORT
import com.vocabulario.app.data.sync.OP_PROFILE_ACTIVATE
import com.vocabulario.app.data.sync.OP_PROFILE_UPDATE
import com.vocabulario.app.data.sync.PROFILE_OP_SENT
import com.vocabulario.app.data.sync.ProfileEditPlan
import com.vocabulario.app.data.sync.ProfileFields
import com.vocabulario.app.data.sync.ProfileOpView
import com.vocabulario.app.data.sync.ProfileUpdatePayload
import com.vocabulario.app.data.sync.overlayDrafts
import com.vocabulario.app.data.sync.planProfileEdit
import com.vocabulario.app.data.sync.withFields
import com.vocabulario.app.data.sync.QueueSnapshot
import com.vocabulario.app.data.session.logoutCovered
import com.vocabulario.app.data.session.unsentFingerprint
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

internal fun buildOfflineDatabase(context: Context, name: String): AppDatabase =
    Room.databaseBuilder(context, AppDatabase::class.java, name)
        .addMigrations(
            AppDatabase.MIGRATION_6_7,
            AppDatabase.MIGRATION_7_8,
            AppDatabase.MIGRATION_8_9,
            AppDatabase.MIGRATION_9_10,
            AppDatabase.MIGRATION_10_11,
            AppDatabase.MIGRATION_11_12,
            AppDatabase.MIGRATION_12_13,
        )
        .build()

@Singleton
class OfflineStore internal constructor(
    private val db: AppDatabase,
) {
    @Inject
    constructor(@ApplicationContext context: Context) : this(buildOfflineDatabase(context, "vocabulario.db"))
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
    private val ownerDao = db.sessionOwnerDao()
    private val json = Json { ignoreUnknownKeys = true }

    /** Aktywny właściciel danych; null w każdej fazie przejściowej i po wylogowaniu. */
    suspend fun activeOwnerContext(): OwnerContext? =
        ownerDao.get()?.let { ownerContextOf(it.ownerUserId, it.generation, it.phase) }

    /**
     * Pod [OwnerScope] zapis przechodzi tylko dla tego samego właściciela i generacji, sprawdzonych
     * w tej samej transakcji co zapis; w przeciwnym razie [SupersededException] bez zmian.
     * Poza zakresem (akcje UI bieżącego właściciela) działa jak zwykły zapis.
     */
    suspend fun <T> guardedWrite(block: suspend () -> T): T {
        val scoped = currentCoroutineContext()[OwnerScope]?.owner ?: return block()
        return db.withTransaction {
            if (activeOwnerContext() != scoped) throw SupersededException()
            block()
        }
    }

    suspend fun applyPull(profileId: String, pull: SyncPullResponse, fullReplace: Boolean): Unit = guardedWrite {
        db.withTransaction {
            applyPullLocked(profileId, pull, fullReplace)
        }
    }

    /** Lokalna praca, której serwer jeszcze nie widział; pull nie może jej cofnąć ani wskrzesić usuniętego. */
    private class PullOverlay(
        val srsCards: Map<String, CachedCardEntity>,
        val movedCards: Map<String, CachedCardEntity>,
        val deletedCardIds: Set<String>,
        val deletedListIds: Set<String>,
        val renamedLists: Map<String, String>,
    )

    private suspend fun capturePullOverlay(): PullOverlay {
        val srsIds = reviewDao.all().map { it.cardId }.toMutableSet()
        undoDao.all().forEach { undo ->
            runCatching { json.decodeFromString(SyncSrsState.serializer(), undo.srsJson).card_id }
                .getOrNull()?.let { srsIds += it }
        }
        val moveIds = moveDao.all().map { it.cardId }.toSet()
        val deletedCards = mutableSetOf<String>()
        val deletedLists = mutableSetOf<String>()
        val renames = mutableMapOf<String, String>()
        for (op in outboxDao.all()) {
            val p = runCatching { json.parseToJsonElement(op.payloadJson) as? JsonObject }.getOrNull() ?: continue
            when (op.type) {
                "card_delete" -> p["cardId"].asContent()?.let { deletedCards += it }
                "list_delete" -> p["listId"].asContent()?.let { deletedLists += it }
                "list_rename" -> {
                    val id = p["listId"].asContent()
                    val name = p["name"].asContent()
                    if (id != null && name != null) renames[id] = name
                }
            }
        }
        suspend fun locals(ids: Collection<String>) =
            ids.mapNotNull { id -> cardDao.byId(id)?.let { id to it } }.toMap()
        return PullOverlay(locals(srsIds), locals(moveIds), deletedCards, deletedLists, renames)
    }

    private fun kotlinx.serialization.json.JsonElement?.asContent(): String? =
        (this as? kotlinx.serialization.json.JsonPrimitive)?.takeIf { it.isString }?.content

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
        val overlay = capturePullOverlay()
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
        val listEntities = pull.lists
            .filter { it.id !in overlay.deletedListIds }
            .map { item ->
                item.toEntity(profileId).let { entity ->
                    overlay.renamedLists[item.id]?.let { entity.copy(name = it) } ?: entity
                }
            }
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
        val entities = pull.cards
            .filter { it.id !in overlay.deletedCardIds && it.deck_id !in overlay.deletedListIds }
            .map { it.toEntity() }
        if (entities.isNotEmpty()) {
            cardDao.upsertAll(entities)
        }
        applyOverlayToCards(overlay)
        if (fullReplace && localOnlyLists.isNotEmpty()) {
            val present = listDao.forProfile(profileId).map { it.id }.toSet()
            val restore = localOnlyLists.filter { it.id !in present }
            if (restore.isNotEmpty()) listDao.upsertAll(restore)
        }
        val now = System.currentTimeMillis()
        val previous = syncMetaDao.get(profileId)
        syncMetaDao.upsert(
            (previous ?: SyncMetaEntity(profileId = profileId)).copy(
                lastPulledAt = pull.server_time,
                lastSyncedAt = now,
                cursor = pull.cursor,
            ),
        )
    }

    /** Stan serwera jako baza, lokalne nowsze oceny i ruchy odtworzone na wierzchu; usuniętej karty nie wskrzesza. */
    private suspend fun applyOverlayToCards(overlay: PullOverlay) {
        for ((id, local) in overlay.srsCards) {
            val pulled = cardDao.byId(id) ?: continue
            cardDao.update(pulled.withSrs(local.toSyncSrsState()).copy(updatedAt = pulled.updatedAt))
        }
        for ((id, local) in overlay.movedCards) {
            val pulled = cardDao.byId(id) ?: continue
            if (pulled.deckId != local.deckId) cardDao.update(pulled.copy(deckId = local.deckId))
        }
    }

    suspend fun lastPulledAt(profileId: String): String? =
        syncMetaDao.get(profileId)?.lastPulledAt

    suspend fun lastCompleteSyncAt(profileId: String): Long? =
        syncMetaDao.get(profileId)?.lastSuccessAt

    /** Każda zmiana kolejek (także status wiersza) daje nowy, spójny snapshot. */
    fun observeQueueSnapshot(): Flow<QueueSnapshot> =
        outboxDao.observeQueueTouch().map { queueSnapshot() }

    suspend fun pullCursor(profileId: String): String? =
        syncMetaDao.get(profileId)?.cursor

    /** Kursor odrzucony przez serwer (410/422): następny pull jest pełny, kolejki i overlaye zostają. */
    suspend fun resetPullCursor(profileId: String): Unit = guardedWrite {
        syncMetaDao.clearCursor(profileId)
    }

    suspend fun recordSyncAttempt(profileId: String, success: Boolean, error: String?): Unit = guardedWrite {
        val now = System.currentTimeMillis()
        val previous = syncMetaDao.get(profileId) ?: SyncMetaEntity(profileId = profileId)
        syncMetaDao.upsert(
            previous.copy(
                lastAttemptAt = now,
                lastSuccessAt = if (success) now else previous.lastSuccessAt,
                lastError = if (success) null else error,
            ),
        )
    }

    /** Spójny odczyt wszystkich kolejek wszystkich profili; operację liczymy raz. */
    suspend fun queueSnapshot(): QueueSnapshot = db.withTransaction {
        val reviews = reviewDao.all()
        val moves = moveDao.all()
        val undos = undoDao.all()
        val lookups = lookupDao.all()
        val ops = outboxDao.all()
        val (reports, rest) = ops.partition { it.type == OP_CONTENT_REPORT }
        QueueSnapshot(
            reviews = reviews.size,
            moves = moves.size,
            undos = undos.size,
            lookupsQueued = lookups.count { it.status != "needs_review" },
            lookupsNeedsReview = lookups.count { it.status == "needs_review" },
            outboxPending = rest.count { it.status == "pending" },
            outboxParked = rest.count { it.status == "parked" },
            outboxBlocked = rest.count { it.status == "blocked" },
            contentReports = reports.size,
            blockedReviews = reviews.count { it.blockedReason != null },
            blockedMoves = moves.count { it.blockedReason != null },
            blockedUndos = undos.count { it.blockedReason != null },
        )
    }

    /** Profile z niewysłaną pracą: stuby lookupów, karty ocen/ruchów i operacje outboxu z `profileId`. */
    suspend fun profilesWithPendingWork(): Set<String> = db.withTransaction {
        val ids = mutableSetOf<String>()
        lookupDao.all().forEach { ids += it.profileId }
        (reviewDao.all().map { it.cardId } + moveDao.all().map { it.cardId }).forEach { cardId ->
            cardDao.byId(cardId)?.let { ids += it.profileId }
        }
        for (op in outboxDao.all()) {
            val p = runCatching { json.parseToJsonElement(op.payloadJson) as? JsonObject }.getOrNull() ?: continue
            p["profileId"].asContent()?.let { ids += it }
        }
        ids
    }

    fun observeMembershipRows(profileId: String) = cardDao.observeMembershipRows(profileId)

    fun observeLastPulledAt(profileId: String) = syncMetaDao.observeLastPulledAt(profileId)

    suspend fun saveSettings(settings: UserSettingsResponse): Unit = guardedWrite {
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

    suspend fun cacheProfile(profile: LanguageProfileResponse): Unit = guardedWrite {
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

    suspend fun ownerSnapshot(): OwnerSnapshot = db.withTransaction { ownerSnapshotLocked() }

    /** Decyzja loginu i zapis zamiaru instalacji w jednej transakcji; inne decyzje niczego nie zmieniają. */
    suspend fun beginInstall(
        candidateUserId: String,
        transitionId: String,
        verifiedProfileIds: Set<String> = emptySet(),
    ): LoginDecision =
        db.withTransaction {
            val snapshot = ownerSnapshotLocked()
            val localProfileIds = if (verifiedProfileIds.isNotEmpty()) ownerDao.localProfileIds().toSet() else emptySet()
            val decision = decideLogin(snapshot, candidateUserId, localProfileIds, verifiedProfileIds)
            when (decision) {
                LoginDecision.Claim -> {
                    deleteOwnedDataLocked()
                    writeOwnerLocked(snapshot, candidateUserId, OwnerPhase.INSTALLING, transitionId)
                }
                LoginDecision.SameOwner ->
                    writeOwnerLocked(snapshot, candidateUserId, OwnerPhase.INSTALLING, transitionId)
                is LoginDecision.OtherAccount, is LoginDecision.LegacyQuarantine -> Unit
            }
            decision
        }

    /** Kończy przejście tylko wtedy, gdy w międzyczasie nie zaczęło się inne. */
    suspend fun completeInstall(transitionId: String): Boolean = db.withTransaction {
        val row = ownerDao.get()
        if (row?.transitionId != transitionId || row.phase != OwnerPhase.INSTALLING) return@withTransaction false
        ownerDao.upsert(row.copy(phase = OwnerPhase.ACTIVE, transitionId = null))
        true
    }

    /** Aktywna sesja przejmuje bazę tylko wtedy, gdy ta nadal nie zawiera danych. */
    suspend fun claimEmpty(ownerUserId: String): Boolean = db.withTransaction {
        val snapshot = ownerSnapshotLocked()
        if (snapshot.hasOwnedData) return@withTransaction false
        writeOwnerLocked(snapshot, ownerUserId, OwnerPhase.ACTIVE, null)
        true
    }

    /**
     * Bariera logoutu: końcowy odczyt kolejek i zapis zamiaru są jedną transakcją. Praca spoza
     * zgody przerywa logout bez zmian ([UnsentChangesException] z aktualnym snapshotem).
     */
    suspend fun beginLogout(transitionId: String, consent: LogoutConsent) {
        db.withTransaction {
            val snapshot = ownerSnapshotLocked()
            val covered = consentCovers(
                consent.disposition,
                consent.acceptedFingerprint,
                snapshot.unsentCount,
                snapshot.unsentFingerprint,
            )
            if (!covered) throw UnsentChangesException(snapshot.unsentCount, snapshot.unsentFingerprint)
            writeOwnerLocked(
                snapshot,
                snapshot.ownerUserId,
                OwnerPhase.LOGGING_OUT,
                transitionId,
                logoutDisposition = consent.disposition,
                acceptedUnsentFingerprint = consent.acceptedFingerprint,
            )
        }
    }

    /** Wycofanie zamiaru, gdy usunięcie sesji się nie powiodło; generacja nie wraca. */
    suspend fun abortLogout(transitionId: String): Boolean = db.withTransaction {
        val row = ownerDao.get() ?: return@withTransaction false
        if (row.transitionId != transitionId || row.phase != OwnerPhase.LOGGING_OUT) return@withTransaction false
        ownerDao.upsert(row.cancelledLogout())
        true
    }

    /**
     * Usuwa dane właściciela, ale nie rekord metadanych ani licznik generacji. Gdy w kolejkach
     * jest praca nieobjęta zapisaną zgodą, dane zostają (właściciel bez sesji) i zwraca false.
     */
    suspend fun completeLogout(): Boolean = db.withTransaction {
        val snapshot = ownerSnapshotLocked()
        if (snapshot.phase != OwnerPhase.LOGGING_OUT) return@withTransaction false
        if (!logoutCovered(snapshot)) {
            ownerDao.get()?.let { ownerDao.upsert(it.cancelledLogout()) }
            return@withTransaction false
        }
        deleteOwnedDataLocked()
        ownerDao.upsert(
            SessionOwnerEntity(
                ownerUserId = null,
                generation = snapshot.generation,
                phase = OwnerPhase.SIGNED_OUT,
                transitionId = null,
            ),
        )
        true
    }

    private fun SessionOwnerEntity.cancelledLogout() = copy(
        phase = OwnerPhase.ACTIVE,
        transitionId = null,
        logoutDisposition = null,
        acceptedUnsentFingerprint = null,
    )

    private suspend fun ownerSnapshotLocked(): OwnerSnapshot {
        val row = ownerDao.get() ?: SessionOwnerEntity()
        val unsentIds = ownerDao.unsentIds()
        return OwnerSnapshot(
            ownerUserId = row.ownerUserId,
            generation = row.generation,
            phase = row.phase,
            transitionId = row.transitionId,
            hasOwnedData = ownerDao.hasOwnedData(),
            unsentCount = unsentIds.size,
            unsentFingerprint = unsentFingerprint(unsentIds),
            logoutDisposition = row.logoutDisposition,
            acceptedUnsentFingerprint = row.acceptedUnsentFingerprint,
        )
    }

    private suspend fun writeOwnerLocked(
        snapshot: OwnerSnapshot,
        ownerUserId: String?,
        phase: String,
        transitionId: String?,
        logoutDisposition: String? = null,
        acceptedUnsentFingerprint: String? = null,
    ) {
        ownerDao.upsert(
            SessionOwnerEntity(
                ownerUserId = ownerUserId,
                generation = snapshot.generation + 1,
                phase = phase,
                transitionId = transitionId,
                logoutDisposition = logoutDisposition,
                acceptedUnsentFingerprint = acceptedUnsentFingerprint,
            ),
        )
    }

    private fun deleteOwnedDataLocked() {
        val sqlite = db.openHelper.writableDatabase
        AppDatabase.OWNED_TABLES.forEach { table -> sqlite.execSQL("DELETE FROM `$table`") }
    }

    suspend fun cardCount(profileId: String): Int = cardDao.countForProfile(profileId)

    suspend fun cardCountsByProfile(): Map<String, Int> =
        cachedProfiles().associate { it.id to cardDao.countForProfile(it.id) }

    suspend fun cachedProfiles(): List<LanguageProfileResponse> =
        profileDao.all().mapNotNull { entity ->
            runCatching {
                json.decodeFromString(LanguageProfileResponse.serializer(), entity.jsonBlob)
            }.getOrNull()
        }

    suspend fun cacheProfiles(profiles: List<LanguageProfileResponse>): Unit = guardedWrite {
        db.withTransaction {
            if (profiles.isEmpty()) {
                profileDao.deleteAll()
            } else {
                profileDao.deleteNotIn(profiles.map { it.id })
                profiles.forEach { cacheProfile(it) }
            }
        }
    }

    suspend fun buildDashboardStats(profileId: String, newLimit: Int, days: Int = 7, newDoneToday: Int = 0): DashboardStatsResponse =
        LocalDashboard.build(
            learningCards = cardDao.systemListCards(profileId),
            newLimit = newLimit,
            nowMs = System.currentTimeMillis(),
            periodDays = days,
            newDoneToday = newDoneToday,
        )

    /** Karty w nauce bez daty due — po hydracji listy / reinstalce, zanim sync wgra SRS. */
    suspend fun countStartedWithoutDue(profileId: String): Int =
        cardDao.systemListCards(profileId).count { card ->
            EnrichmentStatus.isStudyable(card.enrichmentStatus) &&
                card.status.isNotBlank() &&
                card.status != "new" &&
                card.nextReviewAt == null
        }

    /**
     * Karty z `deckId` = UUID listy systemowej są niewidoczne na „Uczę się”
     * (`systemListCards` = `deckId IS NULL`). Wcześniejszy zapis add tak robił.
     */
    suspend fun repairMisplacedSystemDeckIds(profileId: String) {
        val systemIds = listDao.forProfile(profileId)
            .filter { it.isSystem && !it.id.startsWith("local-") && !it.id.startsWith("local:") }
            .map { it.id }
        for (id in systemIds) {
            cardDao.clearDeckIdMatchingList(profileId, id)
        }
    }

    /**
     * Dopisuje karty bez kasowania reszty decku. [cacheCardsFromList] robi replace
     * i nie wolno go wołać z jedną kartą.
     *
     * [overwriteDeckId] = true zapisuje [deckId] nawet gdy jest null (lista systemowa).
     * Domyślnie null znaczy „zostaw dotychczasowy deck”, żeby poll enrichment
     * (GET karty bez `deck_id`) nie gubił listy.
     */
    suspend fun upsertCards(
        profileId: String,
        cards: List<CardResponse>,
        deckId: String? = null,
        overwriteDeckId: Boolean = false,
    ): Unit = guardedWrite {
        if (cards.isEmpty()) return@guardedWrite
        val entities = cards.map { card ->
            val existing = cardDao.byId(card.id)
            CachedCardEntity(
                id = card.id,
                profileId = profileId,
                deckId = if (overwriteDeckId) deckId else deckId ?: existing?.deckId,
                lemmaL2 = card.lemma_l2,
                glossPrimary = card.gloss_primary,
                pos = card.pos,
                contentJson = Json.encodeToString(JsonObject.serializer(), card.content),
                enrichmentStatus = card.enrichment_status,
                contentReviewStatus = card.content_review_status,
                cardActivityStatus = card.card_activity_status,
                hasContentChanges = card.has_content_changes,
                createdAt = card.created_at.ifBlank { existing?.createdAt },
                status = card.srs_status?.takeIf { it.isNotBlank() } ?: existing?.status ?: "new",
                nextReviewAt = card.srs_next_review_at?.toEpochMillis() ?: existing?.nextReviewAt,
                lastReviewedAt = card.srs_last_reviewed_at?.toEpochMillis() ?: existing?.lastReviewedAt,
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

    /** Sygnatura kart — id+deck+enrichment+activity+długość contentu (sekcje dociągane). */
    fun cardsSignature(profileId: String): Flow<String> =
        cardDao.observeForProfile(profileId).map { rows ->
            rows.sortedBy { it.id }.joinToString(";") {
                "${it.id}|${it.deckId.orEmpty()}|${it.enrichmentStatus}|${it.cardActivityStatus.orEmpty()}|${it.contentJson.length}"
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

    fun observeCardById(id: String): Flow<CardResponse?> =
        cardDao.observeById(id).map { it?.toCardResponse() }

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

    /**
     * Pełna synchronizacja list z odpowiedzi serwera — kasuje w Room wiersze usunięte na serwerze.
     * Tylko dla kompletnego GET /lists (sync pull, import refresh). Nigdy dla pojedynczej skrzynki.
     */
    suspend fun cacheLists(profileId: String, lists: List<WordListResponse>): Unit = guardedWrite {
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

    /** Aktualizuje / dopisuje wybrane listy bez kasowania pozostałych wierszy w Room. */
    suspend fun upsertLists(profileId: String, lists: List<WordListResponse>): Unit = guardedWrite {
        if (lists.isEmpty()) return@guardedWrite
        consolidatePendingInboxes(profileId)
        val stubCount = pendingLookupCount(profileId)
        val serverLists = lists.filter { !it.id.startsWith("local-pending-inbox-") }
        val entities = serverLists.map { list ->
            val entity = list.toEntity(profileId)
            if (list.is_pending_inbox) {
                entity.copy(wordCount = list.word_count + stubCount)
            } else {
                entity
            }
        }
        listDao.upsertAll(entities)
        if (serverLists.any { it.is_pending_inbox }) {
            listDao.forProfile(profileId)
                .filter { it.isPendingInbox && it.id.startsWith("local-pending-inbox-") }
                .forEach { listDao.deleteById(it.id) }
        }
    }

    /** UI zawsze czyta komplet list z Room — niezależnie od sieci / kolejki lookupów. */
    suspend fun completeLocalWordLists(profileId: String): List<WordListResponse> {
        consolidatePendingInboxes(profileId)
        ensureLocalSystemList(profileId)
        if (pendingLookupCount(profileId) > 0) {
            ensureLocalPendingInbox(profileId)
        }
        repairMisplacedSystemDeckIds(profileId)
        val all = listDao.forProfile(profileId)
            .filter { !it.pendingDelete }
            .map { it.toResponse() }
        val hasServerInbox = all.any { it.is_pending_inbox && !it.id.startsWith("local-pending-inbox-") }
        return all.filter { list ->
            !list.id.startsWith("local-pending-inbox-") || !hasServerInbox
        }
    }

    suspend fun ensureLocalSystemList(profileId: String): CachedListEntity {
        listDao.forProfile(profileId).firstOrNull { it.isSystem && !it.pendingDelete }?.let { return it }
        val entity = CachedListEntity(
            id = "local-system-learning",
            profileId = profileId,
            name = SYSTEM_LIST_NAME,
            isSystem = true,
            isPendingInbox = false,
            wordCount = 0,
            createdAt = Instant.now().toString(),
            updatedAt = System.currentTimeMillis(),
        )
        listDao.upsertAll(listOf(entity))
        return entity
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

    suspend fun localQueue(profileId: String, newLimit: Int, newDoneToday: Int = 0): List<CachedCardEntity> {
        val now = System.currentTimeMillis()
        val all = cardDao.learningCards(profileId)
        val due = all.filter { card ->
            LocalDashboard.isDue(card, now)
        }.sortedBy { it.nextReviewAt ?: 0L }
        val newCards = all.filter { it.status == "new" }
        val offered = LocalDashboard.newOffered(newLimit, newDoneToday, newCards.size)
        return due + newCards.take(offered)
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

    /** Ocena i jej trwały intent w jednej transakcji: śmierć procesu nie zostawia postępu bez kolejki ani odwrotnie. */
    suspend fun recordReviewLocally(review: PendingReviewEntity): CachedCardEntity? = db.withTransaction {
        val updated = applyReviewLocally(review.cardId, review.grade, review.correct, review.createdAt)
        reviewDao.insert(review)
        updated
    }

    suspend fun recordUndoLocally(clientId: String, srs: SyncSrsState): Unit = db.withTransaction {
        undoReviewLocally(clientId, srs)
        enqueuePendingUndo(clientId, srs)
    }

    suspend fun restoreCard(card: CachedCardEntity) {
        cardDao.update(card)
    }

    /**
     * Zastosowanie ACK push w jednej transakcji z kontrolą właściciela: zdejmuje tylko potwierdzone ID,
     * blokuje not_found/conflict, a serwerowy SRS nakłada wyłącznie na karty bez lokalnych niewysłanych
     * ocen/undo (nowsza lokalna ocena z lotu nie wraca do starego stanu).
     */
    suspend fun applyPushAck(
        confirmedReviews: List<String>,
        blockedReviews: Map<String, String>,
        confirmedMoves: List<String>,
        blockedMoves: Map<String, String>,
        srs: List<SyncSrsState>,
    ): Unit = guardedWrite {
        db.withTransaction {
            if (confirmedReviews.isNotEmpty()) reviewDao.deleteIds(confirmedReviews)
            blockedReviews.forEach { (id, reason) -> reviewDao.block(id, reason) }
            if (confirmedMoves.isNotEmpty()) moveDao.deleteIds(confirmedMoves)
            blockedMoves.forEach { (id, reason) -> moveDao.block(id, reason) }
            if (srs.isNotEmpty()) {
                val protectedIds = reviewDao.all().map { it.cardId }.toMutableSet()
                undoDao.all().forEach { undo ->
                    runCatching { json.decodeFromString(SyncSrsState.serializer(), undo.srsJson).card_id }
                        .getOrNull()?.let { protectedIds += it }
                }
                for (state in srs) {
                    if (state.card_id in protectedIds) continue
                    val card = cardDao.byId(state.card_id) ?: continue
                    cardDao.update(card.withSrs(state))
                }
            }
        }
    }

    suspend fun blockPendingUndo(clientId: String, reason: String): Unit = guardedWrite {
        undoDao.block(clientId, reason)
    }

    /**
     * Świadome „Odrzuć" zablokowanej operacji. Cursor profilu jest zerowany, więc następny pull
     * przywróci stan serwera dla odrzuconej lokalnej zmiany (z zachowaniem pozostałych overlayów).
     */
    suspend fun discardBlocked(kind: BlockedKind, id: String): Unit = guardedWrite {
        db.withTransaction {
            val profileIds = when (kind) {
                BlockedKind.REVIEW -> reviewDao.all().filter { it.clientId == id }
                    .mapNotNull { cardDao.byId(it.cardId)?.profileId }
                BlockedKind.MOVE -> moveDao.all().filter { it.clientId == id }
                    .mapNotNull { cardDao.byId(it.cardId)?.profileId }
                BlockedKind.UNDO -> undoDao.all().filter { it.clientId == id }
                    .mapNotNull { undo ->
                        runCatching { json.decodeFromString(SyncSrsState.serializer(), undo.srsJson).card_id }
                            .getOrNull()?.let { cardDao.byId(it)?.profileId }
                    }
                BlockedKind.OUTBOX -> emptyList()
            }
            when (kind) {
                BlockedKind.REVIEW -> reviewDao.delete(id)
                BlockedKind.MOVE -> moveDao.deleteIds(listOf(id))
                BlockedKind.UNDO -> undoDao.delete(id)
                BlockedKind.OUTBOX -> id.toLongOrNull()?.let { seq ->
                    outboxDao.bySeq(seq)?.let { op ->
                        profileOpView(op)?.payload?.profileId?.let { pid ->
                            outboxDao.deleteBySeq(seq)
                            cachedProfiles().firstOrNull { it.id == pid }?.let { cacheEffectiveProfile(it) }
                        } ?: outboxDao.deleteBySeq(seq)
                    }
                }
            }
            val resets = profileIds.ifEmpty { syncMetaDao.all().map { it.profileId } }
            resets.toSet().forEach { syncMetaDao.clearCursor(it) }
        }
    }

    suspend fun blockedItems(): List<BlockedItem> = db.withTransaction {
        buildList {
            reviewDao.all().filter { it.blockedReason != null }
                .forEach { add(BlockedItem(BlockedKind.REVIEW, it.clientId, it.blockedReason.orEmpty())) }
            moveDao.all().filter { it.blockedReason != null }
                .forEach { add(BlockedItem(BlockedKind.MOVE, it.clientId, it.blockedReason.orEmpty())) }
            undoDao.all().filter { it.blockedReason != null }
                .forEach { add(BlockedItem(BlockedKind.UNDO, it.clientId, it.blockedReason.orEmpty())) }
            outboxDao.all().filter { it.status == "blocked" }
                .forEach {
                    add(
                        BlockedItem(
                            BlockedKind.OUTBOX,
                            it.seq.toString(),
                            it.lastError.orEmpty(),
                            type = it.type,
                            profileId = outboxProfileId(it),
                        ),
                    )
                }
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

    /** Tylko niezablokowane wpisy; zablokowane czekają na decyzję użytkownika, nie na sieć. */
    suspend fun sendableReviews(): List<PendingReviewEntity> = reviewDao.sendable()

    suspend fun sendableMoves(): List<PendingMoveEntity> = moveDao.sendable()

    suspend fun sendableUndos(): List<PendingUndoEntity> = undoDao.sendable()

    suspend fun removePendingReviews(clientIds: List<String>): Unit = guardedWrite {
        if (clientIds.isNotEmpty()) reviewDao.deleteIds(clientIds)
    }

    suspend fun removePendingReview(clientId: String) {
        reviewDao.delete(clientId)
    }

    suspend fun pendingMoves(): List<PendingMoveEntity> = moveDao.all()

    suspend fun removePendingMoves(clientIds: List<String>): Unit = guardedWrite {
        if (clientIds.isNotEmpty()) moveDao.deleteIds(clientIds)
    }

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
    suspend fun markLookupNeedsReview(clientId: String, suggestionsJson: String?): Unit = guardedWrite {
        lookupDao.setStatus(clientId, "needs_review", suggestionsJson)
        lookupDao.byId(clientId)?.let { syncPendingInboxWordCount(it.profileId) }
    }

    suspend fun removePendingLookup(clientId: String): Unit = guardedWrite {
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

    suspend fun removePendingUndo(clientId: String): Unit = guardedWrite {
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

    /** Jedna aktualna kopia ustawień w outboxie — stare PATCH-e nie nadpiszą nowszego tapnięcia. */
    suspend fun replaceSettingsOp(payloadJson: String) {
        for (op in outboxDao.all()) {
            if (op.type == "settings_update") outboxDao.deleteBySeq(op.seq)
        }
        enqueueOp("settings_update", payloadJson)
    }

    suspend fun pendingOps(): List<OutboxOpEntity> = outboxDao.pending()

    suspend fun opByClientId(clientOpId: String): OutboxOpEntity? =
        outboxDao.all().firstOrNull { it.clientOpId == clientOpId }

    suspend fun removeOpByClientId(clientOpId: String): Unit = guardedWrite {
        outboxDao.deleteByClientOpId(clientOpId)
    }
    // ---- Profil: edycje i wybór pary jako trwałe intenty (F-003/T-004) ----

    private fun profileOpView(op: OutboxOpEntity): ProfileOpView? {
        if (op.type != OP_PROFILE_UPDATE) return null
        val payload = runCatching { json.decodeFromString(ProfileUpdatePayload.serializer(), op.payloadJson) }
            .getOrNull() ?: return null
        return ProfileOpView(op.seq, op.status, op.attempts, op.lastError, payload)
    }

    private suspend fun profileOps(profileId: String): List<ProfileOpView> =
        outboxDao.all().mapNotNull(::profileOpView).filter { it.payload.profileId == profileId }

    /** Widoczne wartości = potwierdzony snapshot + nakładka wszystkich niepotwierdzonych edycji. */
    suspend fun profileDrafts(): Map<String, ProfileFields> =
        outboxDao.all().mapNotNull(::profileOpView).groupBy { it.payload.profileId }
            .mapValues { overlayDrafts(it.value) }

    private suspend fun cacheEffectiveProfile(profile: LanguageProfileResponse) {
        val confirmed = profile.confirmed ?: ProfileFields.of(profile)
        val draft = overlayDrafts(profileOps(profile.id))
        cacheProfile(profile.copy(confirmed = confirmed).withFields(draft))
    }

    /**
     * Lokalna edycja: cache widocznych wartości i intent w jednej transakcji, bez sieci.
     * Brak zmian względem obecnych wartości nie tworzy intentu.
     */
    suspend fun editProfileLocally(profileId: String, requested: ProfileFields): LanguageProfileResponse =
        guardedWrite {
            db.withTransaction {
                val current = cachedProfiles().firstOrNull { it.id == profileId } ?: error("no_profile")
                val currentFields = ProfileFields.of(current)
                val changed = requested.changedAgainst(currentFields)
                if (changed.isEmpty) return@withTransaction current
                val prev = changed.valuesFrom(current.confirmed ?: currentFields)
                val existing = profileOps(profileId)
                when (val plan = planProfileEdit(profileId, changed, prev, current.revision, existing)) {
                    is ProfileEditPlan.Append -> enqueueOp(
                        OP_PROFILE_UPDATE,
                        json.encodeToString(ProfileUpdatePayload.serializer(), plan.payload),
                    )
                    is ProfileEditPlan.MergeInto -> outboxDao.bySeq(plan.seq)?.let { row ->
                        outboxDao.update(
                            row.copy(
                                clientOpId = UUID.randomUUID().toString(),
                                payloadJson = json.encodeToString(ProfileUpdatePayload.serializer(), plan.payload),
                                status = if (plan.newPending) "pending" else row.status,
                                attempts = if (plan.newPending) 0 else row.attempts,
                                lastError = if (plan.newPending) null else row.lastError,
                            ),
                        )
                    }
                }
                val shown = current.withFields(changed).copy(confirmed = current.confirmed ?: currentFields)
                cacheProfile(shown)
                shown
            }
        }

    /** Zaczyna wysyłkę: oznacza op jako wysłany i zwraca najświeższą treść (scalenia w locie nie giną). */
    suspend fun markProfileOpSending(seq: Long): OutboxOpEntity? = guardedWrite {
        db.withTransaction {
            val row = outboxDao.bySeq(seq) ?: return@withTransaction null
            if (row.status != "pending") return@withTransaction null
            val marked = if (row.lastError == null) row.copy(lastError = PROFILE_OP_SENT) else row
            if (marked !== row) outboxDao.update(marked)
            marked
        }
    }

    /** Wcześniejsza zablokowana lub zaparkowana edycja tego profilu wstrzymuje kolejne. */
    suspend fun hasEarlierUnresolvedProfileOp(seq: Long, profileId: String): Boolean =
        outboxDao.all().any { row ->
            row.seq < seq && row.status != "pending" && profileOpView(row)?.payload?.profileId == profileId
        }

    /**
     * ACK serwera. Op znika tylko, gdy wysłany `clientOpId` nadal jest aktualny; inaczej w międzyczasie
     * scalono nowszą edycję i zostaje do wysłania na nowej rewizji. Cache dostaje snapshot serwera
     * z nakładką pozostałych edycji, a lokalny wybór aktywnego profilu zostaje.
     */
    suspend fun confirmProfileUpdate(seq: Long, sentClientOpId: String, server: LanguageProfileResponse): Unit =
        guardedWrite {
            db.withTransaction {
                val row = outboxDao.bySeq(seq)
                val profileId = server.id
                if (row != null && row.clientOpId == sentClientOpId) outboxDao.deleteBySeq(seq)
                for (other in outboxDao.all()) {
                    val view = profileOpView(other) ?: continue
                    if (view.payload.profileId != profileId || other.status == "blocked") continue
                    val rebased = view.payload.copy(baseRevision = server.revision)
                    outboxDao.update(
                        other.copy(payloadJson = json.encodeToString(ProfileUpdatePayload.serializer(), rebased)),
                    )
                }
                val local = cachedProfiles().firstOrNull { it.id == profileId }
                cacheEffectiveProfile(
                    server.copy(
                        is_active = local?.is_active ?: server.is_active,
                        confirmed = ProfileFields.of(server),
                    ),
                )
            }
        }

    /** Przelicza widoczny profil po usunięciu/odrzuceniu edycji (np. „przyjmij serwer", „odrzuć"). */
    suspend fun rebuildProfileCache(profileId: String): Unit = guardedWrite {
        db.withTransaction {
            cachedProfiles().firstOrNull { it.id == profileId }?.let { cacheEffectiveProfile(it) }
        }
    }

    /** Kolejny wybór zastępuje jeszcze nie wysłany; wysłane zostają, ostatni wygrywa na serwerze. */
    suspend fun enqueueProfileActivate(profileId: String) {
        for (row in outboxDao.all()) {
            if (row.type == OP_PROFILE_ACTIVATE && row.status == "pending" && row.attempts == 0 && row.lastError == null) {
                outboxDao.deleteBySeq(row.seq)
            }
        }
        enqueueOp(OP_PROFILE_ACTIVATE, buildJsonObject { put("profileId", JsonPrimitive(profileId)) }.toString())
    }

    /** „Zastosuj moje zmiany" po konflikcie: nowa baza z serwera, nowy clientOpId, z powrotem do kolejki. */
    suspend fun reopenProfileOp(seq: Long, serverRevision: Long?): Boolean = guardedWrite {
        db.withTransaction {
            val row = outboxDao.bySeq(seq) ?: return@withTransaction false
            val view = profileOpView(row) ?: return@withTransaction false
            val payload = view.payload.copy(baseRevision = serverRevision)
            outboxDao.update(
                row.copy(
                    clientOpId = UUID.randomUUID().toString(),
                    payloadJson = json.encodeToString(ProfileUpdatePayload.serializer(), payload),
                    status = "pending",
                    attempts = 0,
                    lastError = null,
                ),
            )
            true
        }
    }

    private fun outboxProfileId(op: OutboxOpEntity): String? = runCatching {
        (json.parseToJsonElement(op.payloadJson) as? JsonObject)?.get("profileId").asContent()
    }.getOrNull()

    suspend fun outboxOp(seq: Long): OutboxOpEntity? = outboxDao.bySeq(seq)

    /** Lokalna zmiana i jej intent (outbox) zatwierdzane razem lub wcale. */
    suspend fun <T> atomically(block: suspend () -> T): T = db.withTransaction { block() }

    /** Operacja wymaga decyzji użytkownika: nie jest wysyłana ponownie ani uznawana za wykonaną. */
    suspend fun markOpBlocked(op: OutboxOpEntity, code: String): Unit = guardedWrite {
        // Świeży odczyt: scalenie profilu w trakcie wysyłki nie może zostać nadpisane starą kopią.
        db.withTransaction {
            val row = outboxDao.bySeq(op.seq) ?: return@withTransaction
            outboxDao.update(row.copy(status = "blocked", lastError = code))
        }
    }

    /**
     * Create listy został już wykonany i lista usunięta (receipt): zależne operacje i ruchy do lokalnego
     * ID dostają `target_unavailable`, a lokalny wiersz znika z kartami z powrotem na liście „Uczę się".
     */
    suspend fun blockDependentsOfLocalList(localId: String): Unit = guardedWrite {
        db.withTransaction {
            for (op in outboxDao.pending()) {
                if (op.payloadJson.contains(localId)) {
                    outboxDao.update(op.copy(status = "blocked", lastError = "target_unavailable"))
                }
            }
            moveDao.all().filter { it.targetListId == localId && it.blockedReason == null }
                .forEach { moveDao.block(it.clientId, "target_unavailable") }
            cardDao.cardsByDeckId(localId).forEach { cardDao.update(it.copy(deckId = null)) }
            listDao.deleteById(localId)
        }
    }

    /**
     * 401 na wygasłym tokenie parkowało settings_update i zmiana nigdy nie wylatywała.
     * Po udanym odświeżeniu sesji wracają do kolejki.
     */
    suspend fun unparkAuthFailures(): Unit = guardedWrite {
        for (op in outboxDao.all()) {
            if (op.status != "parked") continue
            val err = op.lastError.orEmpty()
            if (err.contains("401") || err.contains("Unauthorized", ignoreCase = true)) {
                outboxDao.update(op.copy(status = "pending", attempts = 0, lastError = null))
            }
        }
    }

    suspend fun removeOp(op: OutboxOpEntity): Unit = guardedWrite {
        outboxDao.deleteBySeq(op.seq)
    }

    /** Zwiększa licznik prób; parkuje po [MAX_OP_ATTEMPTS], żeby poison-pill nie blokował reszty. */
    suspend fun markOpFailed(op: OutboxOpEntity, error: String?): Unit = guardedWrite {
        db.withTransaction {
            val row = outboxDao.bySeq(op.seq) ?: return@withTransaction
            val attempts = row.attempts + 1
            outboxDao.update(
                row.copy(
                    attempts = attempts,
                    lastError = error,
                    status = if (attempts >= MAX_OP_ATTEMPTS) "parked" else "pending",
                ),
            )
        }
    }

    /** Remap ID listy lokalnej → server ID w cache, kartach, ruchach i payloadach operacji. */
    suspend fun remapLocalListId(localId: String, serverId: String): Unit = guardedWrite {
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
    ): Unit = guardedWrite {
        val newIds = cards.map { it.id }.toSet()
        // Lista systemowa (deckId == null): tylko upsert. Niepełny GET nie może
        // skasować kart, które Room już ma — to nie jest restore z serwera.
        if (deckId != null) {
            val existing = cardDao.cardsForDeck(profileId, deckId)
            val stale = existing.filter { it.id !in newIds && !it.id.startsWith("pending-lookup-") }
            if (stale.isNotEmpty()) {
                cardDao.deleteIds(stale.map { it.id })
            }
        }
        if (cards.isEmpty()) return@guardedWrite
        val entities = cards.map { card ->
            val existing = cardDao.byId(card.id)
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
                createdAt = card.created_at.ifBlank { existing?.createdAt },
                status = card.srs_status?.takeIf { it.isNotBlank() } ?: existing?.status ?: "",
                nextReviewAt = card.srs_next_review_at?.toEpochMillis() ?: existing?.nextReviewAt,
                lastReviewedAt = card.srs_last_reviewed_at?.toEpochMillis() ?: existing?.lastReviewedAt,
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
            createdAt = created_at,
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
        created_at = createdAt.orEmpty(),
        enrichment_status = enrichmentStatus,
        content_review_status = contentReviewStatus,
        card_activity_status = cardActivityStatus,
        has_content_changes = hasContentChanges,
        srs_status = status,
        srs_interval_days = intervalDays,
        srs_next_review_at = nextReviewAt?.let { Instant.ofEpochMilli(it).toString() },
        srs_last_reviewed_at = lastReviewedAt?.let { Instant.ofEpochMilli(it).toString() },
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

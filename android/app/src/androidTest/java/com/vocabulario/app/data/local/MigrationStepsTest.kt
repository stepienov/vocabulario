package com.vocabulario.app.data.local

import android.content.Context
import androidx.room.Room
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.vocabulario.app.data.local.db.AppDatabase
import com.vocabulario.app.data.local.db.CachedCardEntity
import com.vocabulario.app.data.local.db.CachedListEntity
import com.vocabulario.app.data.local.db.CachedProfileEntity
import com.vocabulario.app.data.local.db.OwnerPhase
import com.vocabulario.app.data.local.db.PendingReviewEntity
import com.vocabulario.app.data.local.db.SyncMetaEntity
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.SyncCardItem
import com.vocabulario.app.data.api.SyncPullResponse
import com.vocabulario.app.data.api.SyncSrsState
import com.vocabulario.app.data.api.UserSettingsResponse
import com.vocabulario.app.ui.home.HomeUiState
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.json.JSONObject

@RunWith(AndroidJUnit4::class)
class MigrationStepsTest {
    @Test
    fun roomOpensVersion13AndPreservesCardsAndUnsentWork() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val name = "migration-13-to-14-test.db"
        context.deleteDatabase(name)
        try {
            val schema = InstrumentationRegistry.getInstrumentation().context.assets
                .open("com.vocabulario.app.data.local.db.AppDatabase/13.json")
                .bufferedReader().use { JSONObject(it.readText()).getJSONObject("database") }
            val config = SupportSQLiteOpenHelper.Configuration.builder(context)
                .name(name)
                .callback(object : SupportSQLiteOpenHelper.Callback(13) {
                    override fun onCreate(db: SupportSQLiteDatabase) {
                        val entities = schema.getJSONArray("entities")
                        for (i in 0 until entities.length()) {
                            val entity = entities.getJSONObject(i)
                            val table = entity.getString("tableName")
                            db.execSQL(entity.getString("createSql").replace("\${TABLE_NAME}", table))
                            val indices = entity.getJSONArray("indices")
                            for (j in 0 until indices.length()) {
                                db.execSQL(
                                    indices.getJSONObject(j).getString("createSql")
                                        .replace("\${TABLE_NAME}", table),
                                )
                            }
                        }
                        val setup = schema.getJSONArray("setupQueries")
                        for (i in 0 until setup.length()) db.execSQL(setup.getString(i))
                        db.execSQL(
                            "INSERT INTO cached_cards " +
                                "(id, profileId, lemmaL2, contentJson, enrichmentStatus, status, " +
                                "intervalDays, ease, repetitions, lapses, hasContentChanges, updatedAt) " +
                                "VALUES ('card', 'profile', 'la parada', '{\"lemma\":\"la parada\"}', " +
                                "'ready', 'review', 2, 2.5, 2, 0, 0, 123)",
                        )
                        db.execSQL(
                            "INSERT INTO pending_reviews " +
                                "(clientId, cardId, grade, mode, direction, correct, createdAt) " +
                                "VALUES ('review', 'card', 'good', 'flashcard', 'l2_to_l1', 1, 123)",
                        )
                        db.execSQL(
                            "INSERT INTO outbox_ops " +
                                "(clientOpId, type, payloadJson, createdAt, attempts, status) " +
                                "VALUES ('move', 'move', 'unsent payload', 123, 0, 'pending')",
                        )
                    }

                    override fun onUpgrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
                })
                .build()
            FrameworkSQLiteOpenHelperFactory().create(config).use { it.writableDatabase }

            val db = Room.databaseBuilder(context, AppDatabase::class.java, name)
                .addMigrations(AppDatabase.MIGRATION_13_14)
                .build()
            try {
                val card = requireNotNull(db.cachedCardDao().byId("card"))
                assertEquals("{\"lemma\":\"la parada\"}", card.contentJson)
                assertEquals("review", card.status)
                assertEquals(2, card.repetitions)
                assertEquals(1L, card.learningGeneration)
                assertEquals(1L, db.pendingReviewDao().all().single().learningGeneration)
                assertEquals("unsent payload", db.outboxOpDao().pending().single().payloadJson)
            } finally {
                db.close()
            }
        } finally {
            context.deleteDatabase(name)
        }
    }

    @Test
    fun oldReviewAndUndoCannotOverwriteANewerContentGeneration() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
        try {
            val offline = OfflineStore(db)
            db.cachedCardDao().upsertAll(
                listOf(
                    CachedCardEntity(
                        id = "card", profileId = "profile", lemmaL2 = "la parada",
                        glossPrimary = "przystanek", pos = "noun", contentJson = "{}",
                        status = "new", nextReviewAt = null, learningGeneration = 2,
                    ),
                ),
            )
            val review = PendingReviewEntity(
                clientId = "old-review", cardId = "card", grade = "good", mode = "flashcard",
                direction = "l2_to_l1", correct = true, answer = null, createdAt = 1,
                learningGeneration = 1,
            )
            assertTrue(runCatching { offline.recordReviewLocally(review) }
                .exceptionOrNull() is CardContentChangedException)
            assertTrue(offline.pendingReviews().isEmpty())

            val oldSrs = SyncSrsState(
                card_id = "card", status = "review", repetitions = 4, learning_generation = 1,
            )
            offline.applyPushAck(emptyList(), emptyMap(), emptyList(), emptyMap(), listOf(oldSrs))
            assertEquals(2L, offline.cardSrsSnapshot("card")?.learning_generation)
            assertEquals("new", offline.cardSrsSnapshot("card")?.status)

            assertTrue(runCatching { offline.recordUndoLocally("old-review", oldSrs) }
                .exceptionOrNull() is CardContentChangedException)
            assertTrue(offline.pendingUndos().isEmpty())

            offline.recordReviewLocally(review.copy(clientId = "new-review", learningGeneration = 2))
            assertEquals(2L, offline.pendingReviews().single().learningGeneration)
        } finally {
            db.close()
        }
    }

    @Test
    fun newestUsesOriginalCreationDateAfterCacheAndSyncRefresh() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
        try {
            val offline = OfflineStore(db)
            val older = CardResponse(
                id = "older", lemma_l2 = "older", content = buildJsonObject {},
                created_at = "2026-01-01T10:00:00Z",
            )
            val newer = older.copy(id = "newer", lemma_l2 = "newer", created_at = "2026-01-02T10:00:00Z")
            offline.cacheCardsFromList("profile", listOf(newer, older), "list")
            offline.upsertCards("profile", listOf(older.copy(gloss_primary = "updated")))
            suspend fun assertNewest() {
                val cached = listOf("older", "newer").map {
                    requireNotNull(offline.observeCardById(it).first())
                }
                val state = HomeUiState(selectedListId = "list", listWords = cached)
                assertEquals(listOf("newer", "older"), state.visibleListWords.map { it.id })
                assertEquals(older.created_at, cached.first().created_at)
            }
            assertNewest()
            val pull = SyncPullResponse(
                server_time = "2026-01-04T10:00:00Z",
                settings = UserSettingsResponse("flip", "l2_to_l1", "normal", true, 10, "light"),
                cards = listOf(older, newer).map {
                    SyncCardItem(
                        id = it.id, profile_id = "profile", deck_id = "list",
                        lemma_l2 = it.lemma_l2, content = it.content, created_at = it.created_at,
                        updated_at = if (it.id == "older") "2026-01-04T10:00:00Z" else it.created_at,
                    )
                },
            )
            offline.applyPull("profile", pull, fullReplace = true)
            assertNewest()
            offline.applyPull("profile", pull.copy(cards = pull.cards.take(1)), fullReplace = false)
            assertNewest()
        } finally {
            db.close()
        }
    }

    @Test
    fun profileOwnershipCheckIncludesAllCachedProfileReferences() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
        try {
            db.cachedProfileDao().upsert(CachedProfileEntity("profile", "pl", "en"))
            db.cachedCardDao().upsertAll(
                listOf(
                    CachedCardEntity(
                        "card", "card-profile", lemmaL2 = "word", glossPrimary = null, pos = null,
                        contentJson = "{}", status = "new", nextReviewAt = null,
                    ),
                ),
            )
            db.cachedListDao().upsertAll(listOf(CachedListEntity("list", "list-profile", "list")))
            db.syncMetaDao().upsert(SyncMetaEntity("sync-profile"))

            assertEquals(
                setOf("profile", "card-profile", "list-profile", "sync-profile"),
                db.sessionOwnerDao().localProfileIds().toSet(),
            )
        } finally {
            db.close()
        }
    }

    @Test
    fun migrationStepsPreserveUnsentWorkAndQuarantineLegacyData() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val config = SupportSQLiteOpenHelper.Configuration.builder(context)
            .name(null)
            .callback(object : SupportSQLiteOpenHelper.Callback(1) {
                override fun onCreate(db: SupportSQLiteDatabase) {
                    db.execSQL(
                        "CREATE TABLE cached_cards (profileId TEXT, deckId TEXT, " +
                            "enrichmentStatus TEXT, status TEXT, nextReviewAt INTEGER)",
                    )
                    db.execSQL("CREATE TABLE cached_lists (profileId TEXT)")
                    for (table in listOf(
                        "pending_reviews", "pending_moves", "pending_lookups", "pending_undos",
                        "local_settings", "sync_meta", "cached_profile",
                    )) {
                        db.execSQL("CREATE TABLE `$table` (value TEXT)")
                    }
                    db.execSQL("INSERT INTO pending_moves VALUES ('unsent move')")
                    db.execSQL("INSERT INTO pending_reviews VALUES ('unsent review')")
                    db.execSQL("INSERT INTO cached_cards (profileId, status) VALUES ('profile', 'new')")
                }

                override fun onUpgrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
            })
            .build()
        FrameworkSQLiteOpenHelperFactory().create(config).use { helper ->
            val db = helper.writableDatabase
            AppDatabase.MIGRATION_6_7.migrate(db)
            db.execSQL(
                "INSERT INTO outbox_ops (clientOpId, type, payloadJson, createdAt, attempts, status) " +
                    "VALUES ('op', 'move', 'unsent payload', 1, 0, 'queued')",
            )
            AppDatabase.MIGRATION_7_8.migrate(db)
            AppDatabase.MIGRATION_8_9.migrate(db)
            AppDatabase.MIGRATION_9_10.migrate(db)
            AppDatabase.MIGRATION_10_11.migrate(db)
            AppDatabase.MIGRATION_11_12.migrate(db)
            db.execSQL("INSERT INTO sync_meta (value, cursor) VALUES ('preserved', 'old cursor')")
            AppDatabase.MIGRATION_12_13.migrate(db)
            AppDatabase.MIGRATION_13_14.migrate(db)

            db.query("SELECT phase FROM session_owner WHERE id = 0").use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals(OwnerPhase.LEGACY_UNCLAIMED, cursor.getString(0))
            }
            db.query("SELECT value, blockedReason FROM pending_moves").use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals("unsent move", cursor.getString(0))
                assertTrue(cursor.isNull(1))
            }
            db.query("SELECT payloadJson FROM outbox_ops").use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals("unsent payload", cursor.getString(0))
            }
            db.query("SELECT cursor, lastError FROM sync_meta LIMIT 0").close()
            db.query("SELECT value, cursor FROM sync_meta").use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals("preserved", cursor.getString(0))
                assertTrue(cursor.isNull(1))
            }
            db.query("SELECT createdAt FROM cached_cards LIMIT 0").close()
            db.query("SELECT value, learningGeneration FROM pending_reviews").use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals("unsent review", cursor.getString(0))
                assertEquals(1L, cursor.getLong(1))
            }
            db.query("SELECT learningGeneration FROM cached_cards").use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals(1L, cursor.getLong(0))
            }
            db.query("SELECT status, suggestionsJson FROM pending_lookups LIMIT 0").close()
        }
    }
}

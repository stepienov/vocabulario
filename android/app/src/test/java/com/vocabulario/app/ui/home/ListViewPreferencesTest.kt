package com.vocabulario.app.ui.home

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.SerializationException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ListViewPreferencesTest {
    @get:Rule val temporaryFolder = TemporaryFolder()

    @Test
    fun restoresEachListFromDiskWithoutOverwritingOtherLists() = runBlocking {
        val file = temporaryFolder.newFile("lists.preferences_pb")
        val firstJob = SupervisorJob()
        val secondJob = SupervisorJob()
        val a = ListViewPreferences(
            ListSortOrder.Oldest,
            ListFilterState(pos = setOf("noun"), states = setOf(CardStateFilter.Review)),
        )
        val b = ListViewPreferences(ListSortOrder.LemmaDesc, ListFilterState(pos = setOf("verb")))
        try {
            val first = ListViewPreferencesStore(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + firstJob), produceFile = { file },
            ))
            assertEquals(emptyMap<String, ListViewPreferences>(), first.readAll())
            first.save("a", a)
            first.save("b", b)
            first.save("a", a.copy(sort = ListSortOrder.Newest))
            firstJob.cancelAndJoin()

            val restored = ListViewPreferencesStore(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + secondJob), produceFile = { file },
            ))
            assertEquals(mapOf("a" to a.copy(sort = ListSortOrder.Newest), "b" to b), restored.readAll())
        } finally {
            firstJob.cancelAndJoin()
            secondJob.cancelAndJoin()
        }
    }

    @Test
    fun malformedPreferenceIsAnErrorInsteadOfResettingFilters() = runBlocking<Unit> {
        val job = SupervisorJob()
        try {
            val file = temporaryFolder.newFile("broken.preferences_pb")
            val store = PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + job),
                produceFile = { file },
            )
            store.edit { it[stringPreferencesKey("a")] = "{\"sort\":\"invalid\"}" }
            assertThrows(SerializationException::class.java) {
                runBlocking { ListViewPreferencesStore(store).readAll() }
            }
        } finally {
            job.cancelAndJoin()
        }
    }
}

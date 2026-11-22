package com.vocabulario.app.ui.home

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

private val Context.listViewDataStore by preferencesDataStore("list_view_preferences")

@Serializable
data class ListViewPreferences(
    val sort: ListSortOrder = ListSortOrder.Newest,
    val filter: ListFilterState = ListFilterState(),
)

@Singleton
class ListViewPreferencesStore internal constructor(
    private val dataStore: DataStore<Preferences>,
) {
    @Inject
    constructor(@ApplicationContext context: Context) : this(context.listViewDataStore)

    private val json = Json { ignoreUnknownKeys = true }

    suspend fun readAll(): Map<String, ListViewPreferences> =
        dataStore.data.first().let { preferences ->
            preferences.asMap().keys.associate { key ->
                key.name to json.decodeFromString<ListViewPreferences>(
                    requireNotNull(preferences[stringPreferencesKey(key.name)]),
                )
            }
        }

    suspend fun save(listId: String, preferences: ListViewPreferences) {
        dataStore.edit { it[stringPreferencesKey(listId)] = json.encodeToString(preferences) }
    }
}

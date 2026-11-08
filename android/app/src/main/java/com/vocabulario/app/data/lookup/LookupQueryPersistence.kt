package com.vocabulario.app.data.lookup

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

private val Context.lookupQueryDataStore by preferencesDataStore("lookup_query_prefs")

@Singleton
class LookupQueryPersistence @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val queryKey = stringPreferencesKey("active_lookup_query")
    private val byCategoryKey = booleanPreferencesKey("active_lookup_by_category")
    private val moreKey = booleanPreferencesKey("active_lookup_more")

    suspend fun loadQuery(): String? =
        context.lookupQueryDataStore.data.first()[queryKey]?.takeIf { it.isNotBlank() }

    suspend fun loadByCategory(): Boolean =
        context.lookupQueryDataStore.data.first()[byCategoryKey] == true

    suspend fun loadMore(): Boolean =
        context.lookupQueryDataStore.data.first()[moreKey] == true

    suspend fun saveQuery(query: String?, byCategory: Boolean = false, more: Boolean = false) {
        context.lookupQueryDataStore.edit { prefs ->
            if (query.isNullOrBlank()) {
                prefs.remove(queryKey)
                prefs.remove(byCategoryKey)
                prefs.remove(moreKey)
            } else {
                prefs[queryKey] = query
                prefs[byCategoryKey] = byCategory
                prefs[moreKey] = more
            }
        }
    }
}

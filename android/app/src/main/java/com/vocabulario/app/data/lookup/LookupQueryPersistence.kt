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

data class ActiveLookup(
    val query: String,
    val byCategory: Boolean,
    val more: Boolean,
    val operationId: String?,
)

@Singleton
class LookupQueryPersistence @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val queryKey = stringPreferencesKey("active_lookup_query")
    private val byCategoryKey = booleanPreferencesKey("active_lookup_by_category")
    private val moreKey = booleanPreferencesKey("active_lookup_more")
    private val operationIdKey = stringPreferencesKey("active_lookup_operation_id")

    suspend fun loadActive(): ActiveLookup? {
        val prefs = context.lookupQueryDataStore.data.first()
        val query = prefs[queryKey]?.takeIf { it.isNotBlank() } ?: return null
        return ActiveLookup(query, prefs[byCategoryKey] == true, prefs[moreKey] == true, prefs[operationIdKey])
    }

    suspend fun loadQuery(): String? =
        context.lookupQueryDataStore.data.first()[queryKey]?.takeIf { it.isNotBlank() }

    suspend fun loadByCategory(): Boolean =
        context.lookupQueryDataStore.data.first()[byCategoryKey] == true

    suspend fun loadMore(): Boolean =
        context.lookupQueryDataStore.data.first()[moreKey] == true

    suspend fun saveQuery(
        query: String?,
        byCategory: Boolean = false,
        more: Boolean = false,
        operationId: String? = null,
    ) {
        context.lookupQueryDataStore.edit { prefs ->
            if (query.isNullOrBlank()) {
                prefs.remove(queryKey)
                prefs.remove(byCategoryKey)
                prefs.remove(moreKey)
                prefs.remove(operationIdKey)
            } else {
                prefs[queryKey] = query
                prefs[byCategoryKey] = byCategory
                prefs[moreKey] = more
                if (operationId == null) prefs.remove(operationIdKey)
                else prefs[operationIdKey] = operationId
            }
        }
    }

    /** Czyści zapis tylko gdy aktualny wpis należy do tej ścieżki (normal / category). */
    suspend fun clearIfByCategory(byCategory: Boolean) {
        context.lookupQueryDataStore.edit { prefs ->
            val currentIsCategory = prefs[byCategoryKey] == true
            if (currentIsCategory != byCategory) return@edit
            prefs.remove(queryKey)
            prefs.remove(byCategoryKey)
            prefs.remove(moreKey)
            prefs.remove(operationIdKey)
        }
    }
}

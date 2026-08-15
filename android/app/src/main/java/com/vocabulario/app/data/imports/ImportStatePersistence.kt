package com.vocabulario.app.data.imports

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

private val Context.importJobDataStore by preferencesDataStore("import_job_prefs")

@Singleton
class ImportStatePersistence @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val snapshotKey = stringPreferencesKey("import_job_snapshot")

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    suspend fun load(): ImportJobState? {
        val raw = context.importJobDataStore.data.first()[snapshotKey] ?: return null
        return runCatching { json.decodeFromString<ImportJobState>(raw) }.getOrNull()
            ?.copy(showAbortConfirm = false)
    }

    suspend fun save(state: ImportJobState) {
        val toStore = state.copy(showAbortConfirm = false)
        if (toStore.status == ImportStatus.Idle) {
            clear()
            return
        }
        context.importJobDataStore.edit { prefs ->
            prefs[snapshotKey] = json.encodeToString(toStore)
        }
    }

    suspend fun clear() {
        context.importJobDataStore.edit { it.remove(snapshotKey) }
    }
}

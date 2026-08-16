package com.vocabulario.app.data.imports

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

private val Context.importJobDataStore by preferencesDataStore("import_job_prefs")

@Singleton
class ImportStatePersistence @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val jobIdKey = stringPreferencesKey("import_job_id")

    suspend fun loadJobId(): String? =
        context.importJobDataStore.data.first()[jobIdKey]?.takeIf { it.isNotBlank() }

    suspend fun saveJobId(jobId: String?) {
        context.importJobDataStore.edit { prefs ->
            if (jobId.isNullOrBlank()) {
                prefs.remove(jobIdKey)
            } else {
                prefs[jobIdKey] = jobId
            }
        }
    }
}

package com.vocabulario.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import java.util.Calendar
import javax.inject.Inject
import javax.inject.Singleton

private val Context.newDailyStore by preferencesDataStore("vocabulario_new_daily")

/** Dzienny licznik wprowadzonych nowych kart (limit dotyczy tylko new, nie powtórek). */
@Singleton
class DailyNewCounter @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    suspend fun get(profileId: String, nowMs: Long = System.currentTimeMillis()): Int {
        val key = intPreferencesKey(prefKey(profileId, nowMs))
        return context.newDailyStore.data.first()[key] ?: 0
    }

    suspend fun increment(profileId: String, nowMs: Long = System.currentTimeMillis()) {
        val key = intPreferencesKey(prefKey(profileId, nowMs))
        context.newDailyStore.edit { prefs ->
            prefs[key] = (prefs[key] ?: 0) + 1
        }
    }

    suspend fun decrement(profileId: String, nowMs: Long = System.currentTimeMillis()) {
        val key = intPreferencesKey(prefKey(profileId, nowMs))
        context.newDailyStore.edit { prefs ->
            prefs[key] = ((prefs[key] ?: 0) - 1).coerceAtLeast(0)
        }
    }

    companion object {
        fun localDateKey(nowMs: Long): String {
            val cal = Calendar.getInstance()
            cal.timeInMillis = nowMs
            return "%04d-%02d-%02d".format(
                cal.get(Calendar.YEAR),
                cal.get(Calendar.MONTH) + 1,
                cal.get(Calendar.DAY_OF_MONTH),
            )
        }

        fun prefKey(profileId: String, nowMs: Long): String =
            "new_done_${profileId}_${localDateKey(nowMs)}"
    }
}

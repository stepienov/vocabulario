package com.vocabulario.app.notifications

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ReadyBatchTracker @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun watchImport(ids: Collection<String>) = merge(KEY_IMPORT, ids)

    fun watchOffline(ids: Collection<String>) = merge(KEY_OFFLINE, ids)

    fun hasWatches(): Boolean = load(KEY_IMPORT).isNotEmpty() || load(KEY_OFFLINE).isNotEmpty()

    fun evaluate(statusById: Map<String, String>, notificationsOn: Boolean) {
        finish(KEY_IMPORT, statusById, notificationsOn) { count ->
            NotificationHelper.showImportReady(context, count)
        }
        finish(KEY_OFFLINE, statusById, notificationsOn) { count ->
            NotificationHelper.showOfflineReady(context, count)
        }
    }

    private fun finish(
        key: String,
        statusById: Map<String, String>,
        notificationsOn: Boolean,
        notify: (Int) -> Unit,
    ) {
        val watched = load(key)
        if (!batchComplete(watched, statusById)) return
        val count = readyCount(watched, statusById)
        clear(key)
        if (notificationsOn && count > 0) notify(count)
    }

    private fun merge(key: String, ids: Collection<String>) {
        val next = load(key) + ids.map { it.trim() }.filter { it.isNotEmpty() }
        prefs.edit().putStringSet(key, next).apply()
    }

    private fun load(key: String): Set<String> =
        prefs.getStringSet(key, emptySet())?.toSet().orEmpty()

    private fun clear(key: String) {
        prefs.edit().remove(key).apply()
    }

    companion object {
        private const val PREFS = "vocabulario_ready_batches"
        private const val KEY_IMPORT = "import_ids"
        private const val KEY_OFFLINE = "offline_ids"
    }
}

internal fun isBusyStatus(status: String?): Boolean {
    val s = status?.trim()?.lowercase().orEmpty()
    return s == "pending" || s == "awaiting_network"
}

internal fun batchComplete(watched: Set<String>, statusById: Map<String, String>): Boolean {
    if (watched.isEmpty()) return false
    return watched.all { id ->
        val status = statusById[id]
        status != null && !isBusyStatus(status)
    }
}

internal fun readyCount(watched: Set<String>, statusById: Map<String, String>): Int =
    watched.count { statusById[it]?.equals("ready", ignoreCase = true) == true }

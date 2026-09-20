package com.vocabulario.app.data.lookup

import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.sync.BackgroundJobScheduler
import com.vocabulario.app.i18n.UiStrings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Osobny flow „szukaj w kategorii" — nie dzieli jobów ze zwykłym lookupiem.
 */
@Singleton
class CategoryLookupCoordinator @Inject constructor(
    repository: LearningRepository,
    strings: UiStrings,
    private val persistence: LookupQueryPersistence,
    private val backgroundJobs: BackgroundJobScheduler,
) {
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val session = LookupSession(
        lookupCached = { repository.lookupCategoryCached(it) },
        lookupExpand = { repository.lookupCategoryExpand(it) },
        mapSearchError = { it.userMessage(strings, R.string.err_search) },
        expandFailedNotice = strings.get(R.string.err_lookup_expand),
        parent = appScope,
        onActiveQuery = { query ->
            appScope.launch { persistence.saveQuery(query, byCategory = true) }
        },
    )

    val state: StateFlow<LookupSessionState> get() = session.state

    init {
        appScope.launch {
            val stored = persistence.loadQuery() ?: return@launch
            if (!persistence.loadByCategory()) return@launch
            if (stored.isNotBlank() && state.value.query.isBlank()) {
                session.start(stored)
            }
        }
    }

    fun start(query: String) {
        session.start(query)
        appScope.launch {
            persistence.saveQuery(query.trim(), byCategory = true)
            backgroundJobs.enqueueLookup(replace = true)
        }
    }

    fun clear() {
        session.clear()
        backgroundJobs.cancelLookup()
    }

    fun acceptServerResult(query: String, response: LookupResponse) =
        session.acceptServerResult(query, response)

    fun retryPending() {
        val current = session.state.value
        if (current.expanding || current.query.isNotBlank()) {
            session.refreshFromCache()
        }
        if (current.expanding) return
        if (current.error != null && current.query.isNotBlank()) {
            start(current.query)
            return
        }
        appScope.launch {
            if (!persistence.loadByCategory()) return@launch
            val stored = persistence.loadQuery() ?: return@launch
            val now = session.state.value
            if (now.expanding) {
                now.query.takeIf { it.isNotBlank() }?.let { session.refreshFromCache() }
                return@launch
            }
            if (now.candidates.isNotEmpty() && now.error == null) {
                persistence.saveQuery(null)
                return@launch
            }
            start(stored)
        }
    }
}

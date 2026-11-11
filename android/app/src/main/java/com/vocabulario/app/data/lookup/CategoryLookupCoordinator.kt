package com.vocabulario.app.data.lookup

import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.i18n.UiStrings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Szukanie skojarzeń: słowo i ósemka naraz, potem dwie kolejne ósemki.
 */
@Singleton
class CategoryLookupCoordinator @Inject constructor(
    repository: LearningRepository,
    strings: UiStrings,
    private val persistence: LookupQueryPersistence,
) {
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val session = AssociationSession(
        lookupWord = { repository.lookupCategoryCached(it) },
        lookupRound = { text, round -> repository.lookupCategoryExpand(text, round) },
        mapError = { it.userMessage(strings, R.string.err_lookup_expand) },
        parent = appScope,
    )

    val state: StateFlow<AssociationState> get() = session.state

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
        appScope.launch { persistence.saveQuery(query.trim(), byCategory = true) }
    }

    fun more() = session.more()

    fun clear() {
        session.clear()
        appScope.launch { persistence.saveQuery(null, byCategory = false) }
    }

    fun retryPending() = session.retryPending()
}

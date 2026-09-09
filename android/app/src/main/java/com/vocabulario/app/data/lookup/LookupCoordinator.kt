package com.vocabulario.app.data.lookup

import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.i18n.UiStrings
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

data class LookupSessionState(
    val generation: Long = 0,
    val query: String = "",
    val candidates: List<LookupCandidate> = emptyList(),
    val expanding: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
) {
    val hasResultsOrProgress: Boolean
        get() = expanding || candidates.isNotEmpty() || error != null
}

/**
 * Lookup żyje w scope aplikacji, nie ViewModelu — minimalizacja, inna apka
 * albo zgaszony ekran nie anulują drogiego /lookup/expand.
 */
@Singleton
class LookupCoordinator @Inject constructor(
    repository: LearningRepository,
    strings: UiStrings,
) {
    private val session = LookupSession(
        lookupCached = { repository.lookupCached(it) },
        lookupExpand = { repository.lookupExpand(it) },
        mapSearchError = { it.userMessage(strings, R.string.err_search) },
        expandFailedNotice = strings.get(R.string.err_lookup_expand),
        parent = CoroutineScope(SupervisorJob() + Dispatchers.IO),
    )

    val state: StateFlow<LookupSessionState> get() = session.state

    fun start(query: String) = session.start(query)

    fun clear() = session.clear()
}

internal class LookupSession(
    private val lookupCached: suspend (String) -> LookupResponse,
    private val lookupExpand: suspend (String) -> LookupResponse,
    private val mapSearchError: (Throwable) -> String,
    private val expandFailedNotice: String,
    parent: CoroutineScope,
    private val ioRetryDelayMs: Long = 1_500L,
) {
    private val scope = CoroutineScope(parent.coroutineContext + SupervisorJob())
    private val _state = MutableStateFlow(LookupSessionState())
    val state: StateFlow<LookupSessionState> = _state.asStateFlow()
    private var job: Job? = null

    fun start(query: String) {
        val text = query.trim()
        if (text.isBlank()) return
        val gen = _state.value.generation + 1
        job?.cancel()
        _state.value = LookupSessionState(
            generation = gen,
            query = text,
            expanding = true,
        )
        job = scope.launch {
            try {
                runLookup(text, gen)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                publish(gen) {
                    it.copy(
                        expanding = false,
                        error = if (it.candidates.isEmpty()) mapSearchError(e) else null,
                        notice = if (it.candidates.isNotEmpty()) expandFailedNotice else null,
                    )
                }
            }
        }
    }

    fun clear() {
        job?.cancel()
        job = null
        _state.value = LookupSessionState(generation = _state.value.generation + 1)
    }

    private suspend fun runLookup(text: String, gen: Long) {
        val cached = try {
            withIoRetry { lookupCached(text) }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
        if (!stillCurrent(gen)) return
        if (cached != null) {
            if (cached.candidates.isNotEmpty()) {
                publish(gen) {
                    it.copy(
                        candidates = cached.candidates,
                        expanding = false,
                    )
                }
                return
            }
            if (cached.ai_complete) {
                publish(gen) { it.copy(expanding = false) }
                return
            }
        }

        val expanded = withIoRetry { lookupExpand(text) }
        if (!stillCurrent(gen)) return
        publish(gen) {
            it.copy(
                candidates = expanded.candidates,
                expanding = false,
                error = null,
                notice = null,
            )
        }
    }

    private suspend fun <T> withIoRetry(block: suspend () -> T): T {
        return try {
            block()
        } catch (e: CancellationException) {
            throw e
        } catch (e: IOException) {
            if (ioRetryDelayMs > 0) delay(ioRetryDelayMs)
            block()
        }
    }

    private fun stillCurrent(gen: Long): Boolean = _state.value.generation == gen

    private fun publish(gen: Long, update: (LookupSessionState) -> LookupSessionState) {
        val current = _state.value
        if (current.generation != gen) return
        _state.value = update(current)
    }
}

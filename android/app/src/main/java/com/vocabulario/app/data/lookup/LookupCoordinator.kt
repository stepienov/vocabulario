package com.vocabulario.app.data.lookup

import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.sync.BackgroundJobScheduler
import com.vocabulario.app.i18n.UiStrings
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.coroutineScope
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
    val loadingMore: Boolean = false,
    val suggestionsExhausted: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
) {
    val hasResultsOrProgress: Boolean
        get() = expanding || loadingMore || candidates.isNotEmpty() || error != null || notice != null
}

/**
 * Lookup żyje w scope aplikacji, nie ViewModelu — minimalizacja nie anuluje joba.
 *
 * Sam app-scope nie wystarcza: Android zamraża proces w tle, więc długi POST
 * `/lookup/expand` wisi aż do powrotu. Serwer i tak kończy LLM (lookup_jobs).
 * Źródłem prawdy po freeze jest `/lookup/cached` + WorkManager, nie ten socket.
 */
@Singleton
class LookupCoordinator @Inject constructor(
    repository: LearningRepository,
    strings: UiStrings,
    private val persistence: LookupQueryPersistence,
    private val backgroundJobs: BackgroundJobScheduler,
) {
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val session = LookupSession(
        lookupCached = { repository.lookupCached(it) },
        lookupExpand = { text, more -> repository.lookupExpand(text, more) },
        mapSearchError = { it.userMessage(strings, R.string.err_search) },
        expandFailedNotice = strings.get(R.string.err_lookup_expand),
        longerAnalysisNotice = { strings.get(R.string.lookup_longer_analysis, it) },
        nothingFoundNotice = { strings.get(R.string.lookup_nothing_found, it) },
        parent = appScope,
        singleRequest = true,
        onActiveQuery = { query, more -> appScope.launch { persistence.saveQuery(query, more = more) } },
    )

    val state: StateFlow<LookupSessionState> get() = session.state

    init {
        appScope.launch {
            val stored = persistence.loadQuery() ?: return@launch
            if (persistence.loadByCategory()) return@launch
            if (stored.isNotBlank() && state.value.query.isBlank()) {
                session.start(stored)
            }
        }
    }

    fun start(query: String) {
        session.start(query)
        appScope.launch {
            persistence.saveQuery(query.trim())
            backgroundJobs.cancelLookup()
        }
    }

    fun showMore() = session.showMore()

    fun clear() {
        session.clear()
        backgroundJobs.cancelLookup()
    }

    fun acceptServerResult(query: String, response: LookupResponse) =
        session.acceptServerResult(query, response)

    /**
     * Po powrocie do apki: nie czekaj na zamrożony expand HTTP.
     * Od razu czytamy cache — serwer mógł skończyć kilka minut temu.
     */
    fun retryPending() {
        val current = session.state.value
        if (current.expanding || current.loadingMore) {
            session.refreshFromCache()
        }
        if (current.expanding || current.loadingMore) return
        if (current.error != null && current.query.isNotBlank()) {
            start(current.query)
            return
        }
        appScope.launch {
            if (persistence.loadByCategory()) return@launch
            val stored = persistence.loadQuery() ?: return@launch
            val now = session.state.value
            if (now.expanding || now.loadingMore) {
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

internal class LookupSession(
    private val lookupCached: suspend (String) -> LookupResponse,
    private val lookupExpand: suspend (String, Boolean) -> LookupResponse,
    private val mapSearchError: (Throwable) -> String,
    private val expandFailedNotice: String,
    parent: CoroutineScope,
    private val longerAnalysisNotice: (String) -> String = { "" },
    private val nothingFoundNotice: (String) -> String = { "" },
    private val singleRequest: Boolean = false,
    private val ioRetryDelayMs: Long = 1_500L,
    private val cachedPollDelayMs: Long = 2_000L,
    private val cachedPollAttempts: Int = 90,
    private val onActiveQuery: (String?, Boolean) -> Unit = { _, _ -> },
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
        onActiveQuery(text, false)
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
        onActiveQuery(null, false)
        _state.value = LookupSessionState(generation = _state.value.generation + 1)
    }

    fun showMore() {
        val current = _state.value
        val text = current.query
        if (text.isBlank() || current.candidates.isEmpty()) return
        val gen = current.generation
        job?.cancel()
        onActiveQuery(text, true)
        _state.value = current.copy(loadingMore = true, notice = null)
        job = scope.launch {
            try {
                val response = withIoRetry { lookupExpand(text, true) }
                if (!stillCurrent(gen)) return@launch
                publish(gen) {
                    if (response.added == 0) {
                        it.copy(
                            loadingMore = false,
                            suggestionsExhausted = true,
                            notice = null,
                        )
                    } else {
                        it.copy(
                            loadingMore = false,
                            suggestionsExhausted = false,
                            candidates = mergeShownCandidates(it.candidates, response.candidates),
                            notice = null,
                        )
                    }
                }
                finishActive(gen)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                publish(gen) { it.copy(loadingMore = false, notice = expandFailedNotice) }
                finishActive(gen)
            }
        }
    }

    /** Nie restartuje joba — dokłada wynik z cache do aktualnej generacji. */
    fun refreshFromCache() {
        val snapshot = _state.value
        val text = snapshot.query
        if (text.isBlank()) return
        val gen = snapshot.generation
        scope.launch {
            val cached = try {
                lookupCached(text)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                return@launch
            }
            if (applyCachedOutcome(cached, gen) && snapshot.expanding) {
                job?.cancel()
                job = null
            }
        }
    }

    fun acceptServerResult(query: String, response: LookupResponse) {
        val text = query.trim()
        if (text.isBlank()) return
        val current = _state.value
        if (current.query.isNotBlank() && current.query != text) return
        val gen = if (current.query == text && current.generation > 0) {
            current.generation
        } else {
            val next = current.generation + 1
            _state.value = LookupSessionState(
                generation = next,
                query = text,
                expanding = !response.ai_complete,
            )
            next
        }
        if (applyCachedOutcome(response, gen)) {
            job?.cancel()
            job = null
        }
    }

    private suspend fun runLookup(text: String, gen: Long) {
        if (singleRequest) {
            runSingleLookup(text, gen)
            return
        }
        val cached = try {
            withIoRetry { lookupCached(text) }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
        if (!stillCurrent(gen)) return
        if (cached != null && applyCachedOutcome(cached, gen)) return

        coroutineScope {
            val expandJob = launch {
                try {
                    val expanded = withIoRetry { lookupExpand(text, false) }
                    if (!stillCurrent(gen)) return@launch
                    publish(gen) {
                        it.copy(
                            candidates = expanded.candidates.ifEmpty { it.candidates },
                            expanding = false,
                            error = null,
                            notice = null,
                        )
                    }
                    finishActive(gen)
                } catch (e: CancellationException) {
                    throw e
                } catch (_: IOException) {
                    // poll poniżej / równoległy cached
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
            val pollJob = launch {
                while (stillCurrent(gen) && _state.value.expanding && expandJob.isActive) {
                    delay(cachedPollDelayMs.coerceAtLeast(1L))
                    if (!stillCurrent(gen) || !_state.value.expanding) return@launch
                    val polled = try {
                        lookupCached(text)
                    } catch (e: CancellationException) {
                        throw e
                    } catch (_: Exception) {
                        null
                    } ?: continue
                    if (applyCachedOutcome(polled, gen)) {
                        expandJob.cancel()
                        return@launch
                    }
                }
            }
            expandJob.join()
            if (!stillCurrent(gen)) {
                pollJob.cancel()
                return@coroutineScope
            }
            if (_state.value.expanding && expandJob.isCancelled) {
                pollJob.cancel()
                return@coroutineScope
            }
            if (_state.value.expanding) {
                if (!pollCachedUntilReady(text, gen)) {
                    publish(gen) {
                        it.copy(
                            expanding = false,
                            error = if (it.candidates.isEmpty()) {
                                mapSearchError(IOException("lookup expand failed"))
                            } else {
                                null
                            },
                            notice = if (it.candidates.isNotEmpty()) expandFailedNotice else null,
                        )
                    }
                }
            }
            pollJob.cancel()
        }
    }

    private suspend fun pollCachedUntilReady(text: String, gen: Long): Boolean {
        repeat(cachedPollAttempts) {
            if (cachedPollDelayMs > 0) delay(cachedPollDelayMs) else delay(1L)
            if (!stillCurrent(gen)) return true
            val cached = try {
                lookupCached(text)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                null
            } ?: return@repeat
            if (applyCachedOutcome(cached, gen)) return true
        }
        return false
    }

    private fun applyCachedOutcome(cached: LookupResponse, gen: Long): Boolean {
        if (!stillCurrent(gen)) return true
        return if (cached.candidates.isNotEmpty()) {
            publish(gen) {
                it.copy(
                    candidates = cached.candidates,
                    expanding = !cached.ai_complete,
                    error = null,
                )
            }
            if (cached.ai_complete) {
                finishActive(gen)
                true
            } else {
                false
            }
        } else if (cached.ai_complete) {
            publish(gen) { it.copy(expanding = false, error = null) }
            finishActive(gen)
            true
        } else {
            false
        }
    }

    private fun finishActive(gen: Long) {
        if (!stillCurrent(gen)) return
        onActiveQuery(null, false)
    }

    private suspend fun runSingleLookup(text: String, gen: Long) {
        val cached = try {
            withIoRetry { lookupCached(text) }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
        if (!stillCurrent(gen)) return
        if (cached != null && cached.candidates.isNotEmpty()) {
            publish(gen) {
                it.copy(
                    candidates = cached.candidates,
                    expanding = false,
                    error = null,
                    notice = null,
                    suggestionsExhausted = cached.suggestions_exhausted,
                )
            }
            finishActive(gen)
            return
        }
        if (cached != null && cached.ai_complete) {
            publish(gen) {
                it.copy(
                    expanding = false,
                    error = null,
                    notice = nothingFoundNotice(text).ifBlank { null },
                )
            }
            finishActive(gen)
            return
        }
        if (cached == null) {
            publish(gen) {
                it.copy(expanding = false, error = mapSearchError(IOException("lookup cached failed")))
            }
            return
        }
        val longer = longerAnalysisNotice(text).ifBlank { null }
        if (longer != null) {
            publish(gen) { it.copy(expanding = true, notice = longer, error = null) }
        }
        try {
            val expanded = withIoRetry { lookupExpand(text, false) }
            if (!stillCurrent(gen)) return
            val found = expanded.candidates.ifEmpty { emptyList() }
            publish(gen) {
                it.copy(
                    candidates = found.ifEmpty { it.candidates },
                    expanding = false,
                    error = null,
                    suggestionsExhausted = expanded.suggestions_exhausted,
                    notice = if (found.isEmpty() && it.candidates.isEmpty()) {
                        nothingFoundNotice(text).ifBlank { null }
                    } else {
                        null
                    },
                )
            }
            finishActive(gen)
        } catch (e: CancellationException) {
            throw e
        } catch (_: IOException) {
            val again = try {
                lookupCached(text)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                null
            }
            if (!stillCurrent(gen)) return
            if (again != null && again.candidates.isNotEmpty()) {
                publish(gen) {
                    it.copy(candidates = again.candidates, expanding = false, error = null, notice = null)
                }
                finishActive(gen)
            } else {
                publish(gen) {
                    it.copy(
                        expanding = false,
                        error = if (it.candidates.isEmpty()) {
                            mapSearchError(IOException("lookup expand failed"))
                        } else {
                            null
                        },
                        notice = if (it.candidates.isNotEmpty()) expandFailedNotice else null,
                    )
                }
            }
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

    private fun mergeShownCandidates(
        current: List<LookupCandidate>,
        incoming: List<LookupCandidate>,
    ): List<LookupCandidate> {
        if (current.isEmpty()) return incoming
        if (incoming.isEmpty()) return current
        val used = BooleanArray(incoming.size)
        val out = ArrayList<LookupCandidate>(incoming.size)
        for (cur in current) {
            val match = incoming.withIndex().firstOrNull { (i, inc) ->
                !used[i] && sameShownLemma(cur, inc)
            } ?: continue
            used[match.index] = true
            val inc = match.value
            out.add(inc.copy(
                in_learning = cur.in_learning || inc.in_learning,
                learning_card_id = cur.learning_card_id ?: inc.learning_card_id,
                list_id = cur.list_id ?: inc.list_id,
                list_name = cur.list_name ?: inc.list_name,
                enrichment_status = cur.enrichment_status ?: inc.enrichment_status,
                membershipUnknown = cur.membershipUnknown,
            ))
        }
        incoming.forEachIndexed { i, inc ->
            if (!used[i]) out.add(inc)
        }
        return out
    }

    private fun sameShownLemma(a: LookupCandidate, b: LookupCandidate): Boolean {
        if (!a.lemma.equals(b.lemma, ignoreCase = true)) return false
        val left = com.vocabulario.app.data.normalizePosKey(a.pos)
        val right = com.vocabulario.app.data.normalizePosKey(b.pos)
        if (left != "unknown" && right != "unknown" && left != right) return false
        return true
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

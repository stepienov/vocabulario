package com.vocabulario.app.data.lookup

import com.vocabulario.app.R
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.sync.BackgroundJobScheduler
import com.vocabulario.app.i18n.UiStrings
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.IOException
import java.util.UUID
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
    private data class PersistenceWrite(
        val query: String?,
        val operationId: String? = null,
        val completed: CompletableDeferred<Unit> = CompletableDeferred(),
    )
    private val writes = Channel<PersistenceWrite>(Channel.UNLIMITED)

    private fun persist(query: String?, operationId: String? = null): CompletableDeferred<Unit> {
        val write = PersistenceWrite(query, operationId)
        check(writes.trySend(write).isSuccess)
        return write.completed
    }

    private val session = LookupSession(
        lookupCached = { repository.lookupCached(it) },
        lookupExpand = { text, more, operationId -> repository.lookupExpand(text, more, operationId) },
        mapSearchError = { it.userMessage(strings, R.string.err_search) },
        expandFailedNotice = strings.get(R.string.err_lookup_expand),
        longerAnalysisNotice = { strings.get(R.string.lookup_longer_analysis, it) },
        nothingFoundNotice = { strings.get(R.string.lookup_nothing_found, it) },
        parent = appScope,
        singleRequest = true,
        onActiveQuery = { query, _ -> persist(query) },
        persistMore = { query, operationId -> persist(query, operationId).await() },
    )

    val state: StateFlow<LookupSessionState> get() = session.state

    init {
        appScope.launch {
            for (write in writes) {
                try {
                    if (write.query.isNullOrBlank()) {
                        persistence.clearIfByCategory(byCategory = false)
                    } else {
                        persistence.saveQuery(
                            write.query, more = write.operationId != null,
                            operationId = write.operationId,
                        )
                    }
                    write.completed.complete(Unit)
                } catch (e: CancellationException) {
                    write.completed.cancel(e)
                    throw e
                } catch (e: Exception) {
                    android.util.Log.e("LookupCoordinator", "Could not persist lookup", e)
                    write.completed.completeExceptionally(e)
                }
            }
        }
        appScope.launch {
            val stored = persistence.loadActive() ?: return@launch
            if (stored.byCategory || state.value.query.isNotBlank()) return@launch
            if (stored.more && stored.operationId != null) {
                session.resumeMore(stored.query, stored.operationId)
            } else {
                session.start(stored.query)
            }
        }
    }

    fun start(query: String) {
        session.start(query)
        appScope.launch {
            backgroundJobs.cancelLookup()
        }
    }

    fun showMore() = session.showMore()

    fun clear() {
        session.clear()
        backgroundJobs.cancelLookup()
    }

    fun acceptServerResult(query: String, response: LookupResponse, operationId: String? = null) =
        session.acceptServerResult(query, response, operationId)

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
            val stored = persistence.loadActive() ?: return@launch
            if (stored.byCategory) return@launch
            val now = session.state.value
            if (now.expanding || now.loadingMore) {
                now.query.takeIf { it.isNotBlank() }?.let { session.refreshFromCache() }
                return@launch
            }
            if (stored.more && stored.operationId != null) {
                session.resumeMore(stored.query, stored.operationId)
                return@launch
            }
            if (now.candidates.isNotEmpty() && now.error == null) {
                persist(null)
                return@launch
            }
            start(stored.query)
        }
    }
}

internal class LookupSession(
    private val lookupCached: suspend (String) -> LookupResponse,
    private val lookupExpand: suspend (String, Boolean, String?) -> LookupResponse,
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
    private val persistMore: suspend (String, String) -> Unit = { _, _ -> },
) {
    private val scope = CoroutineScope(parent.coroutineContext + SupervisorJob())
    private val _state = MutableStateFlow(LookupSessionState())
    val state: StateFlow<LookupSessionState> = _state.asStateFlow()
    private var job: Job? = null
    private var moreOperationId: String? = null
    private var morePersistence: Deferred<Unit>? = null

    fun start(query: String) {
        val text = query.trim()
        if (text.isBlank()) return
        val gen = _state.value.generation + 1
        job?.cancel()
        moreOperationId = null
        morePersistence = null
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
        moreOperationId = null
        morePersistence = null
        onActiveQuery(null, false)
        _state.value = LookupSessionState(generation = _state.value.generation + 1)
    }

    fun showMore() {
        val current = _state.value
        val text = current.query
        if (text.isBlank() || current.candidates.isEmpty() || current.loadingMore) return
        startMore(text, moreOperationId ?: UUID.randomUUID().toString(), restore = false)
    }

    fun resumeMore(query: String, operationId: String) {
        if (_state.value.loadingMore && moreOperationId == operationId) return
        startMore(query, operationId, restore = true)
    }

    private fun startMore(text: String, operationId: String, restore: Boolean) {
        val current = _state.value
        val gen = current.generation
        job?.cancel()
        moreOperationId = operationId
        val saved = if (restore) {
            CompletableDeferred(Unit)
        } else {
            scope.async(start = CoroutineStart.UNDISPATCHED) { persistMore(text, operationId) }
        }
        morePersistence = saved
        _state.value = if (restore && current.query != text) {
            LookupSessionState(generation = gen + 1, query = text, loadingMore = true)
        } else {
            current.copy(query = text, loadingMore = true, notice = null)
        }
        val activeGen = _state.value.generation
        job = scope.launch {
            try {
                saved.await()
                val response = withIoRetry { lookupExpand(text, true, operationId) }
                if (!stillCurrent(activeGen)) return@launch
                publish(activeGen) {
                    if (response.added == 0) {
                        it.copy(
                            loadingMore = false,
                            suggestionsExhausted = true,
                            candidates = mergeShownCandidates(it.candidates, response.candidates),
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
                moreOperationId = null
                morePersistence = null
                finishActive(activeGen)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                publish(activeGen) { it.copy(loadingMore = false, notice = expandFailedNotice) }
            }
        }
    }

    /** Nie restartuje joba — dokłada wynik z cache do aktualnej generacji. */
    fun refreshFromCache() {
        val snapshot = _state.value
        val text = snapshot.query
        if (text.isBlank()) return
        val operationId = moreOperationId
        val saved = morePersistence
        val gen = snapshot.generation
        scope.launch {
            val cached = try {
                if (snapshot.loadingMore && operationId != null) {
                    saved?.await()
                    if (moreOperationId != operationId || !_state.value.loadingMore) return@launch
                    lookupExpand(text, true, operationId)
                } else {
                    lookupCached(text)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                return@launch
            }
            if (snapshot.loadingMore &&
                (moreOperationId != operationId || !_state.value.loadingMore)
            ) return@launch
            if (!snapshot.loadingMore && _state.value.loadingMore) return@launch
            if (applyCachedOutcome(cached, gen) && (snapshot.expanding || snapshot.loadingMore)) {
                moreOperationId = null
                morePersistence = null
                job?.cancel()
                job = null
            }
        }
    }

    fun acceptServerResult(query: String, response: LookupResponse, operationId: String? = null) {
        val text = query.trim()
        if (text.isBlank()) return
        val current = _state.value
        if (current.query.isNotBlank() && current.query != text) return
        if (current.loadingMore && moreOperationId != operationId) return
        if (operationId != null && current.query == text &&
            current.candidates.isNotEmpty() && moreOperationId != operationId
        ) return
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
            moreOperationId = null
            morePersistence = null
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
                    val expanded = withIoRetry { lookupExpand(text, false, null) }
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
                    candidates = if (it.loadingMore) {
                        mergeShownCandidates(it.candidates, cached.candidates)
                    } else {
                        cached.candidates
                    },
                    expanding = !cached.ai_complete,
                    // Worker / cache mogą domknąć „Show more” zanim foreground job skończy HTTP.
                    loadingMore = if (cached.ai_complete) false else it.loadingMore,
                    suggestionsExhausted = if (cached.ai_complete) {
                        cached.suggestions_exhausted || (it.loadingMore && cached.added == 0)
                    } else {
                        it.suggestionsExhausted
                    },
                    error = null,
                    notice = null,
                )
            }
            if (cached.ai_complete) {
                finishActive(gen)
                true
            } else {
                false
            }
        } else if (cached.ai_complete) {
            publish(gen) {
                it.copy(
                    expanding = false,
                    loadingMore = false,
                    suggestionsExhausted = cached.suggestions_exhausted || it.suggestionsExhausted,
                    error = null,
                )
            }
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
            val expanded = withIoRetry { lookupExpand(text, false, null) }
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

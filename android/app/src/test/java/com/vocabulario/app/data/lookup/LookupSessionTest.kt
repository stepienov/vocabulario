package com.vocabulario.app.data.lookup

import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupResponse
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LookupSessionTest {

    @Test
    fun cancelDoesNotPublishSearchError() = runTest {
        val hanging = CompletableDeferred<Unit>()
        val session = session(
            parent = this,
            lookupExpand = {
                hanging.complete(Unit)
                awaitCancellation()
            },
        )
        session.start("saber")
        hanging.await()
        session.clear()
        advanceUntilIdle()
        assertNull(session.state.value.error)
        assertFalse(session.state.value.expanding)
        assertTrue(session.state.value.candidates.isEmpty())
    }

    @Test
    fun replacingQueryDoesNotTreatCancelAsFailure() = runTest {
        val firstExpand = CompletableDeferred<Unit>()
        var expandCalls = 0
        val session = session(
            parent = this,
            lookupExpand = {
                expandCalls++
                if (expandCalls == 1) {
                    firstExpand.complete(Unit)
                    awaitCancellation()
                }
                LookupResponse(listOf(candidate("casa")), source = "wiki")
            },
        )
        session.start("saber")
        firstExpand.await()
        session.start("casa")
        advanceUntilIdle()
        assertNull(session.state.value.error)
        assertEquals("casa", session.state.value.query)
        assertEquals(listOf("casa"), session.state.value.candidates.map { it.lemma })
        assertFalse(session.state.value.expanding)
    }

    @Test
    fun resultsStayAfterCallerScopeIsCancelled() = runTest {
        val appScope = CoroutineScope(coroutineContext + SupervisorJob())
        val expandGate = CompletableDeferred<Unit>()
        val session = session(
            parent = appScope,
            lookupExpand = {
                expandGate.await()
                LookupResponse(listOf(candidate("deska")), source = "wiki")
            },
        )
        session.start("deska")
        assertTrue(session.state.value.expanding)
        expandGate.complete(Unit)
        advanceUntilIdle()
        assertEquals(listOf("deska"), session.state.value.candidates.map { it.lemma })
        assertTrue(session.state.value.hasResultsOrProgress)
        assertFalse(session.state.value.expanding)
    }

    @Test
    fun ioExceptionRetriesOnce() = runTest {
        var attempts = 0
        val session = session(
            parent = this,
            ioRetryDelayMs = 0,
            lookupExpand = {
                attempts++
                if (attempts == 1) throw IOException("connection reset")
                LookupResponse(listOf(candidate("hola")), source = "wiki")
            },
        )
        session.start("hola")
        advanceUntilIdle()
        assertEquals(2, attempts)
        assertEquals(listOf("hola"), session.state.value.candidates.map { it.lemma })
        assertNull(session.state.value.error)
    }

    @Test
    fun cancellationExceptionIsNotMappedToError() = runTest {
        val session = session(
            parent = this,
            lookupExpand = { throw CancellationException("viewModel cleared") },
        )
        session.start("saber")
        advanceUntilIdle()
        assertNull(session.state.value.error)
    }

    @Test
    fun expandIoFailurePollsCachedUntilReady() = runTest {
        var cachedCalls = 0
        val session = session(
            parent = this,
            ioRetryDelayMs = 0,
            cachedPollDelayMs = 0,
            cachedPollAttempts = 5,
            lookupCached = {
                cachedCalls++
                if (cachedCalls < 4) {
                    LookupResponse(emptyList(), source = "none")
                } else {
                    LookupResponse(listOf(candidate("hola")), source = "db", ai_complete = true)
                }
            },
            lookupExpand = { throw IOException("connection reset") },
        )
        session.start("hola")
        advanceUntilIdle()
        assertTrue(cachedCalls >= 4)
        assertEquals(listOf("hola"), session.state.value.candidates.map { it.lemma })
        assertNull(session.state.value.error)
        assertFalse(session.state.value.expanding)
    }

    @Test
    fun cachedHitsKeepExpandingUntilFullPrompt() = runTest {
        val expandStarted = CompletableDeferred<Unit>()
        val session = session(
            parent = this,
            lookupCached = {
                LookupResponse(listOf(candidate("casa")), source = "dict", ai_complete = false)
            },
            lookupExpand = {
                expandStarted.complete(Unit)
                awaitCancellation()
            },
        )
        session.start("casa")
        expandStarted.await()
        assertEquals(listOf("casa"), session.state.value.candidates.map { it.lemma })
        assertTrue(session.state.value.expanding)
        assertNull(session.state.value.error)
        session.clear()
    }

    @Test
    fun expandingSessionOpensAddTab() {
        val expanding = LookupSessionState(query = "deska", expanding = true)
        val done = LookupSessionState(
            query = "deska",
            candidates = listOf(LookupCandidate("deska", "noun", "board")),
        )
        assertTrue(expanding.hasResultsOrProgress)
        assertTrue(done.hasResultsOrProgress)
        assertFalse(LookupSessionState().hasResultsOrProgress)
    }

    @Test
    fun hangingExpandCompletesFromParallelCachedPoll() = runTest {
        var cachedCalls = 0
        val session = session(
            parent = this,
            ioRetryDelayMs = 0,
            cachedPollDelayMs = 5,
            lookupCached = {
                cachedCalls++
                if (cachedCalls == 1) {
                    LookupResponse(emptyList(), source = "none")
                } else {
                    LookupResponse(listOf(candidate("hola")), source = "db", ai_complete = true)
                }
            },
            lookupExpand = { awaitCancellation() },
        )
        session.start("hola")
        advanceUntilIdle()
        assertEquals(listOf("hola"), session.state.value.candidates.map { it.lemma })
        assertFalse(session.state.value.expanding)
        assertNull(session.state.value.error)
        assertTrue(cachedCalls >= 2)
    }

    @Test
    fun refreshFromCacheUnblocksFrozenExpand() = runTest {
        var cachedCalls = 0
        val expandStarted = CompletableDeferred<Unit>()
        val session = session(
            parent = this,
            ioRetryDelayMs = 0,
            cachedPollDelayMs = 60_000,
            lookupCached = {
                cachedCalls++
                if (cachedCalls == 1) {
                    LookupResponse(emptyList(), source = "none")
                } else {
                    LookupResponse(listOf(candidate("deska")), source = "db", ai_complete = true)
                }
            },
            lookupExpand = {
                expandStarted.complete(Unit)
                awaitCancellation()
            },
        )
        session.start("deska")
        expandStarted.await()
        assertTrue(session.state.value.expanding)
        session.refreshFromCache()
        advanceTimeBy(1)
        runCurrent()
        assertEquals(listOf("deska"), session.state.value.candidates.map { it.lemma })
        assertFalse(session.state.value.expanding)
        assertNull(session.state.value.error)
        session.clear()
    }

    @Test
    fun acceptServerResultCancelsHangingExpand() = runTest {
        val expandStarted = CompletableDeferred<Unit>()
        val session = session(
            parent = this,
            ioRetryDelayMs = 0,
            cachedPollDelayMs = 60_000,
            lookupExpand = {
                expandStarted.complete(Unit)
                awaitCancellation()
            },
        )
        session.start("casa")
        expandStarted.await()
        session.acceptServerResult(
            "casa",
            LookupResponse(listOf(candidate("casa")), source = "db", ai_complete = true),
        )
        runCurrent()
        assertEquals(listOf("casa"), session.state.value.candidates.map { it.lemma })
        assertFalse(session.state.value.expanding)
        session.clear()
    }

    @Test
    fun singleRequestKeepsPartialCandidatesWithoutExpand() = runTest {
        var expandCalls = 0
        val session = session(
            parent = this,
            singleRequest = true,
            lookupCached = {
                LookupResponse(listOf(candidate("el castillo")), source = "ai", ai_complete = false)
            },
            lookupExpand = {
                expandCalls++
                LookupResponse(emptyList(), source = "ai")
            },
        )
        session.start("zamek")
        advanceUntilIdle()
        assertEquals(0, expandCalls)
        assertEquals(listOf("el castillo"), session.state.value.candidates.map { it.lemma })
        assertFalse(session.state.value.expanding)
    }

    @Test
    fun singleRequestEmptyAnswerExpandsOnce() = runTest {
        var cachedCalls = 0
        var expandCalls = 0
        val session = session(
            parent = this,
            singleRequest = true,
            ioRetryDelayMs = 0,
            lookupCached = {
                cachedCalls++
                LookupResponse(emptyList(), source = "db", ai_complete = false)
            },
            lookupExpand = {
                expandCalls++
                LookupResponse(listOf(candidate("el castillo")), source = "ai", ai_complete = true)
            },
        )
        session.start("zamek")
        advanceUntilIdle()
        assertEquals(1, cachedCalls)
        assertEquals(1, expandCalls)
        assertEquals(listOf("el castillo"), session.state.value.candidates.map { it.lemma })
        assertFalse(session.state.value.expanding)
    }

    @Test
    fun cachedHitRestoresExhaustedSuggestions() = runTest {
        val session = session(
            parent = this,
            singleRequest = true,
            lookupCached = {
                LookupResponse(
                    listOf(candidate("mucho")),
                    source = "db",
                    ai_complete = true,
                    suggestions_exhausted = true,
                )
            },
        )
        session.start("muchN")
        advanceUntilIdle()
        assertTrue(session.state.value.suggestionsExhausted)
        assertNull(session.state.value.notice)
    }

    @Test
    fun showMoreWithNothingAddedKeepsTilesAndHidesTheButton() = runTest {
        val session = session(
            parent = this,
            singleRequest = true,
            lookupCached = {
                LookupResponse(listOf(candidate("el perro")), source = "db", ai_complete = true)
            },
            lookupMore = {
                LookupResponse(listOf(candidate("el perro")), source = "db", ai_complete = true, added = 0)
            },
        )
        session.start("pies")
        advanceUntilIdle()
        session.showMore()
        advanceUntilIdle()
        assertEquals(listOf("el perro"), session.state.value.candidates.map { it.lemma })
        assertTrue(session.state.value.suggestionsExhausted)
        assertNull(session.state.value.notice)
        assertFalse(session.state.value.loadingMore)
    }

    @Test
    fun singleRequestEmptyExpandShowsNothingFound() = runTest {
        val session = session(
            parent = this,
            singleRequest = true,
            ioRetryDelayMs = 0,
            nothingFoundNotice = { "none:$it" },
            longerAnalysisNotice = { "longer:$it" },
            lookupCached = {
                LookupResponse(emptyList(), source = "db", ai_complete = false)
            },
            lookupExpand = {
                LookupResponse(emptyList(), source = "ai", ai_complete = true)
            },
        )
        session.start("terwa")
        advanceUntilIdle()
        assertTrue(session.state.value.candidates.isEmpty())
        assertEquals("none:terwa", session.state.value.notice)
        assertFalse(session.state.value.expanding)
    }

    @Test
    fun showMoreAppendsANewCandidate() = runTest {
        val session = session(
            parent = this,
            singleRequest = true,
            lookupCached = {
                LookupResponse(listOf(candidate("el perro")), source = "db", ai_complete = true)
            },
            lookupMore = {
                LookupResponse(
                    listOf(candidate("el perro"), candidate("el pie")),
                    source = "ai",
                    ai_complete = true,
                    added = 1,
                )
            },
        )
        session.start("pies")
        advanceUntilIdle()
        session.showMore()
        advanceUntilIdle()
        assertEquals(listOf("el perro", "el pie"), session.state.value.candidates.map { it.lemma })
        assertNull(session.state.value.notice)
    }

    @Test
    fun showMoreKeepsVisibleOrderAndAppendsEvenWhenServerRanksTheNewRowFirst() = runTest {
        val session = session(
            parent = this,
            singleRequest = true,
            lookupCached = {
                LookupResponse(
                    listOf(candidate("el camino"), candidate("la carretera")),
                    source = "db",
                    ai_complete = true,
                )
            },
            lookupMore = {
                LookupResponse(
                    listOf(candidate("la vía"), candidate("el camino"), candidate("la carretera")),
                    source = "ai",
                    ai_complete = true,
                    added = 1,
                )
            },
        )
        session.start("droga")
        advanceUntilIdle()
        session.showMore()
        advanceUntilIdle()
        assertEquals(
            listOf("el camino", "la carretera", "la vía"),
            session.state.value.candidates.map { it.lemma },
        )
    }

    private fun session(
        parent: CoroutineScope,
        lookupCached: suspend (String) -> LookupResponse = {
            LookupResponse(emptyList(), source = "none")
        },
        lookupExpand: suspend (String) -> LookupResponse = {
            LookupResponse(emptyList(), source = "none")
        },
        lookupMore: suspend (String) -> LookupResponse = lookupExpand,
        ioRetryDelayMs: Long = 1_500L,
        cachedPollDelayMs: Long = 0L,
        cachedPollAttempts: Int = 0,
        singleRequest: Boolean = false,
        longerAnalysisNotice: (String) -> String = { "" },
        nothingFoundNotice: (String) -> String = { "" },
    ) = LookupSession(
        lookupCached = lookupCached,
        lookupExpand = { text, more -> if (more) lookupMore(text) else lookupExpand(text) },
        mapSearchError = { "search-failed" },
        expandFailedNotice = "expand-failed",
        parent = parent,
        longerAnalysisNotice = longerAnalysisNotice,
        nothingFoundNotice = nothingFoundNotice,
        singleRequest = singleRequest,
        ioRetryDelayMs = ioRetryDelayMs,
        cachedPollDelayMs = cachedPollDelayMs,
        cachedPollAttempts = cachedPollAttempts,
    )

    private fun candidate(lemma: String) = LookupCandidate(
        lemma = lemma,
        pos = "noun",
        gloss = lemma,
    )
}

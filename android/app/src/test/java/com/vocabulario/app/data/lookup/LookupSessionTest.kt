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
import kotlinx.coroutines.test.advanceUntilIdle
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

    private fun session(
        parent: CoroutineScope,
        lookupCached: suspend (String) -> LookupResponse = {
            LookupResponse(emptyList(), source = "none")
        },
        lookupExpand: suspend (String) -> LookupResponse = {
            LookupResponse(emptyList(), source = "none")
        },
        ioRetryDelayMs: Long = 1_500L,
    ) = LookupSession(
        lookupCached = lookupCached,
        lookupExpand = lookupExpand,
        mapSearchError = { "search-failed" },
        expandFailedNotice = "expand-failed",
        parent = parent,
        ioRetryDelayMs = ioRetryDelayMs,
    )

    private fun candidate(lemma: String) = LookupCandidate(
        lemma = lemma,
        pos = "noun",
        gloss = lemma,
    )
}

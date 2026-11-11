package com.vocabulario.app.data.lookup

import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupResponse
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AssociationSessionTest {

    @Test
    fun headwordIsRemovedFromTheRoundInEitherOrder() = runTest {
        val wordGate = CompletableDeferred<Unit>()
        val roundGate = CompletableDeferred<Unit>()
        val session = session(
            parent = this,
            lookupWord = {
                wordGate.await()
                response(candidate("la pradera", "łąka"))
            },
            lookupRound = { _, _ ->
                roundGate.await()
                response(candidate("pradera", "łąka"), candidate("flor", "kwiat"))
            },
        )
        session.start("łąka")
        roundGate.complete(Unit)
        advanceUntilIdle()
        assertEquals(listOf("pradera", "flor"), session.state.value.rounds.single().map { it.lemma })
        wordGate.complete(Unit)
        advanceUntilIdle()
        assertEquals("la pradera", session.state.value.word?.lemma)
        assertEquals(listOf("flor"), session.state.value.rounds.single().map { it.lemma })
    }

    @Test
    fun moreAfterTheThirdRoundDoesNotCallTheNetwork() = runTest {
        var rounds = 0
        val session = session(
            parent = this,
            lookupRound = { _, _ ->
                rounds += 1
                response(candidate("flor$rounds", "kwiat"))
            },
        )
        session.start("łąka")
        advanceUntilIdle()
        session.more()
        advanceUntilIdle()
        session.more()
        advanceUntilIdle()
        val calls = rounds
        session.more()
        advanceUntilIdle()
        assertEquals(calls, rounds)
        assertTrue(session.state.value.exhausted)
        assertFalse(session.state.value.canAskMore)
    }

    @Test
    fun emptySecondRoundMarksTheListFinished() = runTest {
        var round = 0
        val session = session(
            parent = this,
            lookupRound = { _, _ ->
                round += 1
                if (round == 1) response(candidate("flor", "kwiat")) else response()
            },
        )
        session.start("łąka")
        advanceUntilIdle()
        session.more()
        advanceUntilIdle()
        assertTrue(session.state.value.exhausted)
        assertTrue(session.state.value.rounds.size == 1)
    }

    @Test
    fun notReadyLeavesTheButton() = runTest {
        var round = 0
        val session = session(
            parent = this,
            lookupRound = { _, _ ->
                round += 1
                if (round == 1) response(candidate("flor", "kwiat")) else throw AssocRoundNotReady()
            },
        )
        session.start("łąka")
        advanceUntilIdle()
        session.more()
        advanceUntilIdle()
        assertFalse(session.state.value.exhausted)
        assertTrue(session.state.value.canAskMore)
        assertEquals(null, session.state.value.notice)
    }

    private fun session(
        parent: kotlinx.coroutines.test.TestScope,
        lookupWord: suspend (String) -> LookupResponse = { response(candidate("la pradera", "łąka")) },
        lookupRound: suspend (String, Int) -> LookupResponse,
    ) = AssociationSession(
        lookupWord = lookupWord,
        lookupRound = lookupRound,
        mapError = { it.message ?: "error" },
        parent = parent,
    )

    private fun candidate(lemma: String, gloss: String) = LookupCandidate(
        lemma = lemma,
        pos = "noun",
        gloss = gloss,
    )

    private fun response(vararg rows: LookupCandidate) = LookupResponse(
        candidates = rows.toList(),
        source = "ai",
    )
}

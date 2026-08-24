package com.vocabulario.app.data

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PairSessionTest {

    @Test
    fun markDataReadyDuringSwitchDoesNotClearOverlay() = runTest {
        val session = PairSession()
        val started = CompletableDeferred<Unit>()
        val finish = CompletableDeferred<Unit>()
        val job = launch {
            session.withSwitch(awaitDataReload = true) {
                started.complete(Unit)
                finish.await()
                "ok"
            }
        }
        started.await()
        assertTrue(session.busy.value)
        session.markDataReady()
        assertTrue(session.busy.value)
        finish.complete(Unit)
        job.join()
        assertTrue(session.busy.value)
        session.markDataReady()
        assertFalse(session.busy.value)
    }

    @Test
    fun awaitDataReloadFalseClearsBusyWhenBlockReturns() = runTest {
        val session = PairSession()
        session.withSwitch(awaitDataReload = false) { 1 }
        assertFalse(session.busy.value)
        session.markDataReady()
        assertFalse(session.busy.value)
    }

    @Test
    fun markDataReadyWhenIdleIsNoOp() {
        val session = PairSession()
        session.markDataReady()
        assertFalse(session.busy.value)
    }
}

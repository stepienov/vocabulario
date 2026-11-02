package com.vocabulario.app.data

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BlockingBusyTest {

    @Test
    fun nestedRunKeepsOverlayUntilOuterFinishes() = runTest {
        val busy = BlockingBusy()
        val innerStarted = CompletableDeferred<Unit>()
        val innerFinish = CompletableDeferred<Unit>()
        val outerFinish = CompletableDeferred<Unit>()
        val job = launch {
            busy.run {
                busy.run {
                    innerStarted.complete(Unit)
                    innerFinish.await()
                }
                assertTrue(busy.busy.value)
                outerFinish.await()
            }
        }
        innerStarted.await()
        assertTrue(busy.busy.value)
        innerFinish.complete(Unit)
        assertTrue(busy.busy.value)
        outerFinish.complete(Unit)
        job.join()
        assertFalse(busy.busy.value)
    }

    @Test
    fun runClearsBusyOnFailure() = runTest {
        val busy = BlockingBusy()
        runCatching {
            busy.run<Unit> { error("boom") }
        }
        assertFalse(busy.busy.value)
        assertNull(busy.message.value)
    }

    @Test
    fun extraReleaseIsSafe() {
        val busy = BlockingBusy()
        busy.release()
        assertFalse(busy.busy.value)
        busy.acquire()
        assertTrue(busy.busy.value)
        busy.release()
        assertFalse(busy.busy.value)
        assertNull(busy.message.value)
    }

    @Test
    fun nestedRunKeepsSyncMessageUntilOuterFinishes() = runTest {
        val busy = BlockingBusy()
        val innerStarted = CompletableDeferred<Unit>()
        val innerFinish = CompletableDeferred<Unit>()
        val outerFinish = CompletableDeferred<Unit>()
        val job = launch {
            busy.run {
                busy.run("Trwa synchronizacja z serwerem…") {
                    innerStarted.complete(Unit)
                    innerFinish.await()
                }
                assertTrue(busy.busy.value)
                assertEquals("Trwa synchronizacja z serwerem…", busy.message.value)
                outerFinish.await()
            }
        }
        innerStarted.await()
        assertEquals("Trwa synchronizacja z serwerem…", busy.message.value)
        innerFinish.complete(Unit)
        outerFinish.complete(Unit)
        job.join()
        assertFalse(busy.busy.value)
        assertNull(busy.message.value)
    }
}

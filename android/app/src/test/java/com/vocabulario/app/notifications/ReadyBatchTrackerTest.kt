package com.vocabulario.app.notifications

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReadyBatchTrackerTest {

    @Test
    fun emptyWatch_isNotComplete() {
        assertFalse(batchComplete(emptySet(), mapOf("a" to "ready")))
    }

    @Test
    fun stillPending_isNotComplete() {
        val watched = setOf("a", "b")
        assertFalse(batchComplete(watched, mapOf("a" to "ready", "b" to "pending")))
    }

    @Test
    fun awaitingNetwork_isNotComplete() {
        assertFalse(batchComplete(setOf("a"), mapOf("a" to "awaiting_network")))
    }

    @Test
    fun allReady_isComplete() {
        val watched = setOf("a", "b")
        val status = mapOf("a" to "ready", "b" to "ready")
        assertTrue(batchComplete(watched, status))
        assertEquals(2, readyCount(watched, status))
    }

    @Test
    fun missingCardIsStillWaiting() {
        assertFalse(batchComplete(setOf("gone", "b"), mapOf("b" to "ready")))
        assertEquals(1, readyCount(setOf("gone", "b"), mapOf("b" to "ready")))
    }

    @Test
    fun allFailed_completeButZeroReady() {
        val watched = setOf("a")
        assertTrue(batchComplete(watched, mapOf("a" to "failed")))
        assertEquals(0, readyCount(watched, mapOf("a" to "failed")))
    }
}

package com.vocabulario.app.data.sync

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncHeadlineTest {
    private fun report() = SyncReport(null, SyncScope.ACTIVE_PROFILE, 0, 0, emptyMap(), emptyMap(), 0, 0, QueueSnapshot())

    private fun headline(
        online: Boolean = true,
        status: SyncStatus = SyncStatus(),
        queue: QueueSnapshot = QueueSnapshot(),
    ) = syncHeadline(online, status, queue)

    @Test
    fun runningWinsOverEverything() {
        val status = SyncStatus(running = true, last = SyncResult.AuthRequired(report()))
        assertEquals(SyncHeadline.SYNCING, headline(status = status, queue = QueueSnapshot(outboxBlocked = 1)))
    }

    @Test
    fun accountBlocksBeatQueueState() {
        val status = SyncStatus(last = SyncResult.VerificationRequired(report()))
        assertEquals(SyncHeadline.VERIFICATION_REQUIRED, headline(status = status, queue = QueueSnapshot(reviews = 2)))
    }

    @Test
    fun blockedOrParkedNeedsAttentionEvenOffline() {
        assertEquals(SyncHeadline.NEEDS_ATTENTION, headline(online = false, queue = QueueSnapshot(outboxParked = 1)))
        assertEquals(SyncHeadline.NEEDS_ATTENTION, headline(queue = QueueSnapshot(lookupsNeedsReview = 1)))
    }

    @Test
    fun offlineDistinguishesPendingWork() {
        assertEquals(SyncHeadline.OFFLINE, headline(online = false))
        assertEquals(SyncHeadline.OFFLINE_WITH_PENDING, headline(online = false, queue = QueueSnapshot(reviews = 1)))
    }

    @Test
    fun neverClaimsSyncedWhileWorkWaits() {
        val status = SyncStatus(lastCompleteAt = 5L)
        assertEquals(SyncHeadline.SAVED_LOCALLY, headline(status = status, queue = QueueSnapshot(outboxPending = 1)))
        assertEquals(SyncHeadline.SYNCED, headline(status = status))
    }

    @Test
    fun partialOnlyWhenWorkRemains() {
        val status = SyncStatus(last = SyncResult.Offline(report()))
        assertEquals(SyncHeadline.PARTIAL, headline(status = status, queue = QueueSnapshot(moves = 1)))
        assertEquals(SyncHeadline.IDLE, headline(status = status))
    }

    @Test
    fun retryOnlyWhenSomethingWaits() {
        assertTrue(SyncHeadline.SAVED_LOCALLY.canRetry())
        assertFalse(SyncHeadline.SYNCED.canRetry())
        assertFalse(SyncHeadline.SYNCING.canRetry())
    }

    @Test
    fun conflictOffersBothSidesOthersOnlyDiscard() {
        val conflict = BlockedItem(BlockedKind.OUTBOX, "1", ProfileBlock.CONFLICT, OP_PROFILE_UPDATE, "p1")
        assertEquals(listOf(BlockedAction.APPLY_MINE, BlockedAction.ACCEPT_SERVER), blockedActions(conflict))
        val invalid = conflict.copy(reason = ProfileBlock.INVALID)
        assertEquals(listOf(BlockedAction.DISCARD), blockedActions(invalid))
        assertEquals(listOf(BlockedAction.DISCARD), blockedActions(BlockedItem(BlockedKind.REVIEW, "c", "x")))
    }
}

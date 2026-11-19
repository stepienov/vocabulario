package com.vocabulario.app.data.sync

import com.vocabulario.app.data.session.OwnerContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncModelsTest {
    private val ok: PhaseOutcome = PhaseOutcome.Ok

    private fun allPhases(outcome: PhaseOutcome): Map<SyncPhase, PhaseOutcome> =
        SyncPhase.values().associateWith { outcome }

    private fun report(
        phases: Map<SyncPhase, PhaseOutcome> = allPhases(ok),
        pulls: Map<String, PhaseOutcome> = mapOf("p1" to ok),
        confirmed: Int = 0,
        queue: QueueSnapshot = QueueSnapshot(),
    ) = SyncReport(
        owner = OwnerContext("u1", 1),
        scope = SyncScope.ACTIVE_PROFILE,
        startedAt = 0,
        finishedAt = 1,
        phases = phases,
        pullByProfile = pulls,
        sent = 0,
        confirmed = confirmed,
        queue = queue,
    )

    private fun failed(kind: FailureKind, code: String, retryable: Boolean = true, retryAfter: Long? = null) =
        PhaseOutcome.Failed(SyncFailure(kind, code, retryable, retryAfter))

    @Test
    fun classifyMapsStatusesAndCodes() {
        assertEquals(FailureKind.OFFLINE, classifyFailure(null, null, transport = true).kind)
        assertEquals(FailureKind.AUTH, classifyFailure(401, null).kind)
        assertEquals(FailureKind.AUTH, classifyFailure(403, "session_revoked").kind)
        assertEquals(FailureKind.VERIFICATION, classifyFailure(403, "email_verification_required").kind)
        assertEquals(FailureKind.LEGAL, classifyFailure(403, CODE_LEGAL_ACCEPTANCE_REQUIRED).kind)
        assertEquals(FailureKind.CURSOR_EXPIRED, classifyFailure(410, "sync_cursor_expired").kind)
        val limited = classifyFailure(429, null, retryAfterSec = 30)
        assertEquals(FailureKind.RATE_LIMITED, limited.kind)
        assertEquals(30L, limited.retryAfterSec)
        assertTrue(classifyFailure(503, null).retryable)
        assertFalse(classifyFailure(422, "invalid_sync_cursor").retryable)
        assertEquals(FailureKind.CLIENT, classifyFailure(409, "undo_conflict").kind)
    }

    @Test
    fun emptyQueueWithoutPullIsNotComplete() {
        assertTrue(evaluateSyncResult(report(pulls = emptyMap())) is SyncResult.Partial)
    }

    @Test
    fun allPhasesPullAndEmptyQueueIsComplete() {
        assertTrue(evaluateSyncResult(report()) is SyncResult.Complete)
    }

    @Test
    fun leftoverQueueIsRetryableOnlyWhenWaiting() {
        val waiting = evaluateSyncResult(report(queue = QueueSnapshot(reviews = 2)))
        assertTrue(waiting is SyncResult.Partial && waiting.retryable)
        val blockedOnly = evaluateSyncResult(report(queue = QueueSnapshot(reviews = 1, blockedReviews = 1)))
        assertTrue(blockedOnly is SyncResult.Partial && !blockedOnly.retryable)
    }

    @Test
    fun needsReviewLookupsDoNotPreventComplete() {
        val result = evaluateSyncResult(report(queue = QueueSnapshot(lookupsNeedsReview = 3)))
        assertTrue(result is SyncResult.Complete)
    }

    @Test
    fun skippedPhaseNeverCountsAsSuccess() {
        val phases = allPhases(ok) + (SyncPhase.PUSH to PhaseOutcome.NotRun("x"))
        assertTrue(evaluateSyncResult(report(phases = phases)) is SyncResult.Partial)
    }

    @Test
    fun transportFailureWithoutProgressIsOffline() {
        val phases = allPhases(PhaseOutcome.NotRun("offline")) +
            (SyncPhase.LOOKUPS to failed(FailureKind.OFFLINE, "network"))
        val result = evaluateSyncResult(report(phases = phases, pulls = emptyMap()))
        assertTrue(result is SyncResult.Offline)
        assertTrue(result.shouldRetry)
    }

    @Test
    fun authVerificationAndLegalWinAndDoNotRetry() {
        val auth = evaluateSyncResult(report(pulls = mapOf("p1" to failed(FailureKind.AUTH, "invalid_token", false))))
        assertTrue(auth is SyncResult.AuthRequired)
        assertFalse(auth.shouldRetry)
        val verification = evaluateSyncResult(
            report(phases = allPhases(failed(FailureKind.VERIFICATION, "email_verification_required", false))),
        )
        assertTrue(verification is SyncResult.VerificationRequired)
        val legal = evaluateSyncResult(
            report(pulls = mapOf("p1" to failed(FailureKind.LEGAL, CODE_LEGAL_ACCEPTANCE_REQUIRED, false))),
        )
        assertTrue(legal is SyncResult.LegalAcceptanceRequired)
    }

    @Test
    fun failureAfterProgressIsPartialAndKeepsRetryAfter() {
        val phases = allPhases(ok) + (SyncPhase.PUSH to failed(FailureKind.RATE_LIMITED, "rate_limited", true, 45))
        val result = evaluateSyncResult(report(phases = phases, confirmed = 2))
        assertTrue(result is SyncResult.Partial)
        assertEquals(45L, result.retryAfterSec)
    }

    @Test
    fun workerDecisionRetriesOnlyTransientAndWithinLimit() {
        val offline = SyncResult.Offline(report())
        assertEquals(WorkerDecision.RETRY, offline.workerDecision(0))
        assertEquals(WorkerDecision.FAILURE, offline.workerDecision(4))
        assertEquals(WorkerDecision.SUCCESS, SyncResult.Complete(report()).workerDecision(0))
        assertEquals(WorkerDecision.SUCCESS, SyncResult.Busy.workerDecision(0))
        assertEquals(WorkerDecision.SUCCESS, SyncResult.Superseded.workerDecision(0))
        assertEquals(WorkerDecision.SUCCESS, SyncResult.AuthRequired(report()).workerDecision(0))
        assertEquals(WorkerDecision.FAILURE, SyncResult.Failed(report(), "bad", false).workerDecision(0))
    }

    @Test
    fun queueSnapshotCountsBlockedAndWaiting() {
        val q = QueueSnapshot(
            reviews = 3,
            blockedReviews = 1,
            outboxParked = 1,
            lookupsNeedsReview = 2,
            contentReports = 1,
        )
        assertEquals(7, q.total)
        assertEquals(2, q.blocked)
        assertEquals(3, q.waiting)
        assertEquals(5, q.unresolved)
    }

    @Test
    fun ackAcceptsExactlyOneResultPerSentId() {
        val decision = interpretAck(
            listOf("a", "b", "c"),
            listOf(
                OpAck("a", "applied", null),
                OpAck("b", "duplicate", null),
                OpAck("c", "not_found", "card_unavailable"),
            ),
        ) as AckDecision.Valid
        assertEquals(listOf("a", "b"), decision.confirmed)
        assertEquals(mapOf("c" to "card_unavailable"), decision.blocked)
    }

    @Test
    fun ackRejectsMissingDuplicateForeignAndUnknown() {
        val sent = listOf("a", "b")
        fun code(results: List<OpAck>?) = (interpretAck(sent, results) as AckDecision.ProtocolError).code
        assertEquals("ack_missing", code(null))
        assertEquals("ack_missing_id", code(listOf(OpAck("a", "applied", null))))
        assertEquals("ack_duplicate_id", code(listOf(OpAck("a", "applied", null), OpAck("a", "applied", null))))
        assertEquals("ack_unknown_id", code(listOf(OpAck("a", "applied", null), OpAck("z", "applied", null))))
        assertEquals("ack_unknown_outcome", code(listOf(OpAck("a", "applied", null), OpAck("b", "weird", null))))
        assertTrue(interpretAck(emptyList(), null) is AckDecision.Valid)
    }

    @Test
    fun onboardingOnlyForConfirmedEmpty() {
        assertTrue(ProfileResolution.ConfirmedEmpty.needsOnboarding)
        val unavailable = resolveProfileFailure(SyncFailure(FailureKind.OFFLINE, "network", true), hasCache = false)
        assertTrue(unavailable is ProfileResolution.Unavailable)
        assertFalse(unavailable.needsOnboarding)
        assertFalse(ProfileResolution.Found(emptyList(), null, ProfileResolution.Source.SERVER).needsOnboarding)
        assertTrue(
            resolveProfileFailure(SyncFailure(FailureKind.AUTH, "invalid_token", false), false)
                is ProfileResolution.AuthRequired,
        )
        assertTrue(
            resolveProfileFailure(SyncFailure(FailureKind.VERIFICATION, "email_verification_required", false), false)
                is ProfileResolution.VerificationRequired,
        )
    }
}

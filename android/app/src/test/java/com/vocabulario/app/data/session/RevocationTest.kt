package com.vocabulario.app.data.session

import com.vocabulario.app.data.api.TokenResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class RevocationTest {

    private class FakeClock(var now: Long = 1_000_000L) : WallClock {
        override fun nowMs() = now
    }

    private class FakeQueuePersistence(var stored: RevocationQueue = RevocationQueue()) : RevocationPersistence {
        var failWrites = false
        override fun read() = stored
        override fun write(queue: RevocationQueue) {
            if (failWrites) throw IOException("disk full")
            stored = queue
        }
    }

    private class FakeLogout(vararg results: LogoutHttpResult) : RevocationTransport {
        private val queue = ArrayDeque(results.toList())
        val calls = mutableListOf<String>()
        var onCall: () -> Unit = {}
        override fun logout(refreshToken: String): LogoutHttpResult {
            calls += refreshToken
            onCall()
            return queue.removeFirst()
        }
    }

    private class FakeRefresh(vararg results: RefreshHttpResult) : RefreshTransport {
        private val queue = ArrayDeque(results.toList())
        val calls = mutableListOf<Pair<String, String>>()
        override fun refresh(inputRefresh: String, requestId: String): RefreshHttpResult {
            calls += inputRefresh to requestId
            return queue.removeFirst()
        }
    }

    private val material = RevocationMaterial("user-a", "session-1", "refresh-1", null)

    private fun setup(logout: FakeLogout = FakeLogout(), refresh: FakeRefresh = FakeRefresh()): Triple<RevocationStore, FakeQueuePersistence, RevocationProcessor> {
        val clock = FakeClock()
        val persistence = FakeQueuePersistence()
        val store = RevocationStore(persistence, clock)
        return Triple(store, persistence, RevocationProcessor(store, logout, refresh, clock))
    }

    @Test
    fun classifiesLogoutResponses() {
        assertEquals(LogoutHttpResult.Revoked, classifyLogoutResponse(204, "", null))
        assertEquals(
            LogoutHttpResult.Invalid("invalid_refresh_token"),
            classifyLogoutResponse(401, """{"detail":{"code":"invalid_refresh_token","message":"x"}}""", null),
        )
        assertEquals(LogoutHttpResult.RetryAfter(120_000), classifyLogoutResponse(429, "", "120"))
        assertEquals(LogoutHttpResult.RetryAfter(DEFAULT_RETRY_AFTER_MS), classifyLogoutResponse(429, "", "Wed, 21 Oct"))
        assertTrue(classifyLogoutResponse(503, "", null) is LogoutHttpResult.Transient)
        assertTrue(classifyLogoutResponse(408, "", null) is LogoutHttpResult.Transient)
    }

    @Test
    fun confirmedLogoutRemovesSecret() {
        val logout = FakeLogout(LogoutHttpResult.Revoked)
        val (store, persistence, processor) = setup(logout)
        store.add(material)

        val report = processor.processDue()

        assertFalse(report.retryNeeded)
        assertEquals(listOf("refresh-1"), logout.calls)
        assertTrue(persistence.stored.requests.isEmpty())
        assertEquals(RevocationSummary(0, 0), store.summary.value)
    }

    @Test
    fun invalidProofEndsUnconfirmedWithoutSecret() {
        val (store, persistence, processor) = setup(FakeLogout(LogoutHttpResult.Invalid("invalid_refresh_token")))
        store.add(material)

        processor.processDue()

        val request = persistence.stored.requests.single()
        assertEquals(RevocationState.UNCONFIRMED, request.state)
        assertFalse(request.hasSecret)
        assertEquals(RevocationSummary(0, 1), store.summary.value)
    }

    @Test
    fun transientFailureKeepsSecretAndAsksForRetry() {
        val (store, persistence, processor) = setup(FakeLogout(LogoutHttpResult.Transient("http_503")))
        store.add(material)

        assertTrue(processor.processDue().retryNeeded)
        assertEquals("refresh-1", persistence.stored.requests.single().refreshToken)
        assertEquals(RevocationState.PENDING, persistence.stored.requests.single().state)
    }

    @Test
    fun retryAfterDefersRequest() {
        val clock = FakeClock()
        val persistence = FakeQueuePersistence()
        val store = RevocationStore(persistence, clock)
        val logout = FakeLogout(LogoutHttpResult.RetryAfter(60_000))
        val processor = RevocationProcessor(store, logout, FakeRefresh(), clock)
        store.add(material)

        val report = processor.processDue()

        assertFalse(report.retryNeeded)
        assertEquals(clock.now + 60_000, report.nextDeferredAtMs)
        assertTrue(store.due().isEmpty())
        clock.now += 60_000
        assertEquals(1, store.due().size)
    }

    @Test
    fun unknownRotationIsRecoveredWithSameRequestIdAndStoredBeforeLogout() {
        val pending = PendingRefresh("req-1", "refresh-1")
        val refresh = FakeRefresh(RefreshHttpResult.Ok(TokenResponse("access-2", "refresh-2", user_id = "user-a", session_id = "session-1")))
        val logout = FakeLogout(LogoutHttpResult.Revoked)
        val (store, persistence, processor) = setup(logout, refresh)
        logout.onCall = {
            val request = persistence.stored.requests.single()
            assertEquals("refresh-2", request.refreshToken)
            assertNull(request.pendingRefresh)
        }
        store.add(material.copy(pendingRefresh = pending))

        processor.processDue()

        assertEquals(listOf("refresh-1" to "req-1"), refresh.calls)
        assertEquals(listOf("refresh-2"), logout.calls)
        assertTrue(persistence.stored.requests.isEmpty())
    }

    @Test
    fun recoveryOutcomesDoNotFakeConfirmation() {
        val pending = PendingRefresh("req-1", "refresh-1")
        val revoked = FakeLogout()
        val (store, persistence, processor) = setup(revoked, FakeRefresh(RefreshHttpResult.Rejected("session_revoked")))
        store.add(material.copy(pendingRefresh = pending))
        processor.processDue()
        assertTrue("session_revoked confirms revocation", persistence.stored.requests.isEmpty())
        assertTrue(revoked.calls.isEmpty())

        val offline = FakeLogout()
        val (store2, persistence2, processor2) = setup(offline, FakeRefresh(RefreshHttpResult.Transient("network")))
        store2.add(material.copy(pendingRefresh = pending))
        assertTrue(processor2.processDue().retryNeeded)
        assertTrue(offline.calls.isEmpty())
        assertEquals(pending, persistence2.stored.requests.single().pendingRefresh)

        val stale = FakeLogout(LogoutHttpResult.Invalid("invalid_refresh_token"))
        val (store3, persistence3, processor3) = setup(stale, FakeRefresh(RefreshHttpResult.Rejected("invalid_refresh_token")))
        store3.add(material.copy(pendingRefresh = pending))
        processor3.processDue()
        assertEquals(RevocationState.UNCONFIRMED, persistence3.stored.requests.single().state)
    }

    @Test
    fun secretIsPhysicallyPurgedAfterThirtyDays() {
        val clock = FakeClock()
        val persistence = FakeQueuePersistence()
        val store = RevocationStore(persistence, clock)
        store.add(material)
        clock.now += REVOCATION_SECRET_TTL_MS - 1
        assertEquals("refresh-1", store.load().requests.single().refreshToken)

        clock.now += 1
        val reloaded = RevocationStore(persistence, clock).load()

        val request = persistence.stored.requests.single()
        assertEquals(RevocationState.UNCONFIRMED, request.state)
        assertEquals(REVOCATION_REASON_EXPIRED, request.reason)
        assertFalse(request.hasSecret)
        assertEquals(request, reloaded.requests.single())
    }

    @Test
    fun capacityCountsReservationsAndActiveSessionButNeverDropsPending() {
        assertTrue(canReserve(pending = 31, reservations = 0, activeSession = false))
        assertFalse(canReserve(pending = 31, reservations = 0, activeSession = true))
        assertFalse(canReserve(pending = 30, reservations = 1, activeSession = true))

        val (store, persistence, _) = setup()
        repeat(31) { store.add(material) }
        val slot = store.reserve(activeSession = false)
        assertTrue(runCatching { store.reserve(activeSession = false) }.exceptionOrNull() is RevocationQueueFullException)
        store.add(material, slot)
        assertEquals(32, persistence.stored.pendingCount)
        // Wylogowanie aktywnej sesji ma własne miejsce, więc zapis nie jest blokowany limitem.
        store.add(material)
        assertEquals(33, persistence.stored.pendingCount)
    }

    @Test
    fun failedWriteDoesNotPublishRequest() {
        val (store, persistence, _) = setup()
        persistence.failWrites = true

        assertTrue(runCatching { store.add(material) }.isFailure)
        assertEquals(RevocationSummary(0, 0), store.summary.value)
        assertTrue(persistence.stored.requests.isEmpty())
    }

    @Test
    fun codecTreatsUnreadableQueueAsEmpty() {
        val xor = object : SessionCipher {
            override fun encrypt(plain: ByteArray) = plain.map { (it.toInt() xor 0x5A).toByte() }.toByteArray()
            override fun decrypt(blob: ByteArray) = encrypt(blob)
        }
        val queue = RevocationQueue(requests = listOf(RevocationRequest(id = "r1", refreshToken = "refresh-1", createdAtMs = 5)))
        assertEquals(queue, RevocationQueueCodec(xor).decode(RevocationQueueCodec(xor).encode(queue)))
        val noKey = RevocationQueueCodec(object : SessionCipher {
            override fun encrypt(plain: ByteArray) = plain
            override fun decrypt(blob: ByteArray): ByteArray = throw SessionKeyUnavailableException()
        })
        assertEquals(RevocationQueue(), noKey.decode(RevocationQueueCodec(xor).encode(queue)))
    }
}

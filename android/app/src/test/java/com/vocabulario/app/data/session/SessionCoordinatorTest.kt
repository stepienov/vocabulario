package com.vocabulario.app.data.session

import com.vocabulario.app.data.api.TokenResponse
import com.vocabulario.app.data.api.isPublicAuthPath
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class SessionCoordinatorTest {

    private class FakePersistence(var stored: StoredSession = StoredSession.Empty) : SessionPersistence {
        var failWrites = false
        var writes = 0

        val record: SessionRecord? get() = (stored as? StoredSession.Present)?.record

        override fun read(): StoredSession = stored

        override fun write(record: SessionRecord?) {
            if (failWrites) throw IOException("disk full")
            writes++
            stored = if (record == null) StoredSession.Empty else StoredSession.Present(record)
        }
    }

    private class FakeTransport(vararg results: RefreshHttpResult) : RefreshTransport {
        private val queue = ArrayDeque(results.toList())
        val calls = mutableListOf<Pair<String, String>>()
        var delayMs = 0L

        override fun refresh(inputRefresh: String, requestId: String): RefreshHttpResult {
            synchronized(calls) { calls += inputRefresh to requestId }
            if (delayMs > 0) Thread.sleep(delayMs)
            return queue.removeFirst()
        }
    }

    private class FakeLegacy(var tokens: Pair<String, String>? = null) : LegacyTokenSource {
        override fun readLegacyTokens() = tokens
        override fun removeLegacyTokens() {
            tokens = null
        }
    }

    private val active = SessionRecord(
        ownerUserId = "user-a",
        sessionId = "session-1",
        accessToken = "access-1",
        refreshToken = "refresh-1",
    )

    private fun ok(access: String, refresh: String, user: String = "user-a", session: String = "session-1") =
        RefreshHttpResult.Ok(TokenResponse(access, refresh, user_id = user, session_id = session))

    @Test
    fun transientFailureKeepsSessionAndRetriesWithSameRequestId() {
        val persistence = FakePersistence(StoredSession.Present(active))
        val transport = FakeTransport(RefreshHttpResult.Transient("network"), ok("access-2", "refresh-2"))
        val coordinator = SessionCoordinator(persistence, transport, FakeLegacy())

        assertTrue(coordinator.refreshNow() is RefreshOutcome.Failed)
        assertEquals("access-1", coordinator.peekAccessToken())
        assertTrue(coordinator.state.value is SessionState.Active)
        val firstId = persistence.record?.pendingRefresh?.requestId
        assertTrue(!firstId.isNullOrBlank())

        assertEquals(RefreshOutcome.Refreshed("access-2"), coordinator.refreshNow())
        assertEquals(transport.calls[0], transport.calls[1])
        assertEquals("refresh-1" to firstId, transport.calls[1])
        assertEquals("refresh-2", persistence.record?.refreshToken)
        assertNull(persistence.record?.pendingRefresh)
    }

    @Test
    fun pendingRequestIdSurvivesRestart() {
        val persistence = FakePersistence(StoredSession.Present(active))
        SessionCoordinator(persistence, FakeTransport(RefreshHttpResult.Transient("network")), FakeLegacy())
            .refreshNow()
        val pendingId = persistence.record?.pendingRefresh?.requestId

        val transport = FakeTransport(ok("access-2", "refresh-2"))
        SessionCoordinator(persistence, transport, FakeLegacy()).refreshNow()

        assertEquals("refresh-1" to pendingId, transport.calls.single())
    }

    @Test
    fun rejectionRequiresReauthButKeepsOwner() {
        val persistence = FakePersistence(StoredSession.Present(active))
        val coordinator = SessionCoordinator(
            persistence,
            FakeTransport(RefreshHttpResult.Rejected("session_revoked")),
            FakeLegacy(),
        )

        assertEquals(RefreshOutcome.Rejected("session_revoked"), coordinator.refreshNow())
        assertEquals(SessionState.ReauthRequired("user-a", "session_revoked"), coordinator.state.value)
        assertNull(coordinator.peekAccessToken())
        assertEquals(SessionStatus.REAUTH_REQUIRED, persistence.record?.status)
        assertEquals("user-a", persistence.record?.ownerUserId)
        assertNull(persistence.record?.refreshToken)
    }

    @Test
    fun failedWriteDoesNotPublishRefreshedPair() {
        val persistence = FakePersistence(StoredSession.Present(active))
        val transport = FakeTransport(ok("access-2", "refresh-2"))
        // Pending zapisany, dopiero zapis nowej pary zawodzi.
        val pendingOnly = object : SessionPersistence by persistence {
            var count = 0
            override fun write(record: SessionRecord?) {
                if (count++ > 0) throw IOException("disk full")
                persistence.write(record)
            }
        }
        val failing = SessionCoordinator(pendingOnly, transport, FakeLegacy())

        assertEquals(RefreshOutcome.Failed("storage"), failing.refreshNow())
        assertEquals("access-1", failing.peekAccessToken())
        assertEquals("refresh-1", persistence.record?.refreshToken)
        assertTrue(persistence.record?.pendingRefresh != null)
    }

    @Test
    fun concurrentUnauthorizedRequestsShareOneRefresh() {
        val persistence = FakePersistence(StoredSession.Present(active))
        val transport = FakeTransport(ok("access-2", "refresh-2")).apply { delayMs = 100 }
        val coordinator = SessionCoordinator(persistence, transport, FakeLegacy())
        val pool = Executors.newFixedThreadPool(8)
        val start = CountDownLatch(1)
        val fresh = AtomicInteger()
        repeat(8) {
            pool.execute {
                start.await()
                if (coordinator.refreshAfterUnauthorized("access-1") == "access-2") fresh.incrementAndGet()
            }
        }
        start.countDown()
        pool.shutdown()
        assertTrue(pool.awaitTermination(5, TimeUnit.SECONDS))

        assertEquals(1, transport.calls.size)
        assertEquals(8, fresh.get())
    }

    @Test
    fun responseForAnotherOwnerIsNotInstalled() {
        val persistence = FakePersistence(StoredSession.Present(active))
        val coordinator = SessionCoordinator(
            persistence,
            FakeTransport(ok("access-x", "refresh-x", user = "user-b")),
            FakeLegacy(),
        )

        assertEquals(RefreshOutcome.Rejected(REAUTH_REASON_SESSION_MISMATCH), coordinator.refreshNow())
        assertNull(coordinator.peekAccessToken())
        assertEquals("user-a", persistence.record?.ownerUserId)
    }

    @Test
    fun conflictAdoptsNewerStoredPairOrRequiresReauth() {
        val persistence = FakePersistence(StoredSession.Present(active))
        val newer = active.copy(accessToken = "access-9", refreshToken = "refresh-9")
        val transport = object : RefreshTransport {
            override fun refresh(inputRefresh: String, requestId: String): RefreshHttpResult {
                persistence.stored = StoredSession.Present(newer)
                return RefreshHttpResult.Rejected(CODE_REFRESH_CONFLICT)
            }
        }
        assertEquals(
            RefreshOutcome.Refreshed("access-9"),
            SessionCoordinator(persistence, transport, FakeLegacy()).refreshNow(),
        )

        val unresolved = FakePersistence(StoredSession.Present(active))
        val coordinator = SessionCoordinator(
            unresolved,
            FakeTransport(RefreshHttpResult.Rejected(CODE_REFRESH_CONFLICT)),
            FakeLegacy(),
        )
        assertEquals(RefreshOutcome.Rejected(CODE_REFRESH_CONFLICT), coordinator.refreshNow())
    }

    @Test
    fun unreadableRecordIsRecoveryWithoutWrites() {
        val persistence = FakePersistence(StoredSession.Unreadable(RECOVERY_UNREADABLE))
        val legacy = FakeLegacy("old-access" to "old-refresh")
        val coordinator = SessionCoordinator(persistence, FakeTransport(), legacy)

        coordinator.ensureLoaded()

        assertEquals(SessionState.RecoveryRequired(RECOVERY_UNREADABLE), coordinator.state.value)
        assertEquals(0, persistence.writes)
        assertNull(coordinator.peekAccessToken())
        assertEquals("old-access" to "old-refresh", legacy.tokens)
    }

    @Test
    fun retryLoadRereadsOnlyInRecovery() = runBlocking {
        val persistence = FakePersistence(StoredSession.Unreadable(RECOVERY_STORAGE))
        val coordinator = SessionCoordinator(persistence, FakeTransport(), FakeLegacy())
        coordinator.ensureLoaded()
        assertEquals(SessionState.RecoveryRequired(RECOVERY_STORAGE), coordinator.retryLoad())

        persistence.stored = StoredSession.Present(active)
        assertEquals(SessionState.Active("user-a", "session-1"), coordinator.retryLoad())
        assertEquals("access-1", coordinator.peekAccessToken())

        // Poza stanem odzyskiwania ponowienie nie przeładowuje pamięci z dysku.
        persistence.stored = StoredSession.Empty
        assertEquals(SessionState.Active("user-a", "session-1"), coordinator.retryLoad())
        assertEquals(0, persistence.writes)
    }

    @Test
    fun legacyTokensMigrateAndPlaintextIsRemovedOnlyAfterWrite() {
        val failing = FakePersistence().apply { failWrites = true }
        val kept = FakeLegacy("old-access" to "old-refresh")
        SessionCoordinator(failing, FakeTransport(), kept).ensureLoaded()
        assertEquals("old-access" to "old-refresh", kept.tokens)

        val persistence = FakePersistence()
        val legacy = FakeLegacy("old-access" to "old-refresh")
        val coordinator = SessionCoordinator(persistence, FakeTransport(), legacy)
        coordinator.ensureLoaded()

        assertNull(legacy.tokens)
        assertEquals("old-refresh", persistence.record?.refreshToken)
        assertNull(persistence.record?.ownerUserId)
        assertEquals("old-access", coordinator.peekAccessToken())
    }

    @Test
    fun installRejectsIncompleteResponseAndKeepsPreviousRecord() = runBlocking {
        val persistence = FakePersistence(StoredSession.Present(active))
        val coordinator = SessionCoordinator(persistence, FakeTransport(), FakeLegacy())
        coordinator.ensureLoaded()

        val result = runCatching { coordinator.install(TokenResponse("a", "r")) }

        assertTrue(result.exceptionOrNull() is SessionInstallException)
        assertEquals(active, persistence.record)
        assertEquals("access-1", coordinator.peekAccessToken())
    }

    @Test
    fun failedSignOutWriteKeepsSession() = runBlocking {
        val persistence = FakePersistence(StoredSession.Present(active))
        val coordinator = SessionCoordinator(persistence, FakeTransport(), FakeLegacy())
        coordinator.ensureLoaded()
        persistence.failWrites = true

        assertTrue(runCatching { coordinator.signOutLocally() }.isFailure)
        assertEquals("access-1", coordinator.peekAccessToken())

        persistence.failWrites = false
        coordinator.signOutLocally()
        assertEquals(SessionState.SignedOut, coordinator.state.value)
        assertEquals(StoredSession.Empty, persistence.stored)
    }

    @Test
    fun requireReauthDropsTokensButKeepsOwner() = runBlocking {
        val persistence = FakePersistence(StoredSession.Present(active))
        val coordinator = SessionCoordinator(persistence, FakeTransport(), FakeLegacy())

        coordinator.requireReauth(REAUTH_REASON_LEGACY_DATA)

        assertEquals(SessionState.ReauthRequired("user-a", REAUTH_REASON_LEGACY_DATA), coordinator.state.value)
        assertNull(coordinator.peekAccessToken())
        assertNull(persistence.record?.refreshToken)
        assertEquals("user-a", persistence.record?.ownerUserId)
    }

    @Test
    fun classifiesRefreshResponses() {
        val body = { code: String -> """{"detail":{"code":"$code","message":"x"}}""" }
        assertEquals(RefreshHttpResult.Rejected("session_revoked"), classifyRefreshResponse(401, body("session_revoked")))
        assertEquals(RefreshHttpResult.Rejected("refresh_conflict"), classifyRefreshResponse(409, body("refresh_conflict")))
        assertTrue(classifyRefreshResponse(401, "<html>proxy</html>") is RefreshHttpResult.Transient)
        assertTrue(classifyRefreshResponse(500, body("refresh_unavailable")) is RefreshHttpResult.Transient)
        assertTrue(classifyRefreshResponse(429, "") is RefreshHttpResult.Transient)
        assertTrue(classifyRefreshResponse(200, "{}") is RefreshHttpResult.Transient)
        val ok = classifyRefreshResponse(
            200,
            """{"access_token":"a","refresh_token":"r","user_id":"u","session_id":"s","expires_in":900}""",
        )
        assertEquals("u", (ok as RefreshHttpResult.Ok).tokens.user_id)
    }

    @Test
    fun onlyPublicAuthRoutesSkipBearer() {
        assertTrue(isPublicAuthPath("/api/v1/auth/login"))
        assertTrue(isPublicAuthPath("/auth/refresh/"))
        assertTrue(isPublicAuthPath("/api/v1/auth/logout"))
        assertFalse(isPublicAuthPath("/api/v1/auth/password"))
        assertFalse(isPublicAuthPath("/api/v1/me"))
    }

    @Test
    fun codecRoundTripsAndTreatsBadBlobAsUnreadable() {
        val xor = object : SessionCipher {
            override fun encrypt(plain: ByteArray) = plain.map { (it.toInt() xor 0x5A).toByte() }.toByteArray()
            override fun decrypt(blob: ByteArray) = encrypt(blob)
        }
        val codec = SessionRecordCodec(xor)
        val withPending = active.copy(pendingRefresh = PendingRefresh("id-1", "refresh-1"))

        assertEquals(StoredSession.Present(withPending), codec.decode(codec.encode(withPending)))
        val noKey = SessionRecordCodec(object : SessionCipher {
            override fun encrypt(plain: ByteArray) = plain
            override fun decrypt(blob: ByteArray): ByteArray = throw SessionKeyUnavailableException()
        })
        assertEquals(StoredSession.Unreadable(RECOVERY_UNREADABLE), noKey.decode(codec.encode(active)))
    }
}

package com.vocabulario.app.data

import com.vocabulario.app.data.api.UserResponse
import com.vocabulario.app.data.session.SessionState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AccountCacheTest {

    private val cached = CachedAccount(UserResponse(id = "A", email = "a@x.com", role = "user"), fetchedAtMs = 1L)

    @Test
    fun cacheIsReturnedOnlyForItsOwner() {
        assertEquals(cached, cachedFor(cached, SessionState.Active("A", "s1")))
        assertNull(cachedFor(cached, SessionState.Active("B", "s2")))
    }

    @Test
    fun noCacheWithoutKnownOwnerOrSession() {
        assertNull(cachedFor(cached, SessionState.Active(null, "s1")))
        assertNull(cachedFor(cached, SessionState.SignedOut))
        assertNull(cachedFor(null, SessionState.Active("A", "s1")))
    }
}

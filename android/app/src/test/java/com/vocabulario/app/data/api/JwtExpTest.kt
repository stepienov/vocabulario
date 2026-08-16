package com.vocabulario.app.data.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Base64

class JwtExpTest {

    @Test
    fun readsExpFromPayload() {
        val payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"sub":"u","type":"access","exp":1700000000}""".toByteArray())
        val token = "header.$payload.sig"
        assertEquals(1_700_000_000L, jwtExpiresAtEpochSeconds(token))
    }

    @Test
    fun expiringSoonWhenWithinSkew() {
        val exp = 1_000L
        val payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"exp":$exp}""".toByteArray())
        val token = "h.$payload.s"
        assertTrue(jwtIsExpiringSoon(token, nowEpochSeconds = 950, skewSeconds = 90))
        assertFalse(jwtIsExpiringSoon(token, nowEpochSeconds = 800, skewSeconds = 90))
    }
}

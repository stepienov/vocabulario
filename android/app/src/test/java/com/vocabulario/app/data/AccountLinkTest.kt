package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AccountLinkTest {
    @Test
    fun acceptsOnlySupportedAccountLinks() {
        val cases = mapOf(
            "/account/verify-email" to AccountLinkKind.VERIFY,
            "/account/reset-password" to AccountLinkKind.RESET,
        )
        for ((path, kind) in cases) {
            val link = parseAccountLink("https://vocabulario.io$path?lang=pl#token=Abc_123-z")
            assertEquals(kind, link?.kind)
            assertEquals("Abc_123-z", link?.token)
        }
    }

    @Test
    fun rejectsInvalidOriginsPathsAndFragments() {
        val invalid = listOf(
            null,
            "http://vocabulario.io/account/verify-email#token=a",
            "https://vocabulario.io.evil.test/account/verify-email#token=a",
            "https://vocabulario.io@evil.test/account/verify-email#token=a",
            "https://user@vocabulario.io/account/verify-email#token=a",
            "https://vocabulario.io:443/account/verify-email#token=a",
            "https://vocabulario.io/account/verify-email/extra#token=a",
            "https://vocabulario.io/account/change-email#token=a",
            "https://vocabulario.io/account/verify-email?token=a",
            "https://vocabulario.io/account/verify-email#token=",
            "https://vocabulario.io/account/verify-email#token=a&other=b",
            "https://vocabulario.io/account/verify-email#token=${"a".repeat(513)}",
        )
        invalid.forEach { assertNull(it, parseAccountLink(it)) }
    }
}

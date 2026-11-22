package com.vocabulario.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AccountLinkResultTest {
    @Test
    fun responseDistinguishesTerminalAndRetryableErrors() {
        assertNull(accountLinkResult(200, null))
        assertEquals(R.string.account_link_invalid, accountLinkResult(400, null))
        assertEquals(R.string.account_link_used, accountLinkResult(409, null))
        assertEquals(R.string.account_link_expired, accountLinkResult(410, null))
        assertEquals(R.string.account_link_rate_limited, accountLinkResult(429, null))
        assertEquals(R.string.account_link_error, accountLinkResult(503, null))
        assertEquals(R.string.err_password_invalid_chars, accountLinkResult(422, "password_invalid_unicode"))
    }
}

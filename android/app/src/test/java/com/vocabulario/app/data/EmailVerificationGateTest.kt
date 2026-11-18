package com.vocabulario.app.data

import com.vocabulario.app.data.session.SessionState
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EmailVerificationGateTest {

    @Test
    fun requiredOnlyForActiveSessionOfSameOwner() {
        assertTrue(verificationRequiredFor("user-a", SessionState.Active("user-a", "s-1")))
        assertFalse(verificationRequiredFor("user-a", SessionState.Active("user-b", "s-2")))
        assertFalse(verificationRequiredFor(null, SessionState.Active("user-a", "s-1")))
        assertFalse(verificationRequiredFor("user-a", SessionState.ReauthRequired("user-a", "session_revoked")))
    }
}

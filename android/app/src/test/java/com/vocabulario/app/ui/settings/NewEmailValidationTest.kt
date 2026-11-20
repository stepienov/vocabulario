package com.vocabulario.app.ui.settings

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NewEmailValidationTest {

    @Test
    fun acceptsDifferentAddressWithPassword() {
        assertNull(validateNewEmail("old@example.com", " New@Example.com ", "secret"))
    }

    @Test
    fun reportsFirstProblem() {
        assertEquals(NewEmailProblem.EMPTY, validateNewEmail("old@example.com", "  ", "secret"))
        assertEquals(NewEmailProblem.INVALID, validateNewEmail("old@example.com", "nope", "secret"))
        assertEquals(NewEmailProblem.INVALID, validateNewEmail("old@example.com", "a b@example.com", "secret"))
        assertEquals(NewEmailProblem.UNCHANGED, validateNewEmail("Old@example.com", "old@EXAMPLE.com", "secret"))
        assertEquals(NewEmailProblem.PASSWORD_EMPTY, validateNewEmail("old@example.com", "new@example.com", ""))
    }

    @Test
    fun googleOnlyAccountNeedsNoPassword() {
        assertNull(validateNewEmail("old@example.com", "new@example.com", "", passwordRequired = false))
        assertEquals(
            NewEmailProblem.UNCHANGED,
            validateNewEmail("old@example.com", "old@example.com", "", passwordRequired = false),
        )
    }
}

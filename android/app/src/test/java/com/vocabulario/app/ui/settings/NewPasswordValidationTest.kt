package com.vocabulario.app.ui.settings

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NewPasswordValidationTest {

    private val valid = "correct-horse-battery"

    @Test
    fun acceptsMatchingPasswordWithinLimits() {
        assertNull(validateNewPassword("old", valid, valid))
    }

    @Test
    fun reportsFirstProblem() {
        assertEquals(NewPasswordProblem.CURRENT_EMPTY, validateNewPassword("", valid, valid))
        assertEquals(NewPasswordProblem.TOO_SHORT, validateNewPassword("old", "a".repeat(14), "a".repeat(14)))
        assertEquals(NewPasswordProblem.TOO_LONG, validateNewPassword("old", "a".repeat(129), "a".repeat(129)))
        assertEquals(NewPasswordProblem.MISMATCH, validateNewPassword("old", valid, "$valid!"))
    }

    @Test
    fun countsEmojiAsSingleCharacters() {
        val emoji = "\uD83D\uDE42".repeat(15)
        assertNull(validateNewPassword("old", emoji, emoji))
    }
}

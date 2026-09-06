package com.vocabulario.app.i18n

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LookupReadingTest {

    @Test
    fun chipsOnlyWhenBothReadingsPresent() {
        assertFalse(lookupShowsReadingChips(listOf(null, null)))
        assertFalse(lookupShowsReadingChips(listOf("learning")))
        assertFalse(lookupShowsReadingChips(listOf("native", "native")))
        assertTrue(lookupShowsReadingChips(listOf("learning", "native")))
    }

    @Test
    fun polishUiUsesPolishLanguageNames() {
        assertEquals("Hiszpański", languageDisplayName("es", "pl"))
        assertEquals("Polski", languageDisplayName("pl", "pl"))
    }
}
